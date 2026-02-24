export type ScrollPhase = 'idle' | 'stream-follow' | 'catchup';

export interface AutoScrollSnapshot {
  phase: ScrollPhase;
  suspended: boolean;
}

interface AutoScrollConfig {
  bottomThresholdPx: number;
  resumeThresholdPx: number;
  followPxPerSecond: number;
  catchupPxPerSecond: number;
}

const defaultConfig: AutoScrollConfig = {
  bottomThresholdPx: 20,
  resumeThresholdPx: 24,
  followPxPerSecond: 900,
  catchupPxPerSecond: 900
};

export class ChatAutoScroller {
  private suspended = false;
  private phase: ScrollPhase = 'idle';

  constructor(private readonly config: AutoScrollConfig = defaultConfig) {}

  getSnapshot(): AutoScrollSnapshot {
    return { phase: this.phase, suspended: this.suspended };
  }

  markSuspended(): void {
    this.suspended = true;
  }

  maybeResume(distanceFromBottom: number): void {
    if (distanceFromBottom <= this.config.resumeThresholdPx) {
      this.suspended = false;
    }
  }

  nextPhase(params: {
    streamingInProgress: boolean;
    distanceFromBottom: number;
    forceCatchup?: boolean;
  }): AutoScrollSnapshot {
    if (this.suspended) {
      this.phase = 'idle';
      return this.getSnapshot();
    }

    if (params.streamingInProgress) {
      this.phase = 'stream-follow';
      return this.getSnapshot();
    }

    if (params.forceCatchup && params.distanceFromBottom > 1) {
      this.phase = 'catchup';
      return this.getSnapshot();
    }

    this.phase = params.distanceFromBottom > this.config.bottomThresholdPx ? 'catchup' : 'idle';
    return this.getSnapshot();
  }

  getStepForPhase(phase: ScrollPhase, deltaMs: number): number {
    if (phase === 'stream-follow') {
      return (this.config.followPxPerSecond * deltaMs) / 1000;
    }
    if (phase === 'catchup') {
      return (this.config.catchupPxPerSecond * deltaMs) / 1000;
    }
    return 0;
  }
}

export function getDistanceFromBottom(container: HTMLElement): number {
  return Math.max(container.scrollHeight - (container.scrollTop + container.clientHeight), 0);
}
