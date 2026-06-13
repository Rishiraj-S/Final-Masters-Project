"""
pdf_report.py
=============
Server-side match report PDF generator.

Produces a multi-section A3 PDF covering every match analysis tab with
Full / 1st-Half / 2nd-Half permutations where applicable. All figures are
rendered via the same internal functions used by the interactive Dash UI.

Dependencies (added to requirements.txt): fpdf2, kaleido
"""
from __future__ import annotations

import base64
import io
import logging
import struct
from datetime import datetime
from typing import Optional

import pandas as pd
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PNG dimension reader — avoids PIL dependency
# ---------------------------------------------------------------------------

def _png_dims(data: bytes) -> tuple[int, int]:
    """Return (width_px, height_px) from a PNG byte string. Returns (0,0) on error."""
    try:
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            w = struct.unpack('>I', data[16:20])[0]
            h = struct.unpack('>I', data[20:24])[0]
            return w, h
    except Exception:
        pass
    return 0, 0


_PAGE_H   = 297   # A4 height mm
_MARGIN_B =  15   # bottom margin mm
_SAFE_Y   = _PAGE_H - _MARGIN_B   # 282 mm

# ---------------------------------------------------------------------------
# Plotly → PNG helper (lazy import so kaleido is only required when called)
# ---------------------------------------------------------------------------

def _plotly_to_png(fig, w: int = 900, h: int = 480, scale: int = 1) -> Optional[bytes]:
    """Convert a Plotly figure to PNG bytes using kaleido."""
    try:
        import plotly.io as pio
        return pio.to_image(fig, format="png", width=w, height=h, scale=scale)
    except Exception as exc:
        log.warning("Plotly → PNG failed: %s", exc)
        return None


def _get_figure(result):
    """Accept either a go.Figure or a dcc.Graph and return the go.Figure."""
    if result is None:
        return None
    return result.figure if hasattr(result, "figure") else result


# ---------------------------------------------------------------------------
# Dash component tree → static HTML (faithful, non-screenshot capture)
#   • dcc.Graph         → kaleido PNG  (the real figure, exactly as in the app)
#   • html.Img          → <img>        (mplsoccer pitch PNGs, logos)
#   • dbc.Row/Col       → flexbox grid (preserves the app's column layout)
#   • html.Table/Div/…  → same tags with the component's inline styles intact
# ---------------------------------------------------------------------------
import re as _re

_TAG = {
    'Div': 'div', 'Span': 'span', 'P': 'p', 'H1': 'h1', 'H2': 'h2', 'H3': 'h3',
    'H4': 'h4', 'H5': 'h5', 'H6': 'h6', 'Hr': 'hr', 'I': 'i', 'Label': 'label',
    'A': 'a', 'Button': 'button', 'Strong': 'strong', 'B': 'b', 'Small': 'small',
    'Table': 'table', 'Thead': 'thead', 'Tbody': 'tbody', 'Tr': 'tr', 'Th': 'th',
    'Td': 'td', 'Ul': 'ul', 'Li': 'li',
    'Container': 'div', 'Card': 'div', 'CardBody': 'div', 'CardHeader': 'div',
    'CardFooter': 'div', 'Row': 'div', 'Col': 'div', 'Loading': 'div',
}
_VOID = {'hr', 'br', 'img'}


def _css_key(k: str) -> str:
    if k.startswith('Webkit'):
        return '-webkit-' + _re.sub('([A-Z])', lambda m: '-' + m.group(1).lower(), k[6:]).lstrip('-')
    return _re.sub('([A-Z])', lambda m: '-' + m.group(1).lower(), k)


# Map the app's dark palette → a clean light palette so the report reads as a
# light document (not dark cards pasted on white).
_DARK2LIGHT = {
    '#0A0E27': '#FFFFFF', '#0a0e27': '#FFFFFF',
    '#151932': '#FFFFFF', '#1A1D2E': '#FFFFFF', '#1a1d2e': '#FFFFFF',
    '#1E2139': '#F1F3F7', '#1e2139': '#F1F3F7',
    '#2A2F4A': '#D8DCE6', '#2a2f4a': '#D8DCE6',
    '#E8E9ED': '#1A1D2E', '#e8e9ed': '#1A1D2E',
    '#A5A8B8': '#5B5F70', '#a5a8b8': '#5B5F70',
    'rgba(255,255,255,0.03)': 'rgba(0,0,0,0.035)',
    'rgba(255,255,255,0.08)': 'rgba(0,0,0,0.06)',
    'rgba(255,255,255,0.05)': 'rgba(0,0,0,0.035)',
    'rgba(0,0,0,0.55)': 'rgba(255,255,255,0.9)',
    'rgba(0,0,0,0.5)': 'rgba(255,255,255,0.9)',
}


def _lighten_css(css: str) -> str:
    for d, l in _DARK2LIGHT.items():
        css = css.replace(d, l)
    return css


def _style_to_css(style) -> str:
    if not isinstance(style, dict):
        return ''
    return _lighten_css(';'.join(f'{_css_key(k)}:{v}' for k, v in style.items()))


def _escape(t: str) -> str:
    return (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _col_basis(node) -> int:
    # Desktop-first: the PDF page is wide, so prefer the largest breakpoint (lg)
    # to reproduce the app's desktop column layout, not the tablet (md) fallback.
    for a in ('lg', 'md', 'width', 'sm', 'xs'):
        v = getattr(node, a, None)
        if isinstance(v, int):
            return v
    return 12


_LIGHT_TEXT = {'#ffffff', '#fff', 'white', '#e8e9ed', '#a5a8b8'}


_DARK = '#1A1D2E'


def _lighten_fig(fig):
    """Re-theme a dark-designed Plotly figure for a white report page, and make
    ALL labels big & dark (radars, donuts, bars) — matching the look of the
    transition-outcomes donut."""
    try:
        fig.update_layout(paper_bgcolor='white', plot_bgcolor='white',
                          font=dict(color=_DARK, size=16))
    except Exception:
        pass
    # polar (radars) — dark, larger category labels
    try:
        if fig.layout.polar:
            fig.update_layout(polar=dict(
                bgcolor='white',
                radialaxis=dict(gridcolor='rgba(0,0,0,0.12)', linecolor='rgba(0,0,0,0.12)'),
                angularaxis=dict(gridcolor='rgba(0,0,0,0.12)', linecolor='rgba(0,0,0,0.12)',
                                 tickfont=dict(color=_DARK, size=15)),
            ))
    except Exception:
        pass
    # cartesian axes — dark, larger tick labels
    for ax in ('xaxis', 'yaxis'):
        try:
            fig.update_layout(**{ax: dict(gridcolor='rgba(0,0,0,0.10)',
                                          tickfont=dict(color=_DARK, size=15))})
        except Exception:
            pass
    # every trace's data labels → dark, big & bold
    for tr in fig.data:
        try:
            tr.update(textfont=dict(color=_DARK, size=17, family='Arial Black'))
        except Exception:
            try:
                tr.textfont.color = _DARK
            except Exception:
                pass
    # annotations (donut centre totals, zone labels) → dark & prominent
    try:
        for a in (fig.layout.annotations or []):
            if str(getattr(a.font, 'color', '')).lower() in _LIGHT_TEXT:
                a.font.color = _DARK
            try:
                if a.font.size and a.font.size < 15:
                    a.font.size = 15
            except Exception:
                pass
    except Exception:
        pass
    # legend → dark & larger
    try:
        fig.update_layout(legend=dict(font=dict(color=_DARK, size=14), bgcolor='rgba(0,0,0,0)'))
    except Exception:
        pass
    return fig


def _render_fig_png(fig) -> Optional[bytes]:
    """Render a Plotly figure to a crisp PNG.

    Pitch plots (have a background layout image) stay on the app's dark pitch with
    their white labels. Charts (radars, donuts, bars) are re-themed light and
    rendered near-square so they fill their column instead of looking tiny.
    """
    try:
        try:
            h = int(fig.layout.height) if fig.layout.height else 460
        except Exception:
            h = 460
        is_pitch = bool(getattr(fig.layout, 'images', None))
        if is_pitch:
            try:
                fig.update_layout(paper_bgcolor='#151932', plot_bgcolor='#151932')
            except Exception:
                pass
            return _plotly_to_png(fig, w=880, h=h, scale=2)

        _lighten_fig(fig)
        types = {type(t).__name__ for t in fig.data}
        if 'Pie' in types:
            # donuts (incl. small GK donuts) — enlarge ring, render square
            h = max(h, 430)
            try:
                fig.update_layout(height=h)
            except Exception:
                pass
            w = h
        elif 'Scatterpolar' in types:
            # radars — near-square
            w = max(int(h * 1.05), 420)
        elif 'Bar' in types:
            # bar plots — taller aspect so they display bigger in the column
            w = int(h * 0.7)
        elif 'Scatter' in types:
            # wide time-series / line charts (e.g. Match Flow). Keep their natural
            # wide aspect so they don't blow up to a near-square full-page image
            # when displayed at width:100% in the column.
            w = int(h * 2.6)
        else:
            # anything else — near-square
            w = max(int(h * 1.05), 420)
        return _plotly_to_png(fig, w=w, h=h, scale=2)
    except Exception as exc:
        log.warning("fig→png: %s", exc)
        return None


def _children_html(children) -> str:
    if children is None:
        return ''
    if isinstance(children, (list, tuple)):
        return ''.join(_dash_to_html(c) for c in children)
    return _dash_to_html(children)


def _dash_to_html(node) -> str:
    if node is None:
        return ''
    if isinstance(node, (str, int, float)):
        return _escape(str(node))
    ctype = type(node).__name__

    if ctype == 'Graph':
        png = _render_fig_png(getattr(node, 'figure', None)) if getattr(node, 'figure', None) is not None else None
        if not png:
            return ''
        return ('<img style="width:100%;display:block;page-break-inside:avoid" '
                f'src="data:image/png;base64,{base64.b64encode(png).decode()}">')

    if ctype == 'Img':
        src = getattr(node, 'src', '') or ''
        st = _style_to_css(getattr(node, 'style', None))
        return f'<img src="{src}" style="{st};page-break-inside:avoid">'

    tag = _TAG.get(ctype)
    if tag is None:                      # unknown wrapper → just emit children
        return _children_html(getattr(node, 'children', None))

    style = _style_to_css(getattr(node, 'style', None))
    if ctype == 'Row':
        style += ';display:flex;flex-wrap:wrap;align-items:flex-start'
    elif ctype == 'Col':
        # Honor an explicit percentage width from style (e.g. flexBasis: '70%')
        # for splits the 12-col grid can't express (Shot Map / Touch Map 70/30);
        # otherwise fall back to the bootstrap column basis.
        _sd = getattr(node, 'style', None) or {}
        _fb = _sd.get('flexBasis')
        if isinstance(_fb, str) and _fb.strip().endswith('%'):
            basis = _fb.strip()
        else:
            basis = f"{round(_col_basis(node) / 12 * 100, 4)}%"
        style += f';flex:0 0 {basis};max-width:{basis};box-sizing:border-box;padding:3px'
    elif ctype == 'CardBody':
        style += ';padding:12px'
    elif ctype in ('Card',):
        style += ';page-break-inside:avoid'

    if tag in _VOID:
        return f'<{tag} style="{style}">'
    return f'<{tag} style="{style}">{_children_html(getattr(node, "children", None))}</{tag}>'


def _selenium_html_to_pdf(html: str) -> bytes:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import tempfile, os
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=opts)
    try:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            f.write(html.encode("utf-8"))
            tmp = f.name
        driver.get(f"file://{tmp}")
        pdf = driver.execute_cdp_cmd("Page.printToPDF", {
            'landscape': False, 'displayHeaderFooter': False,
            'printBackground': True,
            # Force A3 portrait explicitly (inches) — don't rely on CSS @page,
            # which silently falls back to A4 if not honoured.
            'preferCSSPageSize': False,
            'paperWidth': 11.69, 'paperHeight': 16.54,
            'marginTop': 0.3, 'marginBottom': 0.3, 'marginLeft': 0.3, 'marginRight': 0.3,
            # Apply the 0.8 down-scale here (Chrome scales the whole print layout
            # uniformly) instead of CSS `zoom`, which printToPDF renders
            # inconsistently — the cause of overlap / horizontal shrink in the PDF.
            'scale': 0.8,
        })
        os.unlink(tmp)
        return base64.b64decode(pdf['data'])
    finally:
        driver.quit()


def _combine_row_png(pngs, figsize=(10, 7), bg="#0A0E27") -> Optional[bytes]:
    """Stitch PNGs side by side into one wide PNG (no PIL needed)."""
    pngs = [p for p in pngs if p]
    if not pngs:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, len(pngs), figsize=figsize, facecolor=bg)
        if len(pngs) == 1:
            axes = [axes]
        for ax, png in zip(axes, pngs):
            ax.imshow(plt.imread(io.BytesIO(png)))
            ax.axis("off")
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=0.02)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, facecolor=fig.get_facecolor(),
                    bbox_inches="tight", pad_inches=0.05)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as exc:
        log.warning("Combine PNG failed: %s", exc)
        return pngs[0] if pngs else None


def _filter_period(events: pd.DataFrame, period: Optional[int]) -> pd.DataFrame:
    """Filter events to one period (1 or 2).  None → full match."""
    if period is None or "period_id" not in events.columns:
        return events
    return events[events["period_id"] == period]


# ---------------------------------------------------------------------------
# Custom PDF class
# ---------------------------------------------------------------------------

_HTML_W = 190   # usable content width in mm (A4 = 210 − 2 × 10 mm margins)


# ---------------------------------------------------------------------------
# HTML Report Builder
# ---------------------------------------------------------------------------

class _HTMLReport:
    """Collects report elements and renders them via Jinja2."""

    _BG_DARK   = (12,  16,  40)
    _GOLD      = (200, 165, 45)
    _TEXT      = (40,  40,  45)
    _SUBTEXT   = (100, 100, 110)
    _HEADER_BG = (245, 245, 250)
    _BORDER    = (235, 235, 240)
    _HOME_CLR  = (30,  80, 180)
    _AWAY_CLR  = (180, 40,  40)

    def __init__(self, home: str, away: str, score: str, competition: str, date: str, venue: str):
        self.context = {
            "home_team": home,
            "away_team": away,
            "score": score,
            "competition": competition,
            "date": date,
            "venue": venue,
            "main_kpis": [],
            "home_subs": [],
            "away_subs": [],
            "custom_sections": [],
            "generated_at": datetime.now().strftime("%d %b %Y %H:%M"),
        }
        self.current_section = None

    def add_page(self):
        # Create a continuation page for the current section only if it has content.
        # Calls immediately before section_title() are no-ops (section has no elements yet).
        if self.current_section is not None and self.current_section["elements"]:
            new_section = {
                "title": self.current_section["title"],
                "elements": [],
                "is_continuation": True,
            }
            self.context["custom_sections"].append(new_section)
            self.current_section = new_section

    def get_y(self) -> float:
        # Mock Y for compatibility; real page breaks are triggered by add_page().
        return 0

    def section_title(self, text: str, color=None):
        self.current_section = {
            "title": text,
            "elements": [],
            "is_continuation": False,
        }
        self.context["custom_sections"].append(self.current_section)

    def sub_title(self, text: str, size: int = 10, color=None):
        if not self.current_section:
            self.section_title("Report Section")
        self.current_section["elements"].append({
            "type": "subtitle",
            "content": text
        })

    def add_image_bytes(self, png: bytes, x: float = 10, w: float = 190) -> None:
        if not png: return
        b64 = base64.b64encode(png).decode('utf-8')
        if not self.current_section:
            self.context["lineup_img_base64"] = b64
        else:
            self.current_section["elements"].append({
                "type": "image_full",
                "content": b64
            })

    def two_images(self, left: bytes, right: bytes, col_w: float = 90, gap: float = 5) -> None:
        if not left and not right: return
        l_b64 = base64.b64encode(left).decode('utf-8') if left else ""
        r_b64 = base64.b64encode(right).decode('utf-8') if right else ""
        self.current_section["elements"].append({
            "type": "image_pair",
            "left": l_b64,
            "right": r_b64
        })

    def draw_substitutions(self, home_subs: list, away_subs: list, home_label: str, away_label: str):
        self.context["home_subs"] = home_subs
        self.context["away_subs"] = away_subs

    def two_team_stats(self, metrics, home_dicts, away_dicts, home_label, away_label, pct_keys=None, label_col_w=55):
        pct_keys = pct_keys or set()
        h_f, h_1, h_2 = home_dicts
        a_f, a_1, a_2 = away_dicts

        _H_BG  = "background:rgba(30,80,180,.10);color:#1E50B4;"
        _H_BG2 = "background:rgba(30,80,180,.05);color:#1E50B4;"
        _A_BG  = "background:rgba(180,40,40,.10);color:#B42828;"
        _A_BG2 = "background:rgba(180,40,40,.05);color:#B42828;"

        rows_html = []
        for label, key in metrics:
            hf = self._fmt_val(h_f.get(key, 0), key, pct_keys)
            h1 = self._fmt_val(h_1.get(key, 0), key, pct_keys)
            h2 = self._fmt_val(h_2.get(key, 0), key, pct_keys)
            af = self._fmt_val(a_f.get(key, 0), key, pct_keys)
            a1 = self._fmt_val(a_1.get(key, 0), key, pct_keys)
            a2 = self._fmt_val(a_2.get(key, 0), key, pct_keys)
            rows_html.append(
                f'<tr>'
                f'<td style="font-weight:600;">{label}</td>'
                f'<td style="text-align:center;color:#1E50B4;font-weight:600;">{hf}</td>'
                f'<td style="text-align:center;color:#1E50B4;">{h1}</td>'
                f'<td style="text-align:center;color:#1E50B4;">{h2}</td>'
                f'<td style="text-align:center;color:#B42828;font-weight:600;">{af}</td>'
                f'<td style="text-align:center;color:#B42828;">{a1}</td>'
                f'<td style="text-align:center;color:#B42828;">{a2}</td>'
                f'</tr>'
            )

        html = (
            '<table class="stats-table">'
            '<thead>'
            f'<tr>'
            f'<th rowspan="2" style="text-align:left;vertical-align:middle;">Metric</th>'
            f'<th colspan="3" style="{_H_BG}text-align:center;">{home_label}</th>'
            f'<th colspan="3" style="{_A_BG}text-align:center;">{away_label}</th>'
            f'</tr>'
            f'<tr>'
            f'<th style="{_H_BG2}text-align:center;">Full</th>'
            f'<th style="{_H_BG2}text-align:center;">H1</th>'
            f'<th style="{_H_BG2}text-align:center;">H2</th>'
            f'<th style="{_A_BG2}text-align:center;">Full</th>'
            f'<th style="{_A_BG2}text-align:center;">H1</th>'
            f'<th style="{_A_BG2}text-align:center;">H2</th>'
            f'</tr>'
            '</thead>'
            f'<tbody>{"".join(rows_html)}</tbody>'
            '</table>'
        )
        self.current_section["elements"].append({"type": "table", "content": html})

    def single_team_stats(self, metrics, full, h1, h2, pct_keys=None, label_col_w=70):
        pct_keys = pct_keys or set()
        rows_html = []
        for label, key in metrics:
            rows_html.append(
                f'<tr>'
                f'<td style="font-weight:600;">{label}</td>'
                f'<td style="text-align:center;">{self._fmt_val(full.get(key, 0), key, pct_keys)}</td>'
                f'<td style="text-align:center;">{self._fmt_val(h1.get(key, 0), key, pct_keys)}</td>'
                f'<td style="text-align:center;">{self._fmt_val(h2.get(key, 0), key, pct_keys)}</td>'
                f'</tr>'
            )
        html = (
            '<table>'
            '<thead><tr>'
            '<th style="text-align:left;">Metric</th>'
            '<th style="text-align:center;">Full</th>'
            '<th style="text-align:center;">H1</th>'
            '<th style="text-align:center;">H2</th>'
            '</tr></thead>'
            f'<tbody>{"".join(rows_html)}</tbody>'
            '</table>'
        )
        self.current_section["elements"].append({"type": "table", "content": html})

    def data_table(self, df: pd.DataFrame, col_widths: list[float], align: list[str] = None) -> None:
        if df is None or df.empty: return
        html = df.to_html(index=False, classes="stats-table", border=0)
        self.current_section["elements"].append({"type": "table", "content": html})

    def _fmt_val(self, val, key: str, pct_keys: set) -> str:
        v = val if val is not None else 0
        if key in pct_keys:
            return f"{float(v):.1f}%"
        try:
            return str(int(v))
        except (TypeError, ValueError):
            return str(v)

    def set_cover_kpis(self, rows):
        """Specifically for the cover page visual bars."""
        for label, h_val, a_val, suffix in rows:
            hv = float(h_val) if h_val is not None else 0
            av = float(a_val) if a_val is not None else 0
            max_val = max(hv, av, 1)
            
            self.context["main_kpis"].append({
                "label": label,
                "home_display": f"{hv:.1f}{suffix}" if suffix else f"{int(hv)}",
                "away_display": f"{av:.1f}{suffix}" if suffix else f"{int(av)}",
                "home_pct": (hv / max_val) * 100 * 0.5, # Bar is split 50/50
                "away_pct": (av / max_val) * 100 * 0.5,
            })

    def output_bytes(self) -> bytes:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader("assets/templates"))
        template = env.get_template("match_report.html")
        html_content = template.render(self.context)
        
        # Convert HTML to PDF using Selenium
        return self._html_to_pdf_selenium(html_content)

    def _html_to_pdf_selenium(self, html: str) -> bytes:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        import tempfile
        import os

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        
        driver = webdriver.Chrome(options=chrome_options)
        try:
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
                f.write(html.encode("utf-8"))
                temp_path = f.name
            
            driver.get(f"file://{temp_path}")
            
            # Use Chrome DevTools Protocol to print to PDF
            print_options = {
                'landscape': False,
                'displayHeaderFooter': False,
                'printBackground': True,
                # Force A3 portrait explicitly (inches) — never fall back to A4.
                'preferCSSPageSize': False,
                'paperWidth': 11.69, 'paperHeight': 16.54,
            }
            pdf_data = driver.execute_cdp_cmd("Page.printToPDF", print_options)
            
            os.unlink(temp_path)
            return base64.b64decode(pdf_data['data'])
        finally:
            driver.quit()



# ---------------------------------------------------------------------------
# Dash component tree → figures extractor
# ---------------------------------------------------------------------------

def _figures_from_component(component):
    """
    Recursively walk a Dash component tree.
    Yields go.Figure instances (from dcc.Graph) or raw PNG bytes (from html.Img
    with a data-URI source).
    """
    if component is None:
        return

    ctype = type(component).__name__

    if ctype == "Graph":
        fig = getattr(component, "figure", None)
        if fig is not None:
            yield fig
        return

    if ctype == "Img":
        src = getattr(component, "src", None) or ""
        if "data:image/png;base64," in src:
            try:
                yield base64.b64decode(src.split("data:image/png;base64,")[1])
            except Exception:
                pass
        return

    children = getattr(component, "children", None)
    if children is None:
        return
    if isinstance(children, (list, tuple)):
        for child in children:
            if child is not None and not isinstance(child, (str, int, float, bool)):
                yield from _figures_from_component(child)
    elif not isinstance(children, (str, int, float, bool)):
        yield from _figures_from_component(children)


def _tab_figures_to_pdf(
    pdf: _HTMLReport,
    build_fn,
    events: pd.DataFrame,
    fig_w: int = 860,
    fig_h: int = 480,
) -> None:
    """
    Call build_fn(events), extract all figures / base64 images from the returned
    Dash component tree, convert to PNG and embed as side-by-side pairs.
    """
    tab = build_fn(events)
    pending: Optional[bytes] = None
    for item in _figures_from_component(tab):
        png = item if isinstance(item, bytes) else _plotly_to_png(item, w=fig_w, h=fig_h)
        if png is None:
            continue
        if pending is None:
            pending = png
        else:
            pdf.two_images(pending, png)
            pending = None
    if pending is not None:
        pdf.add_image_bytes(pending)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


_REPORT_SHELL = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: A3; margin: 10mm; }}
body {{ margin: 0; background: #fff; color: #222;
        font-family: Arial, Helvetica, sans-serif; font-size: 11px; }}
img {{ max-width: 100%; }}
table {{ border-collapse: collapse; }}
.rep-divider {{ color: #9A7D00; font-weight: 800; font-size: 15px;
    text-transform: uppercase; letter-spacing: 1px; border-bottom: 2px solid #EDBB00;
    margin: 18px 0 12px; padding-bottom: 6px; text-align: center;
    page-break-after: avoid; break-after: avoid; }}
.rep-first {{ }}
.rep-banner {{ display: flex; align-items: center; justify-content: center;
    gap: 28px; padding: 4px 0 2px; }}
.rep-team {{ display: flex; align-items: center; gap: 10px; font-size: 18px; font-weight: 800; }}
.rep-score {{ font-size: 34px; font-weight: 900; color: #C8A52D; letter-spacing: 2px; }}
.rep-meta {{ text-align: center; color: #666; margin-bottom: 6px; font-size: 11px; }}
.rep-sub {{ font-weight: 700; color: #9A7D00; font-size: 11px; margin-bottom: 4px;
    text-transform: uppercase; text-align: center; }}
</style></head><body>{body}</body></html>"""


def _img_tag(png: bytes, style: str = "width:100%") -> str:
    if not png:
        return ""
    return ('<img style="%s;page-break-inside:avoid" src="data:image/png;base64,%s">'
            % (style, base64.b64encode(png).decode()))


def generate_match_report_pdf(match_id) -> bytes:
    """
    Full match report PDF — a faithful, non-screenshot mirror of
    pages/match_report.py. Every section is built with the SAME public
    build_*_tab(events) functions used by the live app, then its Dash component
    tree is converted to static HTML (real Plotly figures via kaleido, real
    tables, the same dbc column layout) and printed to PDF. Light page, app
    layout & content, one section per page-break — spans as many pages as needed.
    """
    from utils.data_utils import get_match_events
    from utils.match_data_adapter import get_match_metadata, compute_team_kpis
    from utils.logos import get_team_logo_path
    from pages.match_report import (
        build_overview_tab,
        build_attacking_output_tab,
        build_build_up_passing_tab,
        build_defensive_structure_tab,
        build_transitions_counterpressing_tab,
        build_goalkeeping_tab,
        build_player_stats_tab,
        build_attack_radar,
        build_def_radar,
        build_bup_radar,
    )

    events = get_match_events(match_id)
    if events.empty:
        raise ValueError(f"No events found for match_id={match_id}")

    meta        = get_match_metadata(events)
    home_team   = meta.get("home_team", "Home")
    away_team   = meta.get("away_team", "Away")
    competition = meta.get("competition", "")
    raw_date    = str(meta.get("date", "") or "")[:10]
    venue       = str(meta.get("venue", "") or "")
    try:
        date_str = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        date_str = raw_date
    home_kpis = compute_team_kpis(events, "home")
    away_kpis = compute_team_kpis(events, "away")
    score     = f"{home_kpis['goals']} - {away_kpis['goals']}"

    def _logo_b64(team):
        try:
            p = get_team_logo_path(team)             # 'assets/logos/team/xxx.svg'
            if p:
                with open(p.lstrip('/'), "rb") as f:
                    return base64.b64encode(f.read()).decode()
        except Exception:
            pass
        return ""

    h_logo, a_logo = _logo_b64(home_team), _logo_b64(away_team)
    h_img = f'<img src="data:image/svg+xml;base64,{h_logo}" style="height:48px">' if h_logo else ''
    a_img = f'<img src="data:image/svg+xml;base64,{a_logo}" style="height:48px">' if a_logo else ''

    parts = [
        f'<div class="rep-banner"><div class="rep-team">{h_img}<span>{_escape(home_team)}</span></div>'
        f'<div class="rep-score">{_escape(score)}</div>'
        f'<div class="rep-team"><span>{_escape(away_team)}</span>{a_img}</div></div>',
        f'<div class="rep-meta">{_escape(competition)} &middot; {_escape(date_str)}'
        + (f' &middot; {_escape(venue)}' if venue else '') + '</div>',
    ]

    def _divider(title, first=False):
        cls = "rep-divider rep-first" if first else "rep-divider"
        return f'<div class="{cls}">{_escape(title)}</div>'

    def _radars_html():
        cols = []
        for label, fn in (("Attack", build_attack_radar),
                          ("Defence", build_def_radar),
                          ("Possession & Build-Up", build_bup_radar)):
            try:
                fig = _get_figure(fn(events))
                body = _img_tag(_render_fig_png(fig)) if fig is not None else "No data"
            except Exception as exc:
                log.warning("radar %s: %s", label, exc)
                body = "No data"
            sub = '<div class="rep-sub">%s</div>' % label
            cols.append('<div style="flex:0 0 33.33%;max-width:33.33%;box-sizing:border-box;'
                        'padding:6px">' + sub + body + '</div>')
        return '<div style="display:flex;flex-wrap:wrap">' + ''.join(cols) + '</div>'

    # Section order mirrors the live page (radars sit between Overview and Attack)
    _SECTIONS = [
        ("Overview",                        build_overview_tab),
        ("Attack",                          build_attacking_output_tab),
        ("Build-Up & Passing",              build_build_up_passing_tab),
        ("Defense",                         build_defensive_structure_tab),
        ("Transitions & Counterpressing",   build_transitions_counterpressing_tab),
        ("Goalkeeping",                     build_goalkeeping_tab),
        ("Player Stats",                    build_player_stats_tab),
    ]

    for i, (title, fn) in enumerate(_SECTIONS):
        if title == "Attack":
            parts.append(_divider("Performance Radars"))
            parts.append(_radars_html())
        parts.append(_divider(title, first=(i == 0)))
        try:
            parts.append(_dash_to_html(fn(events)))
        except Exception as exc:
            log.warning("section %s: %s", title, exc)
            parts.append(f'<p style="color:#c00">Error rendering {_escape(title)}: {_escape(str(exc))}</p>')

    html = _REPORT_SHELL.format(body="".join(parts))
    # Write the HTML artifact first, then render the PDF from that same HTML.
    try:
        out_dir = Path("logs")
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"match_report_{match_id}.html").write_text(html, encoding="utf-8")
    except Exception as exc:
        log.warning("write html: %s", exc)
    return _selenium_html_to_pdf(html)
