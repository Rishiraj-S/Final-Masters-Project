# xG Model — Expected Goals

## What is xG?

Expected Goals (xG) is a metric that quantifies the probability of a shot resulting in a goal, based on the characteristics of that shot. A value of `0.10` means a 10% chance of scoring from that position under those conditions. It is now standard in professional football analysis and used by clubs, broadcasters, and platforms like Sofascore and FBref.

---

## Model Overview

This is a **binary XGBoost classifier** trained to predict `P(goal | shot)`. The output probability is the xG value.

The model is trained on a large historical shot dataset from **Wyscout**, covering multiple top European leagues. It excludes penalties (conventionally assigned 0.79) and direct free kicks, which have fundamentally different dynamics.

---

## Input Features

After SHAP-based feature selection, the model uses **21 features**:

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

---

## Methodology

### 1. Data & Filtering
- Source: Wyscout historical shot data
- Excluded from training:
  - Own goals (no shooter intent)
  - Penalties (fixed-position, separate convention: 0.79)
  - Direct free kicks (goalkeeper wall fundamentally changes geometry)

### 2. Preprocessing
- Missing `shot_zone` values filled using spatial (x, y) bounding boxes derived from the training set
- Categorical features (`shot_zone`, `period_name`) one-hot encoded
- Five continuous features (`x`, `y`, `distance_to_goal`, `angle_to_goal`, `time_min`) normalised with **MinMaxScaler** fitted only on the training set

### 3. Baseline Model
An untuned XGBoost classifier was trained first to generate SHAP values for feature importance ranking.

### 4. Feature Selection (SHAP)
Mean absolute SHAP values were computed for all features. Features were sorted by cumulative SHAP contribution and a threshold of **99.5%** was applied — any feature contributing less than 0.5% of total model impact was dropped. This reduced the feature set from ~35 to **21 features**, improving generalisation and inference speed.

### 5. Hyperparameter Tuning
**RandomizedSearchCV** with 5-fold stratified cross-validation was run on a stratified 100k-row subsample (stratified due to severe class imbalance — goals are rare). Search space included:
- `n_estimators`, `max_depth`, `learning_rate`
- `subsample`, `colsample_bytree`
- `min_child_weight`, `gamma`, `reg_alpha`, `reg_lambda`

### 6. Monotone Constraints
The final model enforces **monotone constraints** on `distance_to_goal` (−1, must decrease xG as distance increases) and `angle_to_goal` (−1, must decrease as angle narrows). This prevents the model from learning physically impossible patterns in sparse data regions.

### 7. Final Training
The best hyperparameters were applied to the full training set with **early stopping** monitored on a validation split (logloss). The model checkpoint at the best round was saved.

---

## Artifacts

| File | Description |
|---|---|
| `xg_model_final.json` | Trained XGBoost model in native JSON format (version-stable) |
| `xg_scaler.pkl` | MinMaxScaler fitted on training data — must be the same instance used at inference |
| `xg_zone_bounds.pkl` | Spatial bounding boxes per shot zone for null imputation |
| `xg_selected_features.txt` | Exact ordered list of 21 features the model expects |
| `xg_monotone_constraints.json` | Monotone constraint map (metadata — not used at inference) |

---

## Usage

The model is accessed through `utils/xg_utils.py` in the main app, which handles the mapping from Opta event data to the model's feature space automatically.

For direct use:

```python
from xg_model.predictor import XGPredictor

predictor = XGPredictor()  # loads artifacts from xg_model/

xg = predictor.predict({
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
    'pattern_corner_situation': 0,
    'pattern_throw_in_set_piece': 0,
    'is_assisted': 1,
    'is_individual_play': 0,
    'time_min': 67,
    'period_name': 'Second Half',  # or pass period_id=2
    'shot_zone': None,             # inferred from (x, y) if None
})

print(f"xG: {xg:.3f}")
```

For batch prediction (more efficient for multiple shots):

```python
xg_list = predictor.predict_batch([shot1, shot2, shot3])
```

---

## Retraining

To retrain the model (requires the original Wyscout training data):

```bash
cd xg_model
python xg.py
```

This will overwrite all five artifact files. After retraining, restart the Dash app so the new model is loaded.

> **Note**: `xg.py` and the training data parquet files are not included in the repository. The pre-trained artifacts are committed directly and are sufficient to run the app.
