import { promises as fs } from 'fs';
import path from 'path';

/**
 * Theme token updater - modifies CSS variables in globals.css
 */

export interface ThemeTokens {
  colors?: Record<string, string>;
  typography?: {
    fontFamily?: Record<string, string>;
    fontSize?: Record<string, string>;
  };
  spacing?: Record<string, string>;
  borderRadius?: Record<string, string>;
}

export interface UpdateThemeOptions {
  sitePath: string;
  tokens: ThemeTokens;
  mode?: 'light' | 'dark' | 'both';
  dryRun?: boolean;
}

export interface UpdateThemeResult {
  success: boolean;
  changed: boolean;
  changedFiles: string[];
  warnings: string[];
  errors: string[];
  preview?: string;
}

/**
 * Convert hex color to HSL values for CSS variables
 */
export function hexToHSL(hex: string): string {
  // Remove # if present
  hex = hex.replace(/^#/, '');

  // Convert to RGB
  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0,
    s = 0,
    l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

    switch (max) {
      case r:
        h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
        break;
      case g:
        h = ((b - r) / d + 2) / 6;
        break;
      case b:
        h = ((r - g) / d + 4) / 6;
        break;
    }
  }

  h = Math.round(h * 360);
  s = Math.round(s * 100);
  l = Math.round(l * 100);

  return `${h} ${s}% ${l}%`;
}

/**
 * Find CSS variable declarations in content
 */
export function findCSSVariables(content: string): Map<string, string> {
  const variables = new Map<string, string>();
  const lines = content.split('\n');

  for (const line of lines) {
    const match = line.match(/^\s*--([a-z0-9-]+):\s*(.+?);?\s*$/);
    if (match) {
      variables.set(match[1], match[2]);
    }
  }

  return variables;
}

/**
 * Update CSS variable in content
 */
export function updateCSSVariable(
  content: string,
  varName: string,
  newValue: string,
  scope: 'root' | 'dark' = 'root'
): string {
  const lines = content.split('\n');
  let inScope = false;
  let updated = false;

  const selectorPattern = scope === 'root' ? ':root {' : '.dark {';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Check if entering scope
    if (line.trim() === selectorPattern) {
      inScope = true;
      continue;
    }

    // Check if exiting scope
    if (inScope && line.trim() === '}') {
      inScope = false;
      continue;
    }

    // Update variable if in scope
    if (inScope) {
      const match = line.match(/^(\s*)--([a-z0-9-]+):\s*(.+?);?\s*$/);
      if (match && match[2] === varName) {
        lines[i] = `${match[1]}--${varName}: ${newValue};`;
        updated = true;
      }
    }
  }

  // If variable wasn't found, add it to the scope
  if (!updated) {
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim() === selectorPattern) {
        // Find the closing brace
        let closingBrace = i + 1;
        while (closingBrace < lines.length && lines[closingBrace].trim() !== '}') {
          closingBrace++;
        }

        // Insert new variable before closing brace
        const indent = lines[i + 1]?.match(/^(\s*)/)?.[1] || '  ';
        lines.splice(closingBrace, 0, `${indent}--${varName}: ${newValue};`);
        break;
      }
    }
  }

  return lines.join('\n');
}

/**
 * Find globals.css file in site
 */
export async function findGlobalsCSS(sitePath: string): Promise<string | null> {
  const searchPaths = [
    path.join(sitePath, 'app', 'globals.css'),
    path.join(sitePath, 'src', 'app', 'globals.css'),
    path.join(sitePath, 'styles', 'globals.css'),
    path.join(sitePath, 'global.css'),
  ];

  for (const filePath of searchPaths) {
    try {
      await fs.access(filePath);
      return filePath;
    } catch {
      // File doesn't exist, try next
    }
  }

  return null;
}

/**
 * Update theme tokens in site
 */
export async function updateTheme(
  options: UpdateThemeOptions
): Promise<UpdateThemeResult> {
  const { sitePath, tokens, mode = 'both', dryRun = false } = options;

  const result: UpdateThemeResult = {
    success: false,
    changed: false,
    changedFiles: [],
    warnings: [],
    errors: [],
  };

  try {
    // Find globals.css
    const globalsPath = await findGlobalsCSS(sitePath);

    if (!globalsPath) {
      result.errors.push('GLOBALS_CSS_NOT_FOUND: Could not find globals.css in site');
      return result;
    }

    // Read content
    let content = await fs.readFile(globalsPath, 'utf-8');
    let modified = false;

    // Update colors
    if (tokens.colors) {
      for (const [colorName, colorValue] of Object.entries(tokens.colors)) {
        const hslValue = hexToHSL(colorValue);

        if (mode === 'light' || mode === 'both') {
          const newContent = updateCSSVariable(content, colorName, hslValue, 'root');
          if (newContent !== content) {
            content = newContent;
            modified = true;
          }
        }

        if (mode === 'dark' || mode === 'both') {
          const newContent = updateCSSVariable(content, colorName, hslValue, 'dark');
          if (newContent !== content) {
            content = newContent;
            modified = true;
          }
        }
      }
    }

    // Update typography
    if (tokens.typography?.fontFamily) {
      for (const [fontType, fontValue] of Object.entries(tokens.typography.fontFamily)) {
        const varName = `font-${fontType}`;
        const newContent = updateCSSVariable(content, varName, fontValue, 'root');
        if (newContent !== content) {
          content = newContent;
          modified = true;
        }
      }
    }

    // Update spacing
    if (tokens.spacing) {
      for (const [spaceName, spaceValue] of Object.entries(tokens.spacing)) {
        const varName = `spacing-${spaceName}`;
        const newContent = updateCSSVariable(content, varName, spaceValue, 'root');
        if (newContent !== content) {
          content = newContent;
          modified = true;
        }
      }
    }

    // Update border radius
    if (tokens.borderRadius) {
      for (const [radiusName, radiusValue] of Object.entries(tokens.borderRadius)) {
        const varName = `radius-${radiusName}`;
        const newContent = updateCSSVariable(content, varName, radiusValue, 'root');
        if (newContent !== content) {
          content = newContent;
          modified = true;
        }
      }
    }

    if (!modified) {
      result.success = true;
      result.changed = false;
      result.warnings.push('NO_CHANGES: No CSS variables were modified');
      return result;
    }

    // Dry run: return preview
    if (dryRun) {
      result.success = true;
      result.changed = true;
      result.changedFiles = [path.relative(sitePath, globalsPath)];
      result.warnings.push('DRY_RUN: No files were modified');
      result.preview = content;
      return result;
    }

    // Write updated content
    await fs.writeFile(globalsPath, content, 'utf-8');

    result.success = true;
    result.changed = true;
    result.changedFiles = [path.relative(sitePath, globalsPath)];

    return result;
  } catch (error: any) {
    result.errors.push(`UPDATE_THEME_ERROR: ${error.message}`);
    return result;
  }
}

/**
 * Extract current theme tokens from site
 */
export async function extractThemeTokens(sitePath: string): Promise<ThemeTokens> {
  const tokens: ThemeTokens = {
    colors: {},
    typography: {},
  };

  try {
    const globalsPath = await findGlobalsCSS(sitePath);
    if (!globalsPath) return tokens;

    const content = await fs.readFile(globalsPath, 'utf-8');
    const variables = findCSSVariables(content);

    // Extract colors
    const colorVars = ['primary', 'secondary', 'accent', 'background', 'foreground', 'muted', 'border'];
    for (const colorName of colorVars) {
      if (variables.has(colorName)) {
        tokens.colors![colorName] = variables.get(colorName)!;
      }
    }

    // Extract font families
    const fontVars = ['font-sans', 'font-mono', 'font-display'];
    tokens.typography!.fontFamily = {};
    for (const fontVar of fontVars) {
      if (variables.has(fontVar)) {
        const fontType = fontVar.replace('font-', '');
        tokens.typography!.fontFamily[fontType] = variables.get(fontVar)!;
      }
    }

    return tokens;
  } catch {
    return tokens;
  }
}
