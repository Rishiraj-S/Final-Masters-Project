# xG Model — Expected Goals

## What is xG?

Expected Goals (xG) is a metric that quantifies the probability of a shot resulting in a goal, based on the characteristics of that shot. A value of `0.10` means a 10% chance of scoring from that position under those conditions. It is now standard in professional football analysis and used by clubs, broadcasters, and platforms like Sofascore and FBref.

---

## Model Overview

The xG suite comprises **three separate XGBoost binary classifiers**, each trained on a distinct subset of shots. An `XGRouter` class automatically routes any incoming shot to the correct model.

| Model | Class | Covers |
|---|---|---|
| Open play | `XGPredictor` | Regular play, fast break, indirect set pieces, corners, throw-ins |
| Direct free kick | `XGDFKPredictor` | Shots with `pattern_direct_free_kick == 1` |
| Penalty | `XGPenaltyPredictor` | Shots with `is_penalty == 1` |

**Why three models?** Penalties and direct free kicks have fundamentally different shot dynamics — the goalkeeper wall, fixed distance, and near-constant angle mean features that drive open-play xG carry far less or different signal. Training separate models on each subset avoids contaminating the open-play model and allows each to learn the correct feature relationships.

All models share identical preprocessing logic (zone imputation, one-hot encoding, MinMax scaling, feature alignment) implemented in the `_BaseXGPredictor` base class.

All models were trained on a large historical shot dataset from **Wyscout**, covering multiple top European leagues. Own goals are excluded from all models — `XGRouter` returns `None` for own goals.

---

## Input Features

After SHAP-based feature selection, the **open play model** uses **21 features**:

### Spatial
| Feature | Description |
|---|---|
| `x` | Shot x-coordinate (0 = own goal, 100 = opponent goal) |
| `y` | Shot y-coordinate (0 = left touchline, 100 = right touchline) |
| `distance_to_goal` | Euclidean distance from shot to centre of goal |
| `angle_to_goal` | Angle (radians) subtended by the goal posts from the shot location |

### Shot Zone (one-hot encoded)
| Feature | Zone |
|---|---|
| `zone_small_box_centre` | Six-yard box |
| `zone_box_centre` | Central penalty area |
| `zone_out_of_box_centre` | Central outside the box |

*Wide zones and far-post zones were eliminated by SHAP selection — shots from those positions carry very low and near-constant xG.*

### Body Part (one-hot encoded)
| Feature | Description |
|---|---|
| `body_part_head` | Header or diving header |
| `body_part_right_foot` | Right foot |
| `body_part_left_foot` | Left foot |
| `body_part_other` | Overhead, bicycle kick, chest, etc. |

### Pattern of Play (one-hot encoded)
| Feature | Description |
|---|---|
| `pattern_regular_play` | Open play |
| `pattern_fast_break` | Counter-attack |
| `pattern_set_piece` | Indirect set piece |
| `pattern_from_corner` | Directly from a corner |
| `pattern_throw_in_set_piece` | From a throw-in set piece |

### Context
| Feature | Description |
|---|---|
| `is_assisted` | Shot was assisted (qualifier present) |
| `is_individual_play` | Shot was unassisted individual effort |
| `time_min` | Match minute |

### Period (one-hot encoded)
| Feature | Description |
|---|---|
| `period_First Half` | Shot taken in the first half |
| `period_Second Half` | Shot taken in the second half |

*Extra time periods were present in training data but eliminated by SHAP — too few shots to carry meaningful signal.*

The DFK and penalty models use their own SHAP-selected feature subsets (stored in their respective `*_selected_features.txt` files) — the penalty model in particular relies more heavily on body part and period context, as distance and angle are near-constant from the spot.

---

## Methodology

### 1. Data & Filtering
- Source: Wyscout historical shot data
- Each model trained on its specific shot subset:
  - Own goals excluded from all models
  - Open play: excludes penalties, direct free kicks, own goals
  - DFK model: only `pattern_direct_free_kick == 1`
  - Penalty model: only `is_penalty == 1`

### 2. Preprocessing
- Missing `shot_zone` values filled using spatial (x, y) bounding boxes derived from the training set
- Categorical features (`shot_zone`, `period_name`) one-hot encoded
- Five continuous features (`x`, `y`, `distance_to_goal`, `angle_to_goal`, `time_min`) normalised with **MinMaxScaler** fitted only on the training set

### 3. Baseline Model
An untuned XGBoost classifier was trained first to generate SHAP values for feature importance ranking.

### 4. Feature Selection (SHAP)
Mean absolute SHAP values were computed for all features. Features were sorted by cumulative SHAP contribution and a threshold of **99.5%** was applied — any feature contributing less than 0.5% of total model impact was dropped. This reduced the feature set from ~35 to **21 features** (open play), improving generalisation and inference speed.

### 5. Hyperparameter Tuning
**RandomizedSearchCV** with 5-fold stratified cross-validation was run on a stratified 100k-row subsample (stratified due to severe class imbalance — goals are rare). Search space included:
- `n_estimators`, `max_depth`, `learning_rate`
- `subsample`, `colsample_bytree`
- `min_child_weight`, `gamma`, `reg_alpha`, `reg_lambda`

### 6. Monotone Constraints
The final models enforce **monotone constraints** on `distance_to_goal` (−1, must decrease xG as distance increases) and `angle_to_goal` (−1, must decrease as angle narrows). This prevents the model from learning physically impossible patterns in sparse data regions.

### 7. Final Training
The best hyperparameters were applied to the full training set with **early stopping** monitored on a validation split (logloss). The model checkpoint at the best round was saved.

---

## Artifacts

### Open Play Model (`XGPredictor`)
| File | Description |
|---|---|
| `xg_model_final.json` | Trained XGBoost model in native JSON format |
| `xg_scaler.pkl` | MinMaxScaler fitted on open-play training data |
| `xg_zone_bounds.pkl` | Spatial bounding boxes per shot zone for null imputation |
| `xg_selected_features.txt` | Exact ordered list of 21 features the model expects |
| `xg_monotone_constraints.json` | Monotone constraint map (metadata) |

### Direct Free Kick Model (`XGDFKPredictor`)
| File | Description |
|---|---|
| `xg_dfk_model_final.json` | Trained XGBoost model for direct free kicks |
| `xg_dfk_scaler.pkl` | MinMaxScaler fitted on DFK training data |
| `xg_dfk_zone_bounds.pkl` | Spatial bounding boxes for DFK zone imputation |
| `xg_dfk_selected_features.txt` | SHAP-selected feature list for DFK model |
| `xg_dfk_monotone_constraints.json` | Monotone constraint map (metadata) |

### Penalty Model (`XGPenaltyPredictor`)
| File | Description |
|---|---|
| `xg_penalty_model_final.json` | Trained XGBoost model for penalties |
| `xg_penalty_scaler.pkl` | MinMaxScaler fitted on penalty training data |
| `xg_penalty_zone_bounds.pkl` | Spatial bounding boxes for penalty zone imputation |
| `xg_penalty_selected_features.txt` | SHAP-selected feature list for penalty model |
| `xg_penalty_monotone_constraints.json` | Monotone constraint map (metadata) |

---

## Usage

The model is accessed through `utils/xg_utils.py` in the main app, which handles the mapping from Opta event data to the model's feature space automatically via `XGRouter`.

For direct use, the recommended entry point is `XGRouter` — it selects the correct sub-model automatically:

```python
from xg_model.predictor import XGRouter

router = XGRouter()  # loads all three models from xg_model/

# Single shot — router picks the right model automatically
xg = router.predict({
    'x': 88.0,
    'y': 34.0,
    'distance_to_goal': 12.4,
    'angle_to_goal': 0.45,
    'body_part_right_foot': 1,
    'body_part_left_foot': 0,
    'body_part_head': 0,
    'body_part_other': 0,
    'pattern_regular_play': 1,
    'pattern_fast_break': 0,
    'pattern_set_piece': 0,
    'pattern_from_corner': 0,
    'pattern_direct_free_kick': 0,   # → open play model
    'is_penalty': 0,
    'is_own_goal': 0,
    'is_assisted': 1,
    'is_individual_play': 0,
    'time_min': 67,
    'period_name': 'Second Half',    # or pass period_id=2
    'shot_zone': None,               # inferred from (x, y) if None
})

print(f"xG: {xg:.3f}")

# Returns None for own goals
# Direct free kick: set pattern_direct_free_kick=1 → routes to XGDFKPredictor
# Penalty: set is_penalty=1 → routes to XGPenaltyPredictor
```

For batch prediction (more efficient for multiple shots):

```python
xg_list = router.predict_batch([shot1, shot2, shot3])
# Returns list[float | None] — None for own goals
```

To use a specific sub-model directly:

```python
from xg_model.predictor import XGPredictor, XGDFKPredictor, XGPenaltyPredictor

open_play = XGPredictor()
dfk       = XGDFKPredictor()
penalty   = XGPenaltyPredictor()
```

---

## Retraining

To retrain the models (requires the original Wyscout training data):

```bash
cd xg_model
python xg.py          # open play model
python xg_dfk.py      # direct free kick model
python xg_penalty.py  # penalty model
```

Each script overwrites its own five artifact files. After retraining, restart the Dash app so the new models are loaded.

> **Note**: `xg.py`, `xg_dfk.py`, `xg_penalty.py`, and the training data parquet files are not included in the repository. The pre-trained artifacts are committed directly and are sufficient to run the app.
