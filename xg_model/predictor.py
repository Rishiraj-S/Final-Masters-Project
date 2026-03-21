"""
XGPredictor — inference wrappers for all three xG models.

Three XGBoost models cover different shot types:
  XGPredictor        — open play, set pieces (non-FK), fast break, corners
  XGDFKPredictor     — direct free kicks only
  XGPenaltyPredictor — penalties only

Use XGRouter to automatically route any shot to the correct model without
having to decide which model to call at the point of use.

All three models share identical preprocessing logic (zone imputation,
one-hot encoding, MinMax scaling, feature alignment) — only the artifact
files and the shots they were trained on differ.
"""

import pickle
import numpy as np
import pandas as pd
import xgboost as xgb
from pathlib import Path

# ── Constants (must match xg.py / xg_dfk.py / xg_penalty.py exactly) ────────

# The 5 columns that were MinMax-scaled during training.
# The scaler was fitted in this exact order, so we must transform in the same order.
NUMERIC_COLS = ['x', 'y', 'distance_to_goal', 'angle_to_goal', 'time_min']

# Mapping from Opta period_id integers to the string names used in training.
PERIOD_MAP = {
    1: 'First Half',
    2: 'Second Half',
    3: 'Extra Time First Half',
    4: 'Extra Time Second Half',
    5: 'Penalty Shootout',   # kept by xg_penalty.py — needed for correct OHE
}


# ── Base class ────────────────────────────────────────────────────────────────

class _BaseXGPredictor:
    """
    Shared artifact loading and preprocessing logic for all three xG models.
    Subclasses point to their specific artifact files.

    Not intended to be instantiated directly — use XGPredictor,
    XGDFKPredictor, XGPenaltyPredictor, or XGRouter.
    """

    def __init__(
        self,
        model_file:    str,
        scaler_file:   str,
        zone_file:     str,
        features_file: str,
        model_dir:     Path,
    ):
        # XGBoost native JSON format — cross-platform and version-stable.
        self.model = xgb.XGBClassifier()
        self.model.load_model(model_dir / model_file)

        # MinMaxScaler fitted only on X_train — must be the same instance.
        with open(model_dir / scaler_file, 'rb') as f:
            self.scaler = pickle.load(f)

        # Spatial bounding boxes per shot zone for null imputation.
        with open(model_dir / zone_file, 'rb') as f:
            self.zone_bounds = pickle.load(f)

        # Exact ordered feature list the model expects (from SHAP selection).
        with open(model_dir / features_file) as f:
            self.selected_features = [line.strip() for line in f if line.strip()]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _assign_zone(self, x: float, y: float) -> str | None:
        """Look up the shot zone for (x, y). Mirrors assign_zone() in training scripts."""
        for _, row in self.zone_bounds.iterrows():
            if row['x_min'] <= x <= row['x_max'] and row['y_min'] <= y <= row['y_max']:
                return row['shot_zone']
        return None

    def _preprocess(self, shots: list[dict]) -> pd.DataFrame:
        """
        Transform raw shot dicts into the feature matrix the model expects.
        Steps mirror the preprocess() function in the training scripts exactly.
        Extra keys in the dict (e.g. is_penalty, pattern_direct_free_kick used
        for routing) are silently dropped by the final column alignment step.
        """
        df = pd.DataFrame(shots)

        # Accept period_id (int) as an alternative to period_name (str)
        if 'period_id' in df.columns and 'period_name' not in df.columns:
            df['period_name'] = df['period_id'].map(PERIOD_MAP)
        df.drop(columns=['period_id'], errors='ignore', inplace=True)

        # Ensure shot_zone column exists (may be absent or None)
        if 'shot_zone' not in df.columns:
            df['shot_zone'] = None

        # Fill missing shot_zone from (x, y)
        missing = df['shot_zone'].isna()
        if missing.any():
            df.loc[missing, 'shot_zone'] = df[missing].apply(
                lambda r: self._assign_zone(r['x'], r['y']), axis=1
            )

        # One-hot encode shot_zone and period_name
        zone_dummies   = pd.get_dummies(df['shot_zone'],   prefix='zone',   dummy_na=False)
        period_dummies = pd.get_dummies(df['period_name'], prefix='period', dummy_na=False)
        df = pd.concat(
            [df.drop(columns=['shot_zone', 'period_name']), zone_dummies, period_dummies],
            axis=1,
        )

        # Cast binary / OHE columns to int (pd.get_dummies returns bool on newer pandas)
        for col in df.columns:
            if col not in NUMERIC_COLS:
                df[col] = df[col].astype(int)

        # Scale numeric columns using the training scaler
        num_cols_present = [c for c in NUMERIC_COLS if c in df.columns]
        df[num_cols_present] = self.scaler.transform(df[num_cols_present])

        # Align to the model's exact feature set:
        #   - missing columns (zone/period not in this batch) → padded with 0
        #   - extra columns (routing flags, etc.) → dropped by the final selection
        for col in self.selected_features:
            if col not in df.columns:
                df[col] = 0

        return df[self.selected_features]

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(self, shot: dict) -> float:
        """Return the xG probability for a single shot (float 0–1)."""
        df = self._preprocess([shot])
        return float(self.model.predict_proba(df)[0, 1])

    def predict_batch(self, shots: list[dict]) -> list[float]:
        """
        Return xG probabilities for a list of shots.
        Much more efficient than predict() in a loop — single XGBoost forward pass.
        """
        df = self._preprocess(shots)
        return self.model.predict_proba(df)[:, 1].tolist()


# ── Concrete models ───────────────────────────────────────────────────────────

class XGPredictor(_BaseXGPredictor):
    """
    Open play xG model.
    Covers: regular play, fast break, set pieces (indirect), corners, throw-ins.
    Excludes: penalties, direct free kicks, own goals.
    """

    def __init__(self, model_dir=None):
        super().__init__(
            model_file    = 'xg_model_final.json',
            scaler_file   = 'xg_scaler.pkl',
            zone_file     = 'xg_zone_bounds.pkl',
            features_file = 'xg_selected_features.txt',
            model_dir     = Path(model_dir or Path(__file__).parent),
        )


class XGDFKPredictor(_BaseXGPredictor):
    """
    Direct free kick xG model.
    Trained exclusively on shots with pattern_direct_free_kick == 1.
    """

    def __init__(self, model_dir=None):
        super().__init__(
            model_file    = 'xg_dfk_model_final.json',
            scaler_file   = 'xg_dfk_scaler.pkl',
            zone_file     = 'xg_dfk_zone_bounds.pkl',
            features_file = 'xg_dfk_selected_features.txt',
            model_dir     = Path(model_dir or Path(__file__).parent),
        )


class XGPenaltyPredictor(_BaseXGPredictor):
    """
    Penalty xG model.
    Trained exclusively on shots with is_penalty == 1.
    Distance/angle are near-constant from the spot, so body part and
    period context drive most of the variance.
    """

    def __init__(self, model_dir=None):
        super().__init__(
            model_file    = 'xg_penalty_model_final.json',
            scaler_file   = 'xg_penalty_scaler.pkl',
            zone_file     = 'xg_penalty_zone_bounds.pkl',
            features_file = 'xg_penalty_selected_features.txt',
            model_dir     = Path(model_dir or Path(__file__).parent),
        )


# ── Router ────────────────────────────────────────────────────────────────────

class XGRouter:
    """
    Routes each shot to the appropriate xG sub-model and returns the prediction.

    Routing logic (checked in priority order):
      is_own_goal == 1              → None  (no model covers own goals)
      is_penalty == 1               → XGPenaltyPredictor
      pattern_direct_free_kick == 1 → XGDFKPredictor
      anything else                 → XGPredictor  (open play)

    predict_batch groups shots by type so each sub-model runs a single
    XGBoost forward pass — as efficient as calling each model directly.

    Usage
    -----
        router = XGRouter()
        xg = router.predict(shot_dict)          # single shot
        xg_list = router.predict_batch(shots)   # list of shots
    """

    def __init__(self, model_dir=None):
        model_dir     = Path(model_dir or Path(__file__).parent)
        self.open_play = XGPredictor(model_dir)
        self.dfk       = XGDFKPredictor(model_dir)
        self.penalty   = XGPenaltyPredictor(model_dir)

    def _route(self, shot: dict) -> str:
        if shot.get('is_own_goal') == 1:
            return 'own_goal'
        if shot.get('is_penalty') == 1:
            return 'penalty'
        if shot.get('pattern_direct_free_kick') == 1:
            return 'dfk'
        return 'open_play'

    def predict(self, shot: dict) -> float | None:
        """Return xG for a single shot, or None for own goals."""
        route = self._route(shot)
        if route == 'own_goal':
            return None
        return {'open_play': self.open_play, 'dfk': self.dfk, 'penalty': self.penalty}[route].predict(shot)

    def predict_batch(self, shots: list[dict]) -> list[float | None]:
        """
        Return xG for a list of shots. Own goals return None.
        Shots are grouped by type so each sub-model runs a single forward pass.
        """
        results: list[float | None] = [None] * len(shots)

        groups  = {'open_play': [], 'dfk': [], 'penalty': []}
        indices = {'open_play': [], 'dfk': [], 'penalty': []}

        for i, shot in enumerate(shots):
            route = self._route(shot)
            if route != 'own_goal':
                groups[route].append(shot)
                indices[route].append(i)
            # own_goal stays as None in results

        models = {'open_play': self.open_play, 'dfk': self.dfk, 'penalty': self.penalty}
        for key, model in models.items():
            if groups[key]:
                preds = model.predict_batch(groups[key])
                for idx, pred in zip(indices[key], preds):
                    results[idx] = pred

        return results
