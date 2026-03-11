import { beforeEach, describe, expect, it } from 'vitest';

import {
  applyTheme,
  getDefaultTheme,
  isThemeName,
  loadTheme,
  saveTheme,
  THEME_STORAGE_KEY,
  toggleTheme
} from './themeStore';

describe('themeStore', () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('defaults to gruvbox-dark when no persisted theme exists', () => {
    expect(getDefaultTheme()).toBe('gruvbox-dark');
    expect(loadTheme()).toBe('gruvbox-dark');
  });

  it('accepts only known theme names', () => {
    expect(isThemeName('gruvbox-dark')).toBe(true);
    expect(isThemeName('purple-intelligence')).toBe(true);
    expect(isThemeName('unknown')).toBe(false);
  });

  it('persists and applies a theme', () => {
    saveTheme('purple-intelligence');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('purple-intelligence');

    applyTheme('purple-intelligence');
    expect(document.documentElement.getAttribute('data-theme')).toBe('purple-intelligence');
  });

  it('toggles between available themes', () => {
    expect(toggleTheme('gruvbox-dark')).toBe('purple-intelligence');
    expect(toggleTheme('purple-intelligence')).toBe('gruvbox-dark');
  });
});
