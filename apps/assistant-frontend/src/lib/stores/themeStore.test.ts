import { describe, expect, it, beforeEach } from 'vitest';

import { applyTheme, getDefaultTheme, isThemeName } from './themeStore';

describe('themeStore', () => {
  beforeEach(() => {
    document.documentElement.removeAttribute('data-theme');
  });

  it('defaults to gruvbox-dark', () => {
    expect(getDefaultTheme()).toBe('gruvbox-dark');
  });

  it('accepts only known theme names', () => {
    expect(isThemeName('gruvbox-dark')).toBe(true);
    expect(isThemeName('purple-intelligence')).toBe(true);
    expect(isThemeName('solarized')).toBe(false);
    expect(isThemeName(null)).toBe(false);
  });

  it('applies a theme to the root element', () => {
    applyTheme('purple-intelligence');

    expect(document.documentElement.getAttribute('data-theme')).toBe('purple-intelligence');
  });
});
