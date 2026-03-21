"""
XGPredictor — inference wrapper for the trained xG model.

After running xg.py (training), five artifact files are produced:
  xg_model_final.json        — the XGBoost model weights
  xg_scaler.pkl              — MinMaxScaler fitted on training data
  xg_zone_bounds.pkl         — spatial bounds to impute missing shot zones
  xg_selected_features.txt   — exact feature list the model expects
  xg_monotone_constraints.json — metadata only, not needed at inference

This class loads those artifacts once at startup and exposes a simple
predict() / predict_batch() interface. The preprocessing here mirrors
xg.py exactly so that the model sees the same representation at
inference as it did during training.
"""

import pickle
import numpy as np
import pandas as pd
import xgboost as xgb
from pathlib import Path

# ── Constants (must match xg.py exactly) ─────────────────────────────────────

# The 5 columns that were MinMax-scaled during training.
# The scaler was fitted in this exact order, so we must transform in the same order.
NUMERIC_COLS = ['x', 'y', 'distance_to_goal', 'angle_to_goal', 'time_min']

# Mapping from Opta period_id integers to the string names used in training.
# period_name = 'First Half' | 'Second Half' | 'Extra Time First Half' | 'Extra Time Second Half'
PERIOD_MAP = {
    1: 'First Half',
    2: 'Second Half',
    3: 'Extra Time First Half',
    4: 'Extra Time Second Half',
}

# Shots of these types were excluded from training entirely, so the model has
# no concept of them. Raise a clear error rather than silently returning garbage.
INVALID_SHOT_TYPES = {
    'is_own_goal': 'Own goals do not have an xG value.',
    'is_penalty': 'Penalties do not have an xG value (use 0.79 as convention).',
    'pattern_direct_free_kick': 'Direct free kicks are excluded from this model.',
}


class XGPredictor:
    """
    Loads trained xG model artifacts and runs inference.

    Example
    -------
    predictor = XGPredictor()          # defaults to xg_model/ directory
    xg = predictor.predict({
        'x': 88.0, 'y': 34.0,
        'distance_to_goal': 12.4, 'angle_to_goal': 0.45,
        'body_part_right_foot': 1,
        'body_part_left_foot': 0,
        'body_part_head': 0,
        'body_part_other': 0,
        'pattern_regular_play': 1,
        'pattern_fast_break': 0,
        'pattern_set_piece': 0,
        'pattern_from_corner': 0,
        'pattern_corner_situation': 0,
        'pattern_throw_in_set_piece': 0,
        'is_assisted': 1,
        'is_individual_play': 0,
        'time_min': 67,
        'period_name': 'Second Half',  # or pass period_id=2
        'shot_zone': None,             # inferred from (x, y) if None
    })
    print(f"xG: {xg:.3f}")
    """

    def __init__(self, model_dir: str | Path = None):
        """
        Load all artifacts from model_dir (defaults to the directory this
        file lives in, i.e. xg_model/).
        """
        model_dir = Path(model_dir or Path(__file__).parent)

        # ── Load the XGBoost model ────────────────────────────────────────────
        # XGBoost's native JSON format is cross-platform and version-stable.
        # We use load_model() rather than pickle so it's not tied to a specific
        # Python/xgboost version.
        self.model = xgb.XGBClassifier()
        self.model.load_model(model_dir / 'xg_model_final.json')

        # ── Load the MinMaxScaler ─────────────────────────────────────────────
        # This was fitted ONLY on X_train during training. Using the same scaler
        # at inference ensures the numeric values land in the same [0, 1] range
        # the model learned on. If we refit the scaler on new data, the inputs
        # would shift and predictions would be wrong.
        with open(model_dir / 'xg_scaler.pkl', 'rb') as f:
            self.scaler = pickle.load(f)

        # ── Load shot zone spatial bounds ─────────────────────────────────────
        # shot_zone is a categorical label (e.g. "Central", "Left Channel") that
        # some shots are missing. During training, missing zones were filled using
        # the spatial (x, y) bounds of each known zone. We replicate that here.
        with open(model_dir / 'xg_zone_bounds.pkl', 'rb') as f:
            self.zone_bounds = pickle.load(f)

        # ── Load SHAP-selected feature list ───────────────────────────────────
        # SHAP analysis during training dropped features that collectively
        # contribute less than 0.5% of total model impact. The model was then
        # retrained on only these features, so it strictly expects this exact
        # column list in this exact order.
        with open(model_dir / 'xg_selected_features.txt') as f:
            self.selected_features = [line.strip() for line in f if line.strip()]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _assign_zone(self, x: float, y: float) -> str | None:
        """
        Look up which shot zone a (x, y) coordinate falls into.
        Mirrors assign_zone() in xg.py exactly.
        Returns None if the point falls outside all known zone rectangles.
        """
        for _, row in self.zone_bounds.iterrows():
            if row['x_min'] <= x <= row['x_max'] and row['y_min'] <= y <= row['y_max']:
                return row['shot_zone']
        return None

    def _preprocess(self, shots: list[dict]) -> pd.DataFrame:
        """
        Transform a list of raw shot dicts into the feature matrix the model
        expects. Steps mirror xg.py's preprocess() function.
        """
        df = pd.DataFrame(shots)

        # ── Accept period_id (int) as an alternative to period_name (str) ────
        if 'period_id' in df.columns and 'period_name' not in df.columns:
            df['period_name'] = df['period_id'].map(PERIOD_MAP)
        df.drop(columns=['period_id'], errors='ignore', inplace=True)

        # ── Ensure shot_zone column exists (may be absent or None) ────────────
        if 'shot_zone' not in df.columns:
            df['shot_zone'] = None

        # ── Fill missing shot_zone from (x, y) ───────────────────────────────
        # This matches the spatial imputation in preprocess() step 4.
        missing = df['shot_zone'].isna()
        if missing.any():
            df.loc[missing, 'shot_zone'] = df[missing].apply(
                lambda r: self._assign_zone(r['x'], r['y']), axis=1
            )

        # ── One-hot encode shot_zone ──────────────────────────────────────────
        # pd.get_dummies creates a column for each unique value seen in this
        # batch. If a zone was present in training but not in this batch, the
        # column will be absent — we pad it with 0s in the alignment step below.
        # dummy_na=False means NaN shot_zone stays as all-zeros (no separate column).
        zone_dummies = pd.get_dummies(df['shot_zone'], prefix='zone', dummy_na=False)
        df = pd.concat([df.drop(columns=['shot_zone']), zone_dummies], axis=1)

        # ── One-hot encode period_name ────────────────────────────────────────
        period_dummies = pd.get_dummies(df['period_name'], prefix='period', dummy_na=False)
        df = pd.concat([df.drop(columns=['period_name']), period_dummies], axis=1)

        # ── Cast binary / OHE columns to int ─────────────────────────────────
        # In training, all non-numeric non-target columns were cast to int.
        # pd.get_dummies returns bool on newer pandas; int ensures compatibility.
        for col in df.columns:
            if col not in NUMERIC_COLS:
                df[col] = df[col].astype(int)

        # ── Scale numeric columns ─────────────────────────────────────────────
        # Use the scaler fitted on X_train. The column order must match exactly.
        # We only scale columns that are actually present (defensive check).
        num_cols_present = [c for c in NUMERIC_COLS if c in df.columns]
        df[num_cols_present] = self.scaler.transform(df[num_cols_present])

        # ── Align to the model's exact feature set ────────────────────────────
        # This is the key step. The model expects a fixed set of columns in a
        # fixed order (determined by SHAP selection during training).
        # - Columns the model needs but we don't have → fill with 0
        #   (e.g. a zone_* or period_* that didn't appear in this small batch)
        # - Columns we have but the model doesn't need → silently dropped by
        #   the final selection below
        for col in self.selected_features:
            if col not in df.columns:
                df[col] = 0

        return df[self.selected_features]

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(self, shot: dict) -> float:
        """
        Return the xG probability for a single shot.

        Parameters
        ----------
        shot : dict
            Raw shot fields. See class docstring for the full list.
            shot_zone may be omitted or None — it will be inferred from (x, y).
            period_name (str) or period_id (int) are both accepted.

        Returns
        -------
        float
            xG value between 0.0 and 1.0.
        """
        # Validate: reject shot types that were excluded from training
        for field, message in INVALID_SHOT_TYPES.items():
            if shot.get(field) == 1:
                raise ValueError(f"Cannot compute xG: {message}")

        df = self._preprocess([shot])
        return float(self.model.predict_proba(df)[0, 1])

    def predict_batch(self, shots: list[dict]) -> list[float]:
        """
        Return xG probabilities for a list of shots.

        Much more efficient than calling predict() in a loop because XGBoost
        processes all rows in a single forward pass through the trees.

        Parameters
        ----------
        shots : list[dict]
            List of raw shot dicts (same format as predict()).

        Returns
        -------
        list[float]
            xG values in the same order as the input list.
        """
        for i, shot in enumerate(shots):
            for field, message in INVALID_SHOT_TYPES.items():
                if shot.get(field) == 1:
                    raise ValueError(f"Shot {i}: Cannot compute xG: {message}")

        df = self._preprocess(shots)
        return self.model.predict_proba(df)[:, 1].tolist()
