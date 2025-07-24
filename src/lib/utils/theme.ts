// Dynamic theme utilities for Open WebUI

/**
 * Converts HSL values to hex color
 * @param h - Hue (0-360)
 * @param s - Saturation (0-100)
 * @param l - Lightness (0-100)
 * @returns Hex color string
 */
export function hslToHex(h: number, s: number, l: number): string {
  l /= 100;
  const a = s * Math.min(l, 1 - l) / 100;
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, '0');
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

/**
 * Converts hex color to HSL values
 * @param hex - Hex color string (with or without #)
 * @returns Tuple of [hue, saturation, lightness] values
 */
export function hexToHsl(hex: string): [number, number, number] {
  // Remove the # if present
  hex = hex.replace('#', '');
  
  // Parse r, g, b values
  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0, s = 0, l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }

  return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)];
}

/**
 * Generate a complete gray palette with the specified hue and saturation
 * @param baseColor - Base hex color to extract hue from
 * @returns Object mapping shade numbers to hex colors
 */
export function generateCustomGrayPalette(baseColor: string): Record<string, string> {
  const [hue, saturation] = hexToHsl(baseColor);
  
  // Use very low saturation to keep it subtle, regardless of input saturation
  const subtleSaturation = Math.min(saturation, 15);
  
  return {
    50: hslToHex(hue, subtleSaturation, 98),
    100: hslToHex(hue, subtleSaturation, 95),
    200: hslToHex(hue, subtleSaturation, 88),
    300: hslToHex(hue, subtleSaturation, 80),
    400: hslToHex(hue, subtleSaturation, 70),
    500: hslToHex(hue, subtleSaturation, 60),
    600: hslToHex(hue, subtleSaturation, 45),
    700: hslToHex(hue, subtleSaturation, 35),
    800: hslToHex(hue, subtleSaturation, 22), // Main background
    850: hslToHex(hue, subtleSaturation, 16), // Darker background  
    900: hslToHex(hue, subtleSaturation, 10), // Very dark background
    950: hslToHex(hue, subtleSaturation, 6),  // Darkest background
  };
}

/**
 * Apply custom theme colors dynamically via CSS variables
 * @param baseColor - Base hex color to generate palette from
 */
export function applyCustomThemeColors(baseColor: string): void {
  const palette = generateCustomGrayPalette(baseColor);
  const root = document.documentElement;
  
  // Apply the custom color palette
  Object.entries(palette).forEach(([shade, color]) => {
    root.style.setProperty(`--color-gray-${shade}`, color);
  });
}

/**
 * Reset to default gray colors
 */
export function resetToDefaultGrayColors(): void {
  const root = document.documentElement;
  
  // Default gray colors from tailwind.config.js
  const defaultGrays = {
    50: '#f9f9f9',
    100: '#ececec', 
    200: '#e3e3e3',
    300: '#cdcdcd',
    400: '#b4b4b4',
    500: '#9b9b9b',
    600: '#676767',
    700: '#4e4e4e',
    800: '#333',
    850: '#262626',
    900: '#171717',
    950: '#0d0d0d'
  };
  
  Object.entries(defaultGrays).forEach(([shade, color]) => {
    root.style.setProperty(`--color-gray-${shade}`, color);
  });
}
