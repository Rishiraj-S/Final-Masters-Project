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

        rows = []
        for label, key in metrics:
            hv = h_f.get(key, 0)
            av = a_f.get(key, 0)
            h1 = h_1.get(key, 0)
            a1 = a_1.get(key, 0)
            h2 = h_2.get(key, 0)
            a2 = a_2.get(key, 0)
            
            rows.append({
                "label": label,
                "hf": self._fmt_val(hv, key, pct_keys),
                "h1": self._fmt_val(h1, key, pct_keys),
                "h2": self._fmt_val(h2, key, pct_keys),
                "af": self._fmt_val(av, key, pct_keys),
                "a1": self._fmt_val(a1, key, pct_keys),
                "a2": self._fmt_val(a2, key, pct_keys),
            })
        df = pd.DataFrame(rows)
        # Convert to HTML table
        html = df.to_html(index=False, classes="stats-table")
        self.current_section["elements"].append({
            "type": "table",
            "content": html
        })

    def single_team_stats(self, metrics, full, h1, h2, pct_keys=None, label_col_w=70):
        pct_keys = pct_keys or set()
        rows = []
        for label, key in metrics:
            rows.append({
                "Metric": label,
                "Full": self._fmt_val(full.get(key, 0), key, pct_keys),
                "1H": self._fmt_val(h1.get(key, 0), key, pct_keys),
                "2H": self._fmt_val(h2.get(key, 0), key, pct_keys),
            })
        html = pd.DataFrame(rows).to_html(index=False)
        self.current_section["elements"].append({"type": "table", "content": html})

    def data_table(self, df: pd.DataFrame, col_widths: list[float], align: list[str] = None) -> None:
        if df is None or df.empty: return
        html = df.to_html(index=False)
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
# Reusable: render (Full / 1st / 2nd) figure pair into PDF
# ---------------------------------------------------------------------------

_PERIODS = [
    ("Full Match", None),
    ("1st Half",   1),
    ("2nd Half",   2),
]


def _add_period_figs(
    pdf: _HTMLReport,
    events: pd.DataFrame,
    build_fn,          # callable(ev_p) -> (left_png | None, right_png | None)
    label: str,
) -> None:
    """Call build_fn for each period; embed the resulting images."""
    for period_label, period in _PERIODS:
        ev_p = _filter_period(events, period)
        if ev_p.empty:
            continue
        try:
            left_png, right_png = build_fn(ev_p)
        except Exception as exc:
            log.warning("%s (%s): %s", label, period_label, exc)
            continue

        if left_png is None and right_png is None:
            continue

        # Ensure subtitle + content fit — move to new page if near bottom
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.sub_title(f"{label} - {period_label}")
        if left_png and right_png:
            pdf.two_images(left_png, right_png)
        elif left_png:
            pdf.add_image_bytes(left_png, w=90)
        else:
            pdf.add_image_bytes(right_png, w=90)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_match_report_pdf(match_id) -> bytes:
    """
    Generate a complete PDF match report for *match_id*.
    Returns raw PDF bytes for ``dcc.send_bytes``.
    Raises ``ValueError`` when no event data is available.
    """
    # --- lazy imports (heavy / cross-package deps) ----------------------
    # --- lazy imports (heavy / cross-package deps) ----------------------
    from utils.data_utils import get_match_events, get_match_lineup
    from utils.match_data_adapter import get_match_metadata, compute_team_kpis, get_substitutions
    from utils.logos import TEAM_LOGOS
    from pages.match_analysis_tabs.shared import HOME_COLOR, AWAY_COLOR, render_lsc_heatmap_img
    from pages.match_analysis_tabs.overview import (
        _generate_lineup_pitch_image,
        _compute_avg_positions,
        _build_avg_pos_fig,
    )
    from pages.match_analysis_tabs.attacking_output import (
        _compute            as _atk_compute,
        _shot_map_fig       as _atk_shot_map,
        _compute_team_stats as _atk_team_stats,
    )
    from pages.match_analysis_tabs.build_up_passing import (
        _compute            as _bup_compute,
        _network_fig        as _bup_net_fig,
        _entries_fig        as _bup_entries_fig,
        _compute_half_stats as _bup_half,
    )
    from pages.match_analysis_tabs.defensive_structure import (
        _compute            as _def_compute,
        _def_action_map     as _def_map_fn,
        _fouls_offsides_map as _def_fouls_fn,
        _compute_half_stats as _def_half,
    )
    from pages.match_analysis_tabs.transitions_counterpressing import (
        _compute            as _trans_compute,
        _counterpress_map   as _cp_map_fn,
        _compute_half_stats as _trans_half,
    )
    from pages.match_analysis_tabs.goalkeeping import (
        _compute            as _gk_compute,
        _half_stats         as _gk_half_stats,
        _goal_mouth_viz     as _gk_mouth_fn,
        _shot_map_fig       as _gk_shot_map_fn,
        _team_shots         as _gk_team_shots,
    )
    from pages.match_analysis_tabs.player_stats import _build_all_player_stats

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

    # ── Create HTML Report object ─────────────────────────────────────
    pdf = _HTMLReport(home_team, away_team, score, competition, formatted_date, venue)

    # Load Home Logo
    home_logo_fn = TEAM_LOGOS.get(home_team)
    if not home_logo_fn and 'barcelona' in home_team.lower():
        home_logo_fn = 'FC-Barcelona-v2002.svg'
    home_logo_path = Path(f"assets/logos/team/{home_logo_fn}") if home_logo_fn else None
    if home_logo_path and home_logo_path.exists():
        with open(home_logo_path, "rb") as f:
            pdf.context["home_logo_base64"] = base64.b64encode(f.read()).decode("utf-8")

    # Load Away Logo
    away_logo_fn = TEAM_LOGOS.get(away_team)
    if not away_logo_fn and 'barcelona' in away_team.lower():
        away_logo_fn = 'FC-Barcelona-v2002.svg'
    away_logo_path = Path(f"assets/logos/team/{away_logo_fn}") if away_logo_fn else None
    if away_logo_path and away_logo_path.exists():
        with open(away_logo_path, "rb") as f:
            pdf.context["away_logo_base64"] = base64.b64encode(f.read()).decode("utf-8")

    # KPI STAT BARS (Inspired by TV-style comparison bars)
    _kpi_rows = [
        ("Possession",      home_kpis.get("possession", 50),       away_kpis.get("possession", 50), "%"),
        ("Shots",           home_kpis.get("shots", 0),             away_kpis.get("shots", 0), ""),
        ("Shots on Target", home_kpis.get("shots_on_target", 0),   away_kpis.get("shots_on_target", 0), ""),
        ("Assists",         home_kpis.get("assists", 0),           away_kpis.get("assists", 0), ""),
        ("Blocked Shots",   home_kpis.get("blocked_shots", 0),     away_kpis.get("blocked_shots", 0), ""),
        ("Passes",          home_kpis.get("passes", 0),            away_kpis.get("passes", 0), ""),
        ("Pass Accuracy",   home_kpis.get("pass_accuracy", 0),     away_kpis.get("pass_accuracy", 0), "%"),
        ("Fouls Committed", home_kpis.get("fouls", 0),             away_kpis.get("fouls", 0), ""),
        ("Corners",         home_kpis.get("corners", 0),           away_kpis.get("corners", 0), ""),
        ("Offsides",        home_kpis.get("offsides", 0),          away_kpis.get("offsides", 0), ""),
        ("Interceptions",   home_kpis.get("interceptions", 0),     away_kpis.get("interceptions", 0), ""),
        ("Yellow Cards",    home_kpis.get("yellow_cards", 0),      away_kpis.get("yellow_cards", 0), ""),
        ("Red Cards",       home_kpis.get("red_cards", 0),         away_kpis.get("red_cards", 0), ""),
    ]
    pdf.set_cover_kpis(_kpi_rows)

    # ══════════════════════════════════════════════════════════════════
    # SECTION 1 – OVERVIEW
    # ══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("1. Overview")

    # 1a  Lineup pitch (static)
    if lineup_df is not None and not lineup_df.empty:
        pdf.sub_title("Starting XI")
        try:
            b64 = _generate_lineup_pitch_image(
                lineup_df, home_team, away_team, HOME_COLOR, AWAY_COLOR
            )
            if b64:
                pdf.add_image_bytes(base64.b64decode(b64), w=_HTML_W)
        except Exception as exc:
            log.warning("Lineup pitch: %s", exc)

    # 1b Substitutions
    try:
        subs = get_substitutions(events)
        pdf.draw_substitutions(subs.get("home", []), subs.get("away", []), home_team, away_team)
    except Exception as exc:
        log.warning("Substitutions block: %s", exc)

    # 1c  Average Positions  (Full / 1st / 2nd)
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.sub_title("Average Positions")
    for period_label, period in _PERIODS:
        ev_p = _filter_period(events, period)
        if ev_p.empty:
            continue
            
        for subs_flag, subs_label in [(False, "Starters"), (True, "With Subs")]:
            h_png = a_png = None
            try:
                hp = _compute_avg_positions(ev_p, lineup_df, "home", include_subs=subs_flag)
                if hp:
                    h_png = _plotly_to_png(
                        _build_avg_pos_fig(hp, HOME_COLOR, home_team, True), w=440, h=540
                    )
            except Exception as exc:
                log.warning("Avg pos home %s %s: %s", period_label, subs_label, exc)
            try:
                ap = _compute_avg_positions(ev_p, lineup_df, "away", include_subs=subs_flag)
                if ap:
                    a_png = _plotly_to_png(
                        _build_avg_pos_fig(ap, AWAY_COLOR, away_team, False), w=440, h=540
                    )
            except Exception as exc:
                log.warning("Avg pos away %s %s: %s", period_label, subs_label, exc)

            if h_png or a_png:
                if pdf.get_y() > 240:
                    pdf.add_page()
                pdf.sub_title(f"Avg. Positions ({subs_label}) - {period_label}", size=8)
                if h_png and a_png:
                    pdf.two_images(h_png, a_png)
                elif h_png:
                    pdf.add_image_bytes(h_png, w=90)
                else:
                    pdf.add_image_bytes(a_png, w=90)

    # 1c  Match Stats table  (Full / H1 / H2)
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.sub_title("Match Statistics")
    try:
        _kpi_meta = compute_team_kpis
        h_h1_k = _kpi_meta(h1_events, "home") if not h1_events.empty else {}
        h_h2_k = _kpi_meta(h2_events, "home") if not h2_events.empty else {}
        a_h1_k = _kpi_meta(h1_events, "away") if not h1_events.empty else {}
        a_h2_k = _kpi_meta(h2_events, "away") if not h2_events.empty else {}
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
        log.warning("Match stats table: %s", exc)

    # ══════════════════════════════════════════════════════════════════
    # SECTION 2 – ATTACK
    # ══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("2. Attack")

    try:
        def _atk_maps(ev_p: pd.DataFrame):
            atk_p = _atk_compute(ev_p)
            hs_p, as_p = atk_p["home"], atk_p["away"]
            h_png = _plotly_to_png(_atk_shot_map(
                hs_p["shots"], hs_p.get("key_passes", pd.DataFrame()), HOME_COLOR, hs_p["team"]
            ), w=440, h=540)
            a_png = _plotly_to_png(_atk_shot_map(
                as_p["shots"], as_p.get("key_passes", pd.DataFrame()), AWAY_COLOR, as_p["team"]
            ), w=440, h=540)
            return h_png, a_png

        _add_period_figs(pdf, events, _atk_maps, "Shot Maps")

        atk = _atk_compute(events)
        hs, as_ = atk["home"], atk["away"]

        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.sub_title("Top Performers (Shooting)")
        
        pdf.sub_title(hs["team"])
        pdf.data_table(hs["top_shooters"], col_widths=[40, 15, 15, 15], align=["L", "C", "C", "C"])
        
        pdf.sub_title(as_["team"])
        pdf.data_table(as_["top_shooters"], col_widths=[40, 15, 15, 15], align=["L", "C", "C", "C"])

        # Shooting stats
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.sub_title("Shooting Stats")
        hf_s, hh1_s, hh2_s = _atk_team_stats(events, "home")
        af_s, ah1_s, ah2_s = _atk_team_stats(events, "away")
        pdf.two_team_stats(
            metrics=[
                ("Total Shots",     "shots"),
                ("Shots on Target", "on_target"),
                ("Goals",           "goals"),
                ("Shots from Box",  "from_box"),
            ],
            home_dicts=(hf_s, hh1_s, hh2_s),
            away_dicts=(af_s, ah1_s, ah2_s),
            home_label=home_team,
            away_label=away_team,
        )
    except Exception as exc:
        log.warning("Attack section: %s", exc)

    # ══════════════════════════════════════════════════════════════════
    # SECTION 3 – BUILD-UP & PASSING
    # ══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("3. Build-Up & Passing")

    def _bup_nets(ev_p: pd.DataFrame):
        d = _bup_compute(ev_p)
        pngs = []
        for pos, color, is_h in [("home", HOME_COLOR, True),
                                   ("away", AWAY_COLOR, False)]:
            nodes, edges = d[pos]["nodes"], d[pos]["edges"]
            if isinstance(nodes, pd.DataFrame) and not nodes.empty:
                pngs.append(_plotly_to_png(
                    _bup_net_fig(nodes, edges, color, is_home=is_h), w=440, h=400
                ))
            else:
                pngs.append(None)
        return (pngs[0], pngs[1]) if len(pngs) == 2 else (None, None)

    _add_period_figs(pdf, events, _bup_nets, "Pass Networks")

    def _bup_entries_ft(ev_p: pd.DataFrame):
        d = _bup_compute(ev_p)
        pngs = []
        for pos, color, is_h in [("home", HOME_COLOR, True), ("away", AWAY_COLOR, False)]:
            entries = d[pos]["entries_ft"]
            if isinstance(entries, pd.DataFrame) and not entries.empty:
                pngs.append(_plotly_to_png(
                    _bup_entries_fig(entries, "final_third", color, is_home=is_h), w=440, h=540
                ))
            else:
                pngs.append(None)
        return (pngs[0], pngs[1]) if len(pngs) == 2 else (None, None)

    _add_period_figs(pdf, events, _bup_entries_ft, "Entries into Final Third")

    def _bup_entries_z14(ev_p: pd.DataFrame):
        d = _bup_compute(ev_p)
        pngs = []
        for pos, color, is_h in [("home", HOME_COLOR, True), ("away", AWAY_COLOR, False)]:
            entries = d[pos]["entries_z14"]
            if isinstance(entries, pd.DataFrame) and not entries.empty:
                pngs.append(_plotly_to_png(
                    _bup_entries_fig(entries, "zone14", color, is_home=is_h), w=440, h=540
                ))
            else:
                pngs.append(None)
        return (pngs[0], pngs[1]) if len(pngs) == 2 else (None, None)

    _add_period_figs(pdf, events, _bup_entries_z14, "Entries into Zone 14")

    # Pass / Carry / Dribble stats table
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.sub_title("Pass / Carry / Dribble Stats")
    try:
        _bup_metrics = [
            ("Passes",           "passes"),
            ("Pass Accuracy",    "pass_acc"),
            ("Long Balls",       "long_balls"),
            ("Crosses",          "crosses"),
            ("Through Balls",    "thru_balls"),
            ("Into Final Third", "into_ft"),
            ("Carries",          "carries"),
            ("Dribbles",         "dribbles"),
            ("Dribble Acc.",     "drib_acc"),
        ]
        pdf.two_team_stats(
            metrics=_bup_metrics,
            home_dicts=(
                _bup_half(events,    "home"),
                _bup_half(events,    "home", period=1),
                _bup_half(events,    "home", period=2),
            ),
            away_dicts=(
                _bup_half(events,    "away"),
                _bup_half(events,    "away", period=1),
                _bup_half(events,    "away", period=2),
            ),
            home_label=home_team,
            away_label=away_team,
            pct_keys={"pass_acc", "drib_acc"},
        )

        bup = _bup_compute(events)
        
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.sub_title("Top Passing Combinations")
        pdf.sub_title(home_team)
        pdf.data_table(bup["home"]["combos"], col_widths=[50, 15, 15, 15], align=["L", "C", "C", "C"])
        pdf.sub_title(away_team)
        pdf.data_table(bup["away"]["combos"], col_widths=[50, 15, 15, 15], align=["L", "C", "C", "C"])

        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.sub_title("Top 3-Player Passing Combinations")
        pdf.sub_title(home_team)
        pdf.data_table(bup["home"]["combos3"], col_widths=[60, 15, 15, 15], align=["L", "C", "C", "C"])
        pdf.sub_title(away_team)
        pdf.data_table(bup["away"]["combos3"], col_widths=[60, 15, 15, 15], align=["L", "C", "C", "C"])

        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.sub_title("Player Dribbling Stats")
        pdf.sub_title(home_team)
        pdf.data_table(bup["home"]["player_drib_stats"], col_widths=[40, 15, 15, 15], align=["L", "C", "C", "C"])
        pdf.sub_title(away_team)
        pdf.data_table(bup["away"]["player_drib_stats"], col_widths=[40, 15, 15, 15], align=["L", "C", "C", "C"])

        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.sub_title("Player Possession / Touches")
        pdf.sub_title(home_team)
        pdf.data_table(bup["home"]["player_poss_df"], col_widths=[35, 10, 10, 10, 10, 10, 10], align=["L", "C", "C", "C", "C", "C", "C"])
        pdf.sub_title(away_team)
        pdf.data_table(bup["away"]["player_poss_df"], col_widths=[35, 10, 10, 10, 10, 10, 10], align=["L", "C", "C", "C", "C", "C", "C"])

    except Exception as exc:
        log.warning("Build-up stats table: %s", exc)

    # ══════════════════════════════════════════════════════════════════
    # SECTION 4 – DEFENSE
    # ══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("4. Defense")

    def _def_maps(ev_p: pd.DataFrame):
        d = _def_compute(ev_p)
        h_png = _plotly_to_png(
            _get_figure(_def_map_fn(d["home"]["def_events_df"], HOME_COLOR)), w=860, h=480
        )
        a_png = _plotly_to_png(
            _get_figure(_def_map_fn(d["away"]["def_events_df"], AWAY_COLOR)), w=860, h=480
        )
        return h_png, a_png

    _add_period_figs(pdf, events, _def_maps, "Defensive Action Maps")

    def _def_heatmaps(ev_p: pd.DataFrame):
        d = _def_compute(ev_p)
        pngs = []
        for pos, color, is_h in [("home", HOME_COLOR, True), ("away", AWAY_COLOR, False)]:
            hx = d[pos]["heatmap_x"]
            hy = d[pos]["heatmap_y"]
            if hx and hy and len(hx) > 1:
                b64 = render_lsc_heatmap_img(hx, hy, color, show_zone_pcts=True)
                raw = base64.b64decode(b64.split(",")[1])
                pngs.append(raw)
            else:
                pngs.append(None)
        return (pngs[0], pngs[1]) if len(pngs) == 2 else (None, None)

    _add_period_figs(pdf, events, _def_heatmaps, "Defensive Action Heatmaps")

    def _def_fouls(ev_p: pd.DataFrame):
        d = _def_compute(ev_p)
        pngs = []
        for pos, color, is_h in [("home", HOME_COLOR, True), ("away", AWAY_COLOR, False)]:
            fouls = d[pos]["fouls_df"]
            offs  = d[pos]["offsides_df"]
            pngs.append(_plotly_to_png(_get_figure(_def_fouls_fn(fouls, offs)), w=440, h=540))
        return (pngs[0], pngs[1]) if len(pngs) == 2 else (None, None)

    _add_period_figs(pdf, events, _def_fouls, "Fouls & Offsides")

    # Defensive stats table
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.sub_title("Defensive Stats")
    try:
        _def_metrics = [
            ("Tackles",          "tackles"),
            ("Interceptions",    "interceptions"),
            ("Ball Recoveries",  "ball_recoveries"),
            ("Clearances",       "clearances"),
            ("Blocked Shots",    "blocked_shots"),
            ("Fouls Committed",  "fouls_committed"),
            ("PPDA",             "ppda"),
        ]
        pdf.two_team_stats(
            metrics=_def_metrics,
            home_dicts=(
                _def_half(events, "home"),
                _def_half(events, "home", period=1),
                _def_half(events, "home", period=2),
            ),
            away_dicts=(
                _def_half(events, "away"),
                _def_half(events, "away", period=1),
                _def_half(events, "away", period=2),
            ),
            home_label=home_team,
            away_label=away_team,
        )

        def_data = _def_compute(events)
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.sub_title("Top Player Defensive Stats")
        
        pdf.sub_title(home_team)
        pdf.data_table(def_data["home"]["player_full"], col_widths=[40, 15, 12, 12, 12, 12, 12], align=["L", "C", "C", "C", "C", "C", "C"])
        
        pdf.sub_title(away_team)
        pdf.data_table(def_data["away"]["player_full"], col_widths=[40, 15, 12, 12, 12, 12, 12], align=["L", "C", "C", "C", "C", "C", "C"])

    except Exception as exc:
        log.warning("Defense stats table: %s", exc)

    # ══════════════════════════════════════════════════════════════════
    # SECTION 5 – TRANSITIONS & COUNTERPRESSING
    # ══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("5. Transitions & Counterpressing")

    def _cp_maps(ev_p: pd.DataFrame):
        t = _trans_compute(ev_p)
        h_png = _plotly_to_png(
            _get_figure(_cp_map_fn(t["home"]["cp_events_df"], HOME_COLOR)), w=860, h=480
        )
        a_png = _plotly_to_png(
            _get_figure(_cp_map_fn(t["away"]["cp_events_df"], AWAY_COLOR)), w=860, h=480
        )
        return h_png, a_png

    _add_period_figs(pdf, events, _cp_maps, "Counterpressing Maps")

    # Transition stats table
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.sub_title("Transition Stats")
    try:
        _trans_metrics = [
            ("Ball Wins",           "ball_wins"),
            ("Turnovers",           "turnovers"),
            ("Transitions -> Shot",  "counter_shots"),
            ("Quick Regains (CP)",  "cp_regains"),
        ]
        pdf.two_team_stats(
            metrics=_trans_metrics,
            home_dicts=(
                _trans_half(events, "home"),
                _trans_half(events, "home", period=1),
                _trans_half(events, "home", period=2),
            ),
            away_dicts=(
                _trans_half(events, "away"),
                _trans_half(events, "away", period=1),
                _trans_half(events, "away", period=2),
            ),
            home_label=home_team,
            away_label=away_team,
        )
    except Exception as exc:
        log.warning("Transitions stats table: %s", exc)

    # ══════════════════════════════════════════════════════════════════
    # SECTION 6 – GOALKEEPING
    # ══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("6. Goalkeeping")

    _gk_metric_defs = [
        ("Shots Faced",     "total_shots"),
        ("Shots on Target", "shots_on_target"),
        ("Saves",           "saves"),
        ("Goals Conceded",  "goals_conceded"),
        ("Save %",          "save_pct"),
    ]

    try:
        gk_full = _gk_compute(events)

        for gk_pos, opp_pos, color, team_name in [
            ("home", "away", HOME_COLOR, home_team),
            ("away", "home", AWAY_COLOR, away_team),
        ]:
            d_f     = gk_full[gk_pos]
            gk_list = d_f['gk_list']

            if pdf.get_y() > 240:
                pdf.add_page()

            if len(gk_list) == 1:
                # ── Single GK: Full / 1H / 2H stats table ──────────────
                full_gk = {k: d_f[k] for k in
                           ("total_shots", "shots_on_target", "saves", "goals_conceded", "save_pct")}
                h1_gk   = _gk_half_stats(h1_events, gk_pos, opp_pos) if not h1_events.empty else {}
                h2_gk   = _gk_half_stats(h2_events, gk_pos, opp_pos) if not h2_events.empty else {}

                pdf.sub_title(f"GK Stats - {team_name}")
                pdf.single_team_stats(
                    metrics=_gk_metric_defs,
                    full=full_gk, h1=h1_gk, h2=h2_gk,
                    pct_keys={"save_pct"},
                )

                # Goal Mouth + Shot Map per period
                for period_label, period in _PERIODS:
                    ev_p = _filter_period(events, period)
                    if ev_p.empty:
                        continue
                    try:
                        gk_p        = _gk_compute(ev_p)[gk_pos]
                        shots_faced = gk_p["opp_shots_df"]
                        gm_png = _plotly_to_png(
                            _get_figure(_gk_mouth_fn(shots_faced, color, team_name)),
                            w=500, h=420,
                        )
                        sm_png = _plotly_to_png(
                            _gk_shot_map_fn(shots_faced, color, team_name),
                            w=440, h=540,
                        )
                        if gm_png or sm_png:
                            if pdf.get_y() > 240:
                                pdf.add_page()
                            pdf.sub_title(f"{team_name} - {period_label}", size=8)
                            if gm_png and sm_png:
                                pdf.two_images(gm_png, sm_png)
                            elif gm_png:
                                pdf.add_image_bytes(gm_png, w=90)
                            else:
                                pdf.add_image_bytes(sm_png, w=90)
                    except Exception as exc:
                        log.warning("GK plots %s %s: %s", team_name, period_label, exc)

            else:
                # ── Multi-GK: per-GK stats table ───────────────────────
                pdf.sub_title(f"GK Stats - {team_name} (Multiple Goalkeepers)")
                gk_rows = []
                for gk_entry in gk_list:
                    gk_rows.append({
                        "Goalkeeper": gk_entry['name'],
                        "Time":       gk_entry['time_label'] or "Full",
                        "Shots":      gk_entry['total_shots'],
                        "SoT":        gk_entry['shots_on_target'],
                        "Saves":      gk_entry['saves'],
                        "Goals":      gk_entry['goals_conceded'],
                        "Save%":      f"{gk_entry['save_pct']}%",
                    })
                pdf.data_table(
                    pd.DataFrame(gk_rows),
                    col_widths=[50, 20, 18, 14, 14, 14, 16],
                )

                # Plots: (All, GK0, GK1, …) × (Full, 1H, 2H)
                gk_selectors = ['all'] + [str(i) for i in range(len(gk_list))]
                for gk_sel in gk_selectors:
                    if gk_sel == 'all':
                        sel_label = "All GKs"
                    else:
                        idx       = int(gk_sel)
                        gk_entry  = gk_list[idx]
                        sel_label = f"{gk_entry['name']} ({gk_entry['time_label'] or 'Full'})"

                    for period_label, period in _PERIODS:
                        try:
                            shots_all = _gk_team_shots(d_f, gk_sel)
                            if period is not None and 'period_id' in shots_all.columns:
                                shots = shots_all[shots_all['period_id'] == period]
                            else:
                                shots = shots_all
                            if shots.empty:
                                continue
                            title  = f"{team_name} – {sel_label} – {period_label}"
                            gm_png = _plotly_to_png(
                                _get_figure(_gk_mouth_fn(shots, color, title)),
                                w=500, h=420,
                            )
                            sm_png = _plotly_to_png(
                                _gk_shot_map_fn(shots, color, title),
                                w=440, h=540,
                            )
                            if gm_png or sm_png:
                                if pdf.get_y() > 240:
                                    pdf.add_page()
                                pdf.sub_title(title, size=8)
                                if gm_png and sm_png:
                                    pdf.two_images(gm_png, sm_png)
                                elif gm_png:
                                    pdf.add_image_bytes(gm_png, w=90)
                                else:
                                    pdf.add_image_bytes(sm_png, w=90)
                        except Exception as exc:
                            log.warning(
                                "GK plots %s %s %s: %s",
                                team_name, sel_label, period_label, exc,
                            )

    except Exception as exc:
        log.warning("Goalkeeping section: %s", exc)

    # ══════════════════════════════════════════════════════════════════
    # SECTION 7 – PLAYER ANALYSIS
    # ══════════════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.section_title("7. Player Analysis")

    try:
        home_stats, away_stats = _build_all_player_stats(events)
        all_stats = home_stats + away_stats

        if all_stats:
            for s in all_stats:
                if pdf.get_y() > 200:
                    pdf.add_page()
                    pdf.section_title("7. Player Analysis (cont.)")

                team_name  = home_team if s.get('team_position') == 'home' else away_team
                team_color = _HTMLReport._HOME_CLR if s.get('team_position') == 'home' else _HTMLReport._AWAY_CLR
                hex_color  = HOME_COLOR if s.get('team_position') == 'home' else AWAY_COLOR

                pdf.sub_title(f"{s.get('player_name', 'Unknown')} #{s.get('jersey', '')} ({team_name}) - {s.get('display_position', '')}")

                # KPIs
                kpi_str_1 = f"Touches: {s.get('touches', 0)} | Passes: {s.get('passes', 0)} ({s.get('pass_acc', 0)}%) | Shots: {s.get('shots', 0)} | Goals: {s.get('goals', 0)}"
                kpi_str_2 = f"Tackles Won: {s.get('tackle_w', 0)}% | Aerials Won: {s.get('aerial_w', 0)}% | Interceptions: {s.get('ints', 0)} | Ball Recoveries: {s.get('recoveries', 0)}"
                
                pdf.current_section["elements"].append({"type": "subtitle", "content": kpi_str_1})
                pdf.current_section["elements"].append({"type": "subtitle", "content": kpi_str_2})
                
                # Plot heatmaps
                hx, hy = s.get('touch_x', []), s.get('touch_y', [])
                dx, dy = s.get('def_x', []), s.get('def_y', [])
                
                png_t = png_d = None
                if len(hx) > 1:
                    try:
                        b_t = render_lsc_heatmap_img(hx, hy, hex_color)
                        png_t = base64.b64decode(b_t.split(',')[1])
                    except: pass
                if len(dx) > 1:
                    try:
                        b_d = render_lsc_heatmap_img(dx, dy, hex_color)
                        png_d = base64.b64decode(b_d.split(',')[1])
                    except: pass
                
                if png_t and png_d:
                    pdf.two_images(png_t, png_d, col_w=85)
                elif png_t:
                    pdf.add_image_bytes(png_t, w=85)
                elif png_d:
                    pdf.add_image_bytes(png_d, w=85)
                else:
                    pass

        # Full Match Player Stats Table
        if all_stats:
            pass
            
            pdf.sub_title("Match Player Statistics", size=10)
            
            cols = [
                ("Player",  "player_name",  42),
                ("Team",    "team",         26),
                ("TCH",     "touches",      12),
                ("PAS",     "passes",       12),
                ("PA%",     "pass_acc",     12),
                ("SHT",     "shots",        12),
                ("G",       "goals",         9),
                ("TKL",     "tackles",      12),
                ("INT",     "ints",         12),
                ("REC",     "recoveries",   12),
                ("AER",     "aerials",      12),
            ]

            pdf.sub_title("Match Player Statistics")
            # Sorting logic remains same
            sorted_stats = [s for s in all_stats if s.get('team_position') == 'home'] + \
                           [s for s in all_stats if s.get('team_position') == 'away']

            # Use pdf.data_table or similar for the big table
            # Actually the original code had a manual loop for the big table because it had custom sorting/coloring.
            # I'll convert the sorted_stats to a DataFrame and use data_table.
            table_data = []
            for s in sorted_stats:
                table_data.append({
                    "Player": s.get('player_name', ''),
                    "Team": s.get('team', ''),
                    "TCH": s.get('touches', 0),
                    "PAS": s.get('passes', 0),
                    "PA%": s.get('pass_acc', 0),
                    "SHT": s.get('shots', 0),
                    "G": s.get('goals', 0),
                    "TKL": s.get('tackles', 0),
                    "INT": s.get('ints', 0),
                    "REC": s.get('recoveries', 0),
                    "AER": s.get('aerials', 0),
                })
            pdf.data_table(pd.DataFrame(table_data), col_widths=[42, 26, 12, 12, 12, 12, 9, 12, 12, 12, 12])

    except Exception as exc:
        log.warning("Player analysis section: %s", exc)

    return pdf.output_bytes()
