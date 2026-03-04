import { describe, expect, it } from 'vitest';

import { formatTimestamp } from '$lib/utils/datetime';

describe('datetime utils', () => {
  it('formats valid timestamps for display', () => {
    const formatted = formatTimestamp('2026-01-02T03:04:05Z');

    expect(formatted).toBe('2026/01/02 03:04');
  });

  it('returns empty string for invalid timestamps', () => {
    expect(formatTimestamp('not-a-date')).toBe('');
    expect(formatTimestamp('')).toBe('');
    expect(formatTimestamp(null)).toBe('');
  });

  it('formats backend timestamps with bracketed timezone names', () => {
    const formatted = formatTimestamp('2026-03-04T23:17:10.326738+00:00[Etc/UTC]');

    expect(formatted).toBe('2026/03/04 23:17');
  });
});
