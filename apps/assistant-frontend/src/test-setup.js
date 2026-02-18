import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/svelte';
import { afterEach } from 'vitest';

// Keep DOM isolated between tests to avoid duplicated components leaking state.
afterEach(() => {
  cleanup();
});

// JSDOM does not implement scroll behavior, so we neutralize it globally for tests.
if (!HTMLElement.prototype.scrollTo) {
  HTMLElement.prototype.scrollTo = () => {};
}

// Svelte transitions rely on Web Animations API; provide a minimal test-safe stub.
if (!Element.prototype.animate) {
  Element.prototype.animate = () => ({
    finished: Promise.resolve(),
    cancel: () => {},
    play: () => {}
  });
}
