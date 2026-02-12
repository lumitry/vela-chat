# Custom Theme Creation Guide for VelaChat

## Overview

VelaChat uses a sophisticated theming system that combines:
1. **CSS Custom Properties** (CSS variables) defined in `tailwind.config.js`
2. **CSS classes** applied to `document.documentElement`
3. **JavaScript-based theme switching**

**Important Note**: Theming requires some workarounds and careful implementation. It's often easier just to use the built-in custom color schemes feature, which allows you to select colors directly from the UI without needing to create a full theme file. This guide is already kind of outdated since I added the custom feature and removed built-in support for the new `forest`, `ocean`, and `sunset` themes, but it still should serve as a good reference.

## Key Challenges & Solutions

### 1. Theme Application Timing
Themes may not apply immediately due to CSS variable conflicts. The `applyTheme` function now:
- Resets all CSS custom properties first
- Properly removes old theme classes
- Ensures dark mode is applied for custom themes

### 2. Anchor Tag Styling
Some menu items use `<a>` tags instead of `<button>` tags, which don't inherit button styling. The `theme-fixes.css` file addresses this.

### 3. Color Harmony
The original themes were too vibrant and clashed with existing UI elements. The new approach uses:
- **Subtle color shifts** from the default gray palette
- **Consistent color temperature** (warm/cool) across all shades
- **Maintained contrast ratios** for accessibility

## Creating a Custom Theme

### Step 1: Create Your Theme CSS File

Create a new CSS file in `/static/themes/your-theme-name.css`:

```css
/* Your Custom Theme - Subtle approach */
html.your-theme-name {
  /* Only redefine gray colors with subtle shifts */
  --color-gray-50: #fefbf8;    /* Very subtle warm/cool shift */
  --color-gray-100: #f7f3f0;   
  --color-gray-200: #f0e8e2;   
  --color-gray-300: #e1d2c7;   
  --color-gray-400: #c4b5a8;   
  --color-gray-500: #a59186;   
  --color-gray-600: #7a6b5e;   
  --color-gray-700: #5a4f45;   
  --color-gray-800: #3d342d;   /* Key background color */
  --color-gray-850: #2f2621;   
  --color-gray-900: #1f1b17;   /* Sidebar/darker areas */
  --color-gray-950: #151310;   
}
```

**Important**: Keep color shifts very subtle. The original grays are:
- `--color-gray-800: #333` 
- `--color-gray-850: #262626`
- `--color-gray-900: #171717`
- `--color-gray-950: #0d0d0d`

### Step 2: Include the CSS File

Add your theme CSS to `/src/routes/+layout.svelte`:

```svelte
<link rel="stylesheet" type="text/css" href="/themes/your-theme-name.css" />
```

### Step 3: Add Theme to Settings

1. **Add to theme selector** in `/src/lib/components/chat/Settings/General.svelte`:
```svelte
<option value="your-theme-name">🎨 Your Theme Name</option>
```

2. **Add to themes array**:
```javascript
let themes = ['dark', 'light', 'rose-pine dark', 'rose-pine-dawn light', 'oled-dark', 'her', 'sunset', 'ocean', 'forest', 'your-theme-name'];
```

3. **Update the applyTheme function** to handle your theme in the meta theme color section and add it to the custom themes check.

### Step 4: Add Initial Theme Support

Update `/src/app.html` to handle initial loading:

```javascript
} else if (localStorage.theme === 'your-theme-name') {
  document.documentElement.classList.add('dark');
  document.documentElement.classList.add('your-theme-name');
  metaThemeColorTag.setAttribute('content', '#your-darkest-color');
```

## Current Themes (OUTDATED)

### 1. Sunset Theme (Warm)
- Very subtle warm brown tones
- Temperature: Warm
- Good for: Evening use, reduces blue light

### 2. Ocean Theme (Cool) 
- Very subtle cool blue-gray tones
- Temperature: Cool
- Good for: Daytime use, easier on eyes

### 3. Forest Theme (Neutral-Green)
- Very subtle green-gray tones  
- Temperature: Neutral with slight green tint
- Good for: All-day use, natural feeling

## Design Philosophy

1. **Subtlety over Boldness**: Barely perceptible color shifts work better than dramatic changes
2. **Consistency**: All grays should have the same temperature (warm/cool)
3. **Accessibility**: Maintain contrast ratios from the original theme
4. **Harmony**: Don't fight the existing design, enhance it subtly

## Troubleshooting

- **Theme not applying immediately**: The new `applyTheme` function should fix this
- **Anchor tags not styled**: Covered by `theme-fixes.css`
- **Colors too bold**: Make them more subtle - shift hue/saturation slightly, not dramatically
- **Text hard to read**: Ensure you're only changing background colors, not text colors
- **Theme not persisting**: Check that theme name matches exactly across all files

## Advanced Tips

1. **Use HSL color space** for easier temperature adjustments
2. **Test in different lighting conditions**
3. **Consider colorblind users** - avoid red/green as primary distinguishing colors
4. **Keep a backup** of working configurations before making changes
