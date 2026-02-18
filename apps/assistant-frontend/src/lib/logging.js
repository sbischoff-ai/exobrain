const LEVELS = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40
};

const DEFAULT_LEVEL = import.meta.env.DEV ? 'debug' : 'warn';
const configuredLevel = (import.meta.env.PUBLIC_LOG_LEVEL || DEFAULT_LEVEL).toLowerCase();
const minimumLevel = LEVELS[configuredLevel] ?? LEVELS[DEFAULT_LEVEL];

function shouldLog(level) {
  return LEVELS[level] >= minimumLevel;
}

function formatMessage(scope, message) {
  return `[${scope}] ${message}`;
}

export function createLogger(scope) {
  return {
    debug(message, context) {
      if (shouldLog('debug')) {
        console.debug(formatMessage(scope, message), context ?? '');
      }
    },
    info(message, context) {
      if (shouldLog('info')) {
        console.info(formatMessage(scope, message), context ?? '');
      }
    },
    warn(message, context) {
      if (shouldLog('warn')) {
        console.warn(formatMessage(scope, message), context ?? '');
      }
    },
    error(message, context) {
      if (shouldLog('error')) {
        console.error(formatMessage(scope, message), context ?? '');
      }
    }
  };
}
