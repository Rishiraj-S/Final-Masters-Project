"""
pdf_report.py
=============
Server-side match report PDF generator.

Produces a multi-section A4 PDF covering every match analysis tab with
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

def _plotly_to_png(fig, w: int = 900, h: int = 480) -> Optional[bytes]:
    """Convert a Plotly figure to PNG bytes using kaleido."""
    try:
        import plotly.io as pio
        return pio.to_image(fig, format="png", width=w, height=h)
    except Exception as exc:
        log.warning("Plotly → PNG failed: %s", exc)
        return None


def _get_figure(result):
    """Accept either a go.Figure or a dcc.Graph and return the go.Figure."""
    if result is None:
        return None
    return result.figure if hasattr(result, "figure") else result


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
                'preferCSSPageSize': True,
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

def generate_match_report_pdf(match_id) -> bytes:
    """
    Generate a complete PDF match report for *match_id*.

    Structure mirrors pages/match_report.py exactly — one section per tab,
    using the same public build_*_tab(events) functions.
    """
    from utils.data_utils import get_match_events, get_match_lineup
    from utils.match_data_adapter import get_match_metadata, compute_team_kpis, get_substitutions
    from utils.logos import TEAM_LOGOS
    from page_utils.visualizations import HOME_COLOR, AWAY_COLOR
    from pages.match_analysis_tabs import (
        build_attacking_output_tab,
        build_build_up_passing_tab,
        build_defensive_structure_tab,
        build_transitions_counterpressing_tab,
        build_goalkeeping_tab,
        build_player_stats_tab,
    )
    from pages.match_analysis_tabs.overview import _generate_team_lineup_image

    # ── Load data ──────────────────────────────────────────────────────
    events = get_match_events(match_id)
    if events.empty:
        raise ValueError(f"No events found for match_id={match_id}")

    meta        = get_match_metadata(events)
    lineup_df   = get_match_lineup(match_id)
    home_team   = meta.get("home_team", "Home")
    away_team   = meta.get("away_team", "Away")
    competition = meta.get("competition", "")
    raw_date    = str(meta.get("date", "") or "")[:10]
    venue       = str(meta.get("venue", "") or "")

    try:
        formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        formatted_date = raw_date

    home_kpis = compute_team_kpis(events, "home")
    away_kpis = compute_team_kpis(events, "away")
    score     = f"{home_kpis['goals']} - {away_kpis['goals']}"
    h1_events = _filter_period(events, 1)
    h2_events = _filter_period(events, 2)

    # ── Create HTML Report object ──────────────────────────────────────
    pdf = _HTMLReport(home_team, away_team, score, competition, formatted_date, venue)

    for pos, team in [("home", home_team), ("away", away_team)]:
        logo_fn = TEAM_LOGOS.get(team)
        if not logo_fn and "barcelona" in team.lower():
            logo_fn = "FC-Barcelona-v2002.svg"
        logo_path = Path(f"assets/logos/team/{logo_fn}") if logo_fn else None
        if logo_path and logo_path.exists():
            with open(logo_path, "rb") as f:
                pdf.context[f"{pos}_logo_base64"] = base64.b64encode(f.read()).decode("utf-8")

    pdf.set_cover_kpis([
        ("Possession",      home_kpis.get("possession", 50),       away_kpis.get("possession", 50),     "%"),
        ("Shots",           home_kpis.get("shots", 0),             away_kpis.get("shots", 0),           ""),
        ("Shots on Target", home_kpis.get("shots_on_target", 0),   away_kpis.get("shots_on_target", 0), ""),
        ("Passes",          home_kpis.get("passes", 0),            away_kpis.get("passes", 0),          ""),
        ("Pass Accuracy",   home_kpis.get("pass_accuracy", 0),     away_kpis.get("pass_accuracy", 0),   "%"),
        ("Fouls",           home_kpis.get("fouls", 0),             away_kpis.get("fouls", 0),           ""),
        ("Corners",         home_kpis.get("corners", 0),           away_kpis.get("corners", 0),         ""),
        ("Yellow Cards",    home_kpis.get("yellow_cards", 0),      away_kpis.get("yellow_cards", 0),    ""),
        ("Red Cards",       home_kpis.get("red_cards", 0),         away_kpis.get("red_cards", 0),       ""),
    ])

    # ══════════════════════════════════════════════════════════════════
    # SECTION 1 — OVERVIEW  (same as tab-overview in match_report.py)
    # ══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("1. Overview")

    if lineup_df is not None and not lineup_df.empty:
        pdf.sub_title("Starting XI")
        try:
            home_start = lineup_df[(lineup_df["team_position"] == "home") & (lineup_df["role"] == "Start")].copy()
            away_start = lineup_df[(lineup_df["team_position"] == "away") & (lineup_df["role"] == "Start")].copy()
            h_fmt = home_start["formation"].iloc[0] if not home_start.empty else ""
            a_fmt = away_start["formation"].iloc[0] if not away_start.empty else ""
            h_b64 = _generate_team_lineup_image(home_start, h_fmt, HOME_COLOR)
            a_b64 = _generate_team_lineup_image(away_start, a_fmt, AWAY_COLOR)
            h_png = base64.b64decode(h_b64) if h_b64 else None
            a_png = base64.b64decode(a_b64) if a_b64 else None
            if h_png and a_png:
                pdf.two_images(h_png, a_png)
            elif h_png:
                pdf.add_image_bytes(h_png)
            elif a_png:
                pdf.add_image_bytes(a_png)
        except Exception as exc:
            log.warning("Lineup: %s", exc)

    try:
        subs = get_substitutions(events)
        pdf.draw_substitutions(subs.get("home", []), subs.get("away", []), home_team, away_team)
    except Exception as exc:
        log.warning("Substitutions: %s", exc)

    pdf.sub_title("Match Statistics")
    try:
        h_h1_k = compute_team_kpis(h1_events, "home") if not h1_events.empty else {}
        h_h2_k = compute_team_kpis(h2_events, "home") if not h2_events.empty else {}
        a_h1_k = compute_team_kpis(h1_events, "away") if not h1_events.empty else {}
        a_h2_k = compute_team_kpis(h2_events, "away") if not h2_events.empty else {}
        pdf.two_team_stats(
            metrics=[
                ("Shots",           "shots"),
                ("Shots on Target", "shots_on_target"),
                ("Passes",          "passes"),
                ("Pass Accuracy",   "pass_accuracy"),
                ("Possession",      "possession"),
                ("Fouls",           "fouls"),
                ("Corners",         "corners"),
                ("Yellow Cards",    "yellow_cards"),
                ("Red Cards",       "red_cards"),
            ],
            home_dicts=(home_kpis, h_h1_k, h_h2_k),
            away_dicts=(away_kpis, a_h1_k, a_h2_k),
            home_label=home_team,
            away_label=away_team,
            pct_keys={"pass_accuracy", "possession"},
        )
    except Exception as exc:
        log.warning("Match stats: %s", exc)

    # ══════════════════════════════════════════════════════════════════
    # SECTIONS 2-7 — one per tab in match_report.py
    # Each calls the same public build_*_tab(events) function,
    # then walks the returned Dash component tree to extract figures.
    # ══════════════════════════════════════════════════════════════════
    _TAB_SECTIONS = [
        ("2. Attack",                        build_attacking_output_tab),
        ("3. Build-Up & Passing",            build_build_up_passing_tab),
        ("4. Defense",                       build_defensive_structure_tab),
        ("5. Transitions & Counterpressing", build_transitions_counterpressing_tab),
        ("6. Goalkeeping",                   build_goalkeeping_tab),
        ("7. Player Stats",                  build_player_stats_tab),
    ]

    for section_title, build_fn in _TAB_SECTIONS:
        pdf.add_page()
        pdf.section_title(section_title)
        try:
            _tab_figures_to_pdf(pdf, build_fn, events)
        except Exception as exc:
            log.warning("%s: %s", section_title, exc)

    return pdf.output_bytes()
