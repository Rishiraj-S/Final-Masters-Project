"""
CuléVision Configuration
Central configuration file for the application
"""
import os

# FC Barcelona Brand Colors - Dark Theme
COLORS = {
    # Official FC Barcelona Colors
    'primary_blue': '#004D98',      # Blaugrana Blue
    'garnet': '#A50044',             # Blaugrana Garnet/Red
    'gold': '#EDBB00',               # Gold accent
    'white': '#FFFFFF',              # White

    # Dark Theme Colors
    'dark_bg': '#0A0E27',            # Main background
    'dark_secondary': '#151932',     # Secondary background
    'dark_tertiary': '#1E2139',      # Tertiary background
    'dark_border': '#2A2F4A',        # Border color

    # Text Colors
    'text_primary': '#E8E9ED',       # Primary text
    'text_secondary': '#A5A8B8'      # Secondary text
}

# Application Settings
APP_CONFIG = {
    'title': 'CuléVision',
    'subtitle': 'Game Analytics',
    'version': '0.1.0',
    'debug': os.getenv('CULEVISION_DEBUG', 'true').lower() == 'true',
    'host': '0.0.0.0',
    'port': 8050
}

# Navigation Links
NAV_LINKS = [
    {'label': 'Home', 'href': '/'},
    {'label': 'Match Analysis', 'href': '/match-analysis'},
    {'label': 'Player Analysis', 'href': '/player-analysis'},
    {'label': 'Team Analysis', 'href': '/team-analysis'},
    {'label': 'Opposition Analysis', 'href': '/opposition-analysis'},
]


