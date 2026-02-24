import { describe, expect, it } from 'vitest';

import { ChatAutoScroller } from './chatAutoScroll';

describe('ChatAutoScroller', () => {
  it('uses follow phase while streaming is active', () => {
    const scroller = new ChatAutoScroller();

    const snapshot = scroller.nextPhase({
      streamingInProgress: true,
      distanceFromBottom: 240
    });

    expect(snapshot.phase).toBe('stream-follow');
  });

  it('suspends and resumes when user returns close to bottom', () => {
    const scroller = new ChatAutoScroller();

    scroller.markSuspended();
    expect(
      scroller.nextPhase({
        streamingInProgress: true,
        distanceFromBottom: 140
      }).phase
    ).toBe('idle');

    scroller.maybeResume(10);

    expect(
      scroller.nextPhase({
        streamingInProgress: true,
        distanceFromBottom: 140
      }).phase
    ).toBe('stream-follow');
  });

  it('keeps catchup phase active below bottom threshold when forced', () => {
    const scroller = new ChatAutoScroller();

    expect(
      scroller.nextPhase({
        streamingInProgress: false,
        distanceFromBottom: 5,
        forceCatchup: true
      }).phase
    ).toBe('catchup');
  });

  it('continues catchup scrolling after stream ends until bottom is reached', () => {
    const scroller = new ChatAutoScroller();

    expect(
      scroller.nextPhase({
        streamingInProgress: false,
        distanceFromBottom: 90
      }).phase
    ).toBe('catchup');

    expect(
      scroller.nextPhase({
        streamingInProgress: false,
        distanceFromBottom: 5
      }).phase
    ).toBe('idle');

    expect(Math.round(scroller.getStepForPhase('catchup', 1000))).toBe(900);
  });
});
