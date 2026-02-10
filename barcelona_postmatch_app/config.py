"""Configuration constants for Barcelona Post-Match Analysis App."""

# Barcelona colors
BARCELONA_PRIMARY = "#A50044"   # Blaugrana red
BARCELONA_SECONDARY = "#004D98" # Blaugrana blue
BARCELONA_GOLD = "#EDBB00"      # Accent gold
BARCELONA_DARK = "#1A1A2E"      # Dark background

# Opposition default colors
OPPOSITION_PRIMARY = "#888888"
OPPOSITION_SECONDARY = "#CCCCCC"

TEAM_COLORS = {
    "Barcelona": (BARCELONA_PRIMARY, BARCELONA_SECONDARY),
    "FC Barcelona": (BARCELONA_PRIMARY, BARCELONA_SECONDARY),
    "Real Madrid": ("#FFFFFF", "#D4A843"),
    "Atletico Madrid": ("#CE1126", "#272E61"),
    "Sevilla": ("#D40F24", "#FFFFFF"),
    "Real Sociedad": ("#003DA5", "#FFFFFF"),
    "Villarreal": ("#FFE114", "#005DAA"),
    "Athletic Club": ("#EE2523", "#FFFFFF"),
    "Real Betis": ("#00954C", "#FFFFFF"),
    "Valencia": ("#EE3524", "#FFFFFF"),
    "Girona": ("#CD1719", "#FFFFFF"),
}

# Opta coordinate system (0-100 normalized)
OPTA_X_MAX = 100.0
OPTA_Y_MAX = 100.0

# Pitch dimensions in meters
PITCH_LENGTH = 105
PITCH_WIDTH = 68

# Detection thresholds
PRESSURE_DISTANCE = 3       # meters proximity for under-pressure
PROGRESSIVE_DISTANCE = 10   # minimum x-distance (in Opta units) for progressive pass
TRANSITION_TIME_WINDOW = 10 # seconds for transition detection
PRESS_REGAIN_WINDOW = 5     # seconds for press success
FAST_COUNTER_WINDOW = 5     # seconds for fast counter classification

# Phase zone boundaries (in Opta x-coordinates, attacking left-to-right: 0=own goal, 100=opp goal)
PHASE_ZONES = {
    "own_half": (0, 50),
    "middle_third": (33.3, 66.7),
    "final_third": (66.7, 100),
}

# Event type IDs (from Opta)
EVENT_TYPES = {
    "pass": 1,
    "offside_pass": 2,
    "take_on": 3,
    "foul": 4,
    "out": 5,
    "corner_awarded": 6,
    "tackle": 7,
    "interception": 8,
    "turnover": 9,
    "save": 10,
    "claim": 11,
    "clearance": 12,
    "miss": 13,
    "post": 14,
    "saved_shot": 15,
    "goal": 16,
    "card": 17,
    "player_off": 18,
    "player_on": 19,
    "player_retired": 20,
    "player_returns": 21,
    "start": 32,
    "end": 30,
    "team_setup": 34,
    "formation_change": 40,
    "aerial": 44,
    "challenge": 45,
    "ball_recovery": 49,
    "dispossessed": 50,
    "error": 51,
    "ball_touch": 61,
    "blocked_pass": 74,
    "delayed_start": 27,
    "end_delay": 28,
    "offside_provoked": 69,
    "attempt_saved": 15,
    "keeper_pick_up": 52,
    "chance_missed": 60,
    "temp_save": 10,
    "resume": 29,
    "contentious_referee_decision": 26,
}

# Shot event type IDs
SHOT_TYPES = {13, 14, 15, 16}  # miss, post, saved_shot, goal

# Set piece qualifiers
SET_PIECE_QUALIFIERS = {
    "corner": "Corner taken",
    "free_kick": "Free kick taken",
    "throw_in": "Throw in",
    "goal_kick": "Goal Kick",
}

# Formation mappings (from Opta ID to string)
FORMATION_MAP = {
    "2": "4-4-2",
    "3": "4-1-2-1-2",
    "4": "4-3-3",
    "5": "4-5-1",
    "6": "4-4-1-1",
    "7": "4-1-4-1",
    "8": "4-2-3-1",
    "9": "4-3-2-1",
    "10": "5-3-2",
    "11": "5-4-1",
    "12": "3-5-2",
    "13": "3-4-3",
    "14": "3-4-2-1",
    "15": "3-4-1-2",
    "16": "3-1-4-2",
    "17": "3-3-3-1",
    "18": "3-3-1-3",
    "19": "4-1-3-2",
    "20": "4-2-2-2",
    "21": "3-2-4-1",
    "22": "4-3-1-2",
    "23": "4-2-4-0",
    "24": "4-4-2 Diamond",
    "25": "5-2-3",
    "26": "3-5-1-1",
    "27": "5-2-2-1",
    "28": "4-2-1-3",
}

# KPI benchmarks (La Liga season averages for context)
LEAGUE_AVERAGES = {
    "progressive_pass_rate": 12.0,      # %
    "press_success_rate": 30.0,         # %
    "transition_speed": 6.0,            # seconds
    "possession_efficiency": 12.0,      # shots per 100 possessions
    "defensive_compactness": 55.0,      # index (0-100)
    "press_intensity": 2.0,             # defenders per press
    "pass_completion": 85.0,            # %
    "duel_win_rate": 50.0,              # %
}

# Visualization settings
HEATMAP_COLORSCALE = "YlOrRd"
HEATMAP_BINS_X = 10
HEATMAP_BINS_Y = 8
SCATTER_SIZE_SCALE = 10
PITCH_BG_COLOR = "#1A472A"
PITCH_LINE_COLOR = "#FFFFFF"
PITCH_LINE_WIDTH = 2

# Barcelona team identifiers (to match in data)
BARCELONA_NAMES = {"Barcelona", "FC Barcelona", "Futbol Club Barcelona"}
BARCELONA_CODES = {"BAR", "FCB"}

# Data path relative to project root
DATA_BASE_PATH = "opta_pipeline/data/result"
