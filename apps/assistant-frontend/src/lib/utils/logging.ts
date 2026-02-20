const LEVELS: Record<string, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40
};

const DEFAULT_LEVEL = import.meta.env.DEV ? 'debug' : 'warn';
const configuredLevel = (import.meta.env.PUBLIC_LOG_LEVEL || DEFAULT_LEVEL).toLowerCase();
const minimumLevel = LEVELS[configuredLevel] ?? LEVELS[DEFAULT_LEVEL];

function shouldLog(level: keyof typeof LEVELS): boolean {
  return LEVELS[level] >= minimumLevel;
}

function formatMessage(scope: string, message: string): string {
  return `[${scope}] ${message}`;
}

export function createLogger(scope: string) {
  return {
    debug(message: string, context?: unknown): void {
      if (shouldLog('debug')) {
        console.debug(formatMessage(scope, message), context ?? '');
      }
    },
    info(message: string, context?: unknown): void {
      if (shouldLog('info')) {
        console.info(formatMessage(scope, message), context ?? '');
      }
    },
    warn(message: string, context?: unknown): void {
      if (shouldLog('warn')) {
        console.warn(formatMessage(scope, message), context ?? '');
      }
    },
    error(message: string, context?: unknown): void {
      if (shouldLog('error')) {
        console.error(formatMessage(scope, message), context ?? '');
      }
    }
  };
}
