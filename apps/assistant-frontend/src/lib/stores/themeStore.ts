export const THEME_STORAGE_KEY = 'exobrain.assistant.theme';

export type ThemeName = 'gruvbox-dark' | 'purple-intelligence';

const DEFAULT_THEME: ThemeName = 'gruvbox-dark';
const VALID_THEMES: ThemeName[] = ['gruvbox-dark', 'purple-intelligence'];

export function getDefaultTheme(): ThemeName {
  return DEFAULT_THEME;
}

export function isThemeName(value: unknown): value is ThemeName {
  return typeof value === 'string' && VALID_THEMES.includes(value as ThemeName);
}

export function loadTheme(): ThemeName {
  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  return isThemeName(storedTheme) ? storedTheme : DEFAULT_THEME;
}

export function saveTheme(theme: ThemeName): void {
  window.localStorage.setItem(THEME_STORAGE_KEY, theme);
}

export function applyTheme(theme: ThemeName): void {
  document.documentElement.setAttribute('data-theme', theme);
}

export function toggleTheme(theme: ThemeName): ThemeName {
  return theme === 'gruvbox-dark' ? 'purple-intelligence' : 'gruvbox-dark';
}
