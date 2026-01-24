# CuléVision Styling Guide

## Overview
CuléVision uses a dark theme inspired by FC Barcelona's official colors: Blaugrana Blue (#004D98), Blaugrana Garnet (#A50044), and Gold (#EDBB00).

## Project Structure

```
Final-Masters-Project/
├── app.py                 # Main Dash application
├── config.py              # Configuration and constants
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
├── STYLING.md             # This file - styling documentation
└── assets/                # Static assets (auto-loaded by Dash)
    ├── culevision_logo.png    # CuléVision logo
    └── style.css              # Custom CSS styling
```

## Color Palette

### FC Barcelona Official Colors
- **Blaugrana Blue**: `#004D98` - Primary brand color
- **Blaugrana Garnet**: `#A50044` - Secondary brand color
- **Gold**: `#EDBB00` - Accent color for highlights

### Dark Theme Colors
- **Dark Background**: `#0A0E27` - Main background
- **Dark Secondary**: `#151932` - Card and component backgrounds
- **Dark Tertiary**: `#1E2139` - Hover states and depth
- **Dark Border**: `#2A2F4A` - Border and divider color

### Text Colors
- **Primary Text**: `#E8E9ED` - Main text color
- **Secondary Text**: `#A5A8B8` - Descriptive and secondary text

## CSS Organization

The `assets/style.css` file is automatically loaded by Dash and contains:

1. **CSS Variables** - Defined in `:root` for easy theme management
2. **Global Styles** - Body, text, and base element styling
3. **Component Styles** - Cards, buttons, forms, navigation, etc.
4. **Utility Classes** - Helper classes for colors and styling
5. **Animations** - Smooth transitions and fade-in effects
6. **Responsive Design** - Mobile-friendly adjustments

## Key Features

### Logo Integration
- Located in navbar
- 50px height on desktop, 40px on mobile
- Hover effect with slight scale animation
- Drop shadow for depth

### Navigation Bar
- Gradient background (blue to garnet)
- Gold border bottom (3px)
- Active state highlighting with gold accent
- Smooth hover transitions

### Cards
- Dark gradient backgrounds
- Hover animations (lift effect)
- Border glow on hover (blue and garnet)
- Gold titles for emphasis
- Consistent shadow depth

### Custom Scrollbar
- Styled to match theme
- Blue to garnet gradient
- Smooth hover transitions

## Usage in Components

### Using CSS Classes
```python
# Utility classes available
className="text-barca-blue"      # Blue text
className="text-barca-garnet"    # Garnet text
className="text-barca-gold"      # Gold text
className="bg-barca-blue"        # Blue background
```

### Using Config Colors
```python
from config import COLORS

# In component styles
style={'color': COLORS['gold']}
style={'backgroundColor': COLORS['dark_secondary']}
```

## Customization

To modify the theme:

1. **Colors**: Edit `config.py` COLORS dictionary
2. **CSS Variables**: Modify `:root` section in `assets/style.css`
3. **Components**: Update specific component styles in `assets/style.css`

## Best Practices

1. **Consistency**: Always use defined colors from config or CSS variables
2. **Accessibility**: Maintain sufficient contrast ratios for readability
3. **Performance**: Use CSS animations sparingly
4. **Responsiveness**: Test on multiple screen sizes
5. **Organization**: Keep styles in CSS file, not inline (except dynamic values)

## Future Enhancements

- Support for light theme toggle
- Additional color schemes for different competitions
- Enhanced animations for data visualizations
- Custom Plotly theme matching the dark design
