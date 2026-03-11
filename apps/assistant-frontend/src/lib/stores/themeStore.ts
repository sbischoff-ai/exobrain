export type ThemeName = 'gruvbox-dark' | 'purple-intelligence';

const DEFAULT_THEME: ThemeName = 'gruvbox-dark';
const VALID_THEMES: ThemeName[] = ['gruvbox-dark', 'purple-intelligence'];

export function getDefaultTheme(): ThemeName {
  return DEFAULT_THEME;
}

export function isThemeName(value: unknown): value is ThemeName {
  return typeof value === 'string' && VALID_THEMES.includes(value as ThemeName);
}

export function applyTheme(theme: ThemeName): void {
  document.documentElement.setAttribute('data-theme', theme);
}
