# CuléVision Styling Guide

## Overview

CuléVision uses a dark theme inspired by FC Barcelona's official colours: Blaugrana Blue (`#004D98`), Blaugrana Garnet (`#A50044`), and Gold (`#EDBB00`). All colour tokens, chart defaults, and pitch plot constants are defined centrally and must be imported — never hardcoded in page or tab modules.

---

## Colour Tokens

### Source of Truth — `utils/config.py`

```python
from utils.config import COLORS

COLORS = {
    # FC Barcelona brand
    'primary_blue':   '#004D98',   # Blaugrana Blue — navbar, primary buttons
    'garnet':         '#A50044',   # Blaugrana Garnet — accent highlights
    'gold':           '#EDBB00',   # Gold — KPI values, active nav links
    'white':          '#FFFFFF',

    # Dark theme backgrounds
    'dark_bg':        '#0A0E27',   # Main page background
    'dark_secondary': '#151932',   # Cards and panels
    'dark_tertiary':  '#1E2139',   # Inputs, table rows, hover states
    'dark_border':    '#2A2F4A',   # Card borders, dividers

    # Text
    'text_primary':   '#E8E9ED',   # Main body text
    'text_secondary': '#A5A8B8',   # Labels and subtitles
}
```

### CSS Custom Properties — `assets/style.css`

The same tokens are mirrored as CSS variables in `:root`:

```css
:root {
    --barca-blue:     #004D98;
    --barca-garnet:   #A50044;
    --barca-gold:     #EDBB00;
    --dark-bg:        #0A0E27;
    --dark-secondary: #151932;
    --dark-tertiary:  #1E2139;
    --dark-border:    #2A2F4A;
    --text-primary:   #E8E9ED;
    --text-secondary: #A5A8B8;
}
```

Use CSS variables in `assets/style.css` and Python `COLORS` dict in component `style={}` props.

---

## Pitch Plot Constants — `page_utils/visualizations.py`

All pitch plot modules must import colour constants from here:

```python
from page_utils.visualizations import (
    HOME_COLOR,          # '#004D98' — Barcelona (Blaugrana Blue)
    AWAY_COLOR,          # '#A50044' — opponents (Garnet)
    GOLD,                # '#EDBB00'
    PITCH_BG,            # '#151932' — pitch background fill
    PITCH_LINE_COLOR,    # '#8899CC' — pitch line colour
)
```

`HOME_COLOR` is always Barcelona's colour regardless of actual home/away status in the match.

---

## Plotly Chart Theming — `page_utils/visualizations.py`

```python
from page_utils.visualizations import CHART_CONFIG, CHART_LAYOUT_DEFAULTS, layout_config

# Suppress the Plotly toolbar on all charts
config = CHART_CONFIG   # {'displayModeBar': False}

# Base Plotly layout (transparent background, brand font, legend at top)
fig.update_layout(**CHART_LAYOUT_DEFAULTS)

# Merge base layout with custom overrides — avoids TypeError on duplicate kwargs
fig.update_layout(**layout_config(
    title='My Chart',
    height=400,
    margin=dict(l=20, r=20, t=40, b=20),
))
```

`CHART_LAYOUT_DEFAULTS` sets:
- `paper_bgcolor` / `plot_bgcolor` → transparent
- `font` → `#E8E9ED`, size 12
- `margin` → `l=40, r=40, t=50, b=40`
- `legend` → horizontal, anchored top-centre

---

## mplsoccer Pitch Plots

All pitch visualisations are rendered server-side via mplsoccer to base64 PNG:

```python
from mplsoccer import Pitch, VerticalPitch
from page_utils.visualizations import PITCH_BG, PITCH_LINE_COLOR

pitch = Pitch(pitch_color=PITCH_BG, line_color=PITCH_LINE_COLOR)
fig, ax = pitch.draw(figsize=(10, 6.5))

# Always use scatter(), never mpatches.Circle — patches distort with axis aspect ratio
pitch.scatter(x, y, ax=ax, s=80, color=HOME_COLOR, zorder=3)
```

**Coordinate convention**: `x=0` = own goal, `x=100` = opponent goal for **both** teams. Do **not** flip away-team coordinates — Opta data is already normalised per team.

---

## Typography

| Context | Font |
|---------|------|
| Brand heading (navbar, logo text) | `'Barcelona'` (custom OTF via `@font-face`) |
| All other text | `'Segoe UI', Tahoma, Geneva, Verdana, sans-serif` |
| Code / data values | System monospace |

Font file: `assets/fonts/Barcelona FC 23-24 Tipografstore.otf`

```css
.culevision-brand {
    font-family: 'Barcelona', 'Segoe UI', sans-serif;
    color: var(--barca-gold);
}
```

---

## CSS Classes — `assets/style.css`

### Utility colour classes

```python
className="text-barca-blue"      # text colour → #004D98
className="text-barca-garnet"    # text colour → #A50044
className="text-barca-gold"      # text colour → #EDBB00
className="bg-barca-blue"        # background  → #004D98
className="bg-barca-garnet"      # background  → #A50044
className="bg-barca-gold"        # background  → #EDBB00
```

### Shadow utilities

```python
className="shadow-sm"    # subtle shadow
className="shadow"       # standard shadow
className="shadow-lg"    # prominent shadow
```

### Styled components (auto-applied via CSS selectors)

| Selector | Behaviour |
|----------|-----------|
| `.card` | Dark gradient background, hover lift + border glow |
| `.card-title` | Gold text |
| `.navbar` | Blue-to-garnet gradient, 3 px gold bottom border |
| `.navbar .nav-link` | White text, gold underline on hover/active |
| `.nav-tabs .nav-link.active` | Gold text, garnet bottom border |
| `.btn-primary` | Blue fill, hover darkens |
| `.btn-secondary` | Garnet fill |
| `.form-control`, `.form-select` | Dark tertiary background, border on focus |
| `.table tbody tr:hover` | Garnet tint highlight |
| `.modal-content` | Dark secondary background |
| `.progress-bar` | Blue-to-garnet gradient |

---

## Component Style Patterns

### Inline styles (dynamic values only)

```python
# Colour from COLORS dict
html.Div(style={'color': COLORS['gold'], 'backgroundColor': COLORS['dark_secondary']})

# KPI value label (standard pattern)
html.H3("12", style={'color': COLORS['gold'], 'fontWeight': 'bold'})

# Divider
html.Hr(style={'borderColor': COLORS['dark_border'], 'margin': '12px 0'})
```

### Dash Bootstrap cards (standard pattern)

```python
import dash_bootstrap_components as dbc

dbc.Card([
    dbc.CardBody([
        html.H6("Label", className="text-barca-gold"),
        html.H3("Value", style={'color': COLORS['gold']}),
    ])
], className="shadow-sm h-100")
```

### Plotly chart (standard pattern)

```python
import plotly.graph_objects as go
from page_utils.visualizations import CHART_CONFIG, layout_config, HOME_COLOR

fig = go.Figure()
fig.add_trace(go.Bar(x=..., y=..., marker_color=HOME_COLOR))
fig.update_layout(**layout_config(title="Chart Title", height=350))

dcc.Graph(figure=fig, config=CHART_CONFIG)
```

---

## Asset Conventions

| Asset type | Path format |
|------------|-------------|
| Team logo | `'assets/logos/team/{name}.svg'` |
| Tournament logo | `'assets/logos/tournament/{name}.png'` |
| Country flag | `'assets/logos/flags/{country}.svg'` |
| Player image | `'assets/players/{jersey}-{name}.webp'` |

All paths use the Dash-relative format `'assets/...'` — **no leading `/`**.

---

## Rules

1. **Never hardcode hex values** in page or tab modules — always import from `COLORS` or `page_utils/visualizations.py`.
2. **Never redefine colour constants locally** — import `HOME_COLOR`, `AWAY_COLOR`, `GOLD` from `page_utils/visualizations.py`.
3. **Use `layout_config(**overrides)`** instead of `**CHART_LAYOUT_DEFAULTS, key=val` — the latter raises `TypeError` on duplicate keys.
4. **Use `pitch.scatter()`** not `mpatches.Circle` — patches distort under non-square axis aspect ratios.
5. **Inline styles for dynamic values only** — static presentation belongs in `assets/style.css`.
6. **Do not flip away-team coordinates** on pitch plots — Opta data is per-team normalised.
