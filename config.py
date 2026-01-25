"""
CuléVision Configuration
Central configuration file for the application
"""

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
    'debug': True,
    'host': '0.0.0.0',
    'port': 8050
}

# Logo Configuration
LOGO_CONFIG = {
    'path': '/assets/logos/culevision_logo.png',
    'height': '50px',
    'alt': 'CuléVision Logo'
}

# Navigation Links
NAV_LINKS = [
    {'label': 'Home', 'href': '/'},
    {'label': 'Team Identity', 'href': '/team-identity'},
    {'label': 'Match Analysis', 'href': '/match-analysis'},
    {'label': 'Opposition Analysis', 'href': '/opposition-analysis'}
]

# Feature Cards Configuration
FEATURES = [
    {
        'icon': '⚽',
        'title': 'Match Analysis',
        'description': 'Automated analysis reducing review time from 3-4 hours to 30 minutes.'
    },
    {
        'icon': '🎯',
        'title': 'Rival Analysis',
        'description': 'Comprehensive opposition scouting and SWOT analysis.'
    },
    {
        'icon': '🏆',
        'title': 'Team Identity',
        'description': 'KPIs defining Barcelona\'s playing style and game model.'
    },
    {
        'icon': '🚨',
        'title': 'Live Alerts',
        'description': 'Real-time detection of critical match moments.'
    },
    {
        'icon': '💬',
        'title': 'Virtual Assistant',
        'description': 'Interactive query and analysis capabilities.'
    },
    {
        'icon': '📊',
        'title': 'Data Insights',
        'description': 'Deep dive into match statistics and performance metrics.'
    }
]
