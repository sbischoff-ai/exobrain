import { describe, expect, it } from 'vitest';

import { ChatAutoScroller } from './chatAutoScroll';

describe('ChatAutoScroller', () => {
  it('uses fast phase while stream message top is still below container top', () => {
    const scroller = new ChatAutoScroller();

    const snapshot = scroller.nextPhase({
      streamingInProgress: true,
      streamMessageTopAtOrAboveContainerTop: false,
      distanceFromBottom: 240
    });

    expect(snapshot.phase).toBe('stream-fast');
  });

  it('switches to slow phase once stream message reaches top boundary', () => {
    const scroller = new ChatAutoScroller();

    const snapshot = scroller.nextPhase({
      streamingInProgress: true,
      streamMessageTopAtOrAboveContainerTop: true,
      distanceFromBottom: 200
    });

    expect(snapshot.phase).toBe('stream-slow');
    expect(Math.round(scroller.getStepForPhase('stream-slow', 1000))).toBe(22);
  });

  it('suspends and resumes when user returns close to bottom', () => {
    const scroller = new ChatAutoScroller();

    scroller.markSuspended();
    expect(
      scroller.nextPhase({
        streamingInProgress: true,
        streamMessageTopAtOrAboveContainerTop: false,
        distanceFromBottom: 140
      }).phase
    ).toBe('idle');

    scroller.maybeResume(10);

    expect(
      scroller.nextPhase({
        streamingInProgress: true,
        streamMessageTopAtOrAboveContainerTop: false,
        distanceFromBottom: 140
      }).phase
    ).toBe('stream-fast');
  });


  it('keeps catchup phase active below bottom threshold when forced', () => {
    const scroller = new ChatAutoScroller();

    expect(
      scroller.nextPhase({
        streamingInProgress: false,
        streamMessageTopAtOrAboveContainerTop: true,
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
        streamMessageTopAtOrAboveContainerTop: true,
        distanceFromBottom: 90
      }).phase
    ).toBe('catchup');

    expect(
      scroller.nextPhase({
        streamingInProgress: false,
        streamMessageTopAtOrAboveContainerTop: true,
        distanceFromBottom: 5
      }).phase
    ).toBe('idle');

    expect(Math.round(scroller.getStepForPhase('catchup', 1000))).toBe(22);
  });
});
