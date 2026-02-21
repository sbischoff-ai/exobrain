import { randomUUID } from 'node:crypto';

const DEFAULT_EMAIL = 'test.user@exobrain.local';
const DEFAULT_PASSWORD = 'password123';
const SESSION_COOKIE = 'exobrain_mock_session';
const DAY_MS = 24 * 60 * 60 * 1000;

function formatReference(date) {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}/${month}/${day}`;
}

function buildSeedState() {
  const today = new Date();
  const entries = [];
  for (let i = 0; i < 7; i += 1) {
    entries.push(formatReference(new Date(today.getTime() - i * DAY_MS)));
  }

  const messagesByReference = {
    [entries[0]]: [
      {
        id: randomUUID(),
        role: 'assistant',
        content:
          'Welcome to mock mode.\n\n```ts\nconst status = "ready";\nconsole.log(status);\n```',
        sequence: 1
      },
      { id: randomUUID(), role: 'user', content: 'Show me around this UI.', sequence: 2 },
      {
        id: randomUUID(),
        role: 'assistant',
        content: 'Use the journal drawer on the left and send messages to test streaming states.',
        sequence: 3
      }
    ],
    [entries[1]]: [
      { id: randomUUID(), role: 'assistant', content: 'Yesterday journal entry.', sequence: 1 },
      { id: randomUUID(), role: 'user', content: 'Old context example.', sequence: 2 }
    ]
  };

  return { entries, messagesByReference, sessions: new Set() };
}

function parseCookies(cookieHeader = '') {
  return cookieHeader
    .split(';')
    .map((part) => part.trim())
    .filter(Boolean)
    .reduce((acc, part) => {
      const [name, ...rest] = part.split('=');
      acc[name] = decodeURIComponent(rest.join('='));
      return acc;
    }, {});
}

function json(res, status, payload, headers = {}) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json');
  Object.entries(headers).forEach(([key, value]) => {
    res.setHeader(key, value);
  });
  res.end(JSON.stringify(payload));
}

function sendTextStream(res, chunks) {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain; charset=utf-8');
  res.setHeader('Transfer-Encoding', 'chunked');

  let index = 0;
  const timer = setInterval(() => {
    if (index >= chunks.length) {
      clearInterval(timer);
      res.end();
      return;
    }
    res.write(chunks[index]);
    index += 1;
  }, 60);
}

async function parseBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(Buffer.from(chunk));
  }
  if (!chunks.length) {
    return {};
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

function getReferenceFromPath(pathname) {
  const base = '/api/journal/';
  if (!pathname.startsWith(base)) {
    return null;
  }
  const tail = pathname.slice(base.length);
  if (tail === 'today' || tail === 'today/messages') {
    return null;
  }
  if (tail.endsWith('/messages')) {
    return decodeURIComponent(tail.slice(0, -'/messages'.length));
  }
  return decodeURIComponent(tail);
}

function requireSession(req, res, state) {
  const cookies = parseCookies(req.headers.cookie || '');
  const sessionId = cookies[SESSION_COOKIE];
  if (!sessionId || !state.sessions.has(sessionId)) {
    json(res, 401, { detail: 'Unauthorized' });
    return null;
  }
  return sessionId;
}

function parseOptionalNumber(value) {
  if (value == null || value === "") {
    return undefined;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function listMessagesDescending(messages, cursor, limit) {
  let filtered = [...messages];
  if (typeof cursor === 'number' && !Number.isNaN(cursor)) {
    filtered = filtered.filter((message) => message.sequence < cursor);
  }
  const sorted = filtered.sort((a, b) => b.sequence - a.sequence);
  return sorted.slice(0, limit);
}

function ensureReference(state, reference) {
  if (!state.entries.includes(reference)) {
    state.entries.unshift(reference);
  }
  if (!state.messagesByReference[reference]) {
    state.messagesByReference[reference] = [];
  }
}

export function createMockApiPlugin({ enabled }) {
  const state = buildSeedState();

  return {
    name: 'assistant-frontend-mock-api',
    configureServer(server) {
      if (!enabled) {
        return;
      }

      server.middlewares.use(async (req, res, next) => {
        if (!req.url) {
          next();
          return;
        }

        const url = new URL(req.url, 'http://localhost');
        const { pathname, searchParams } = url;

        if (!pathname.startsWith('/api/')) {
          next();
          return;
        }

        if (pathname === '/api/auth/login' && req.method === 'POST') {
          const body = await parseBody(req);
          if (body.email !== DEFAULT_EMAIL || body.password !== DEFAULT_PASSWORD) {
            json(res, 401, { detail: 'Invalid credentials for mock mode' });
            return;
          }

          const sessionId = randomUUID();
          state.sessions.add(sessionId);
          json(
            res,
            200,
            { ok: true },
            { 'Set-Cookie': `${SESSION_COOKIE}=${sessionId}; Path=/; HttpOnly; SameSite=Lax` }
          );
          return;
        }

        if (pathname === '/api/auth/logout' && req.method === 'POST') {
          const cookies = parseCookies(req.headers.cookie || '');
          if (cookies[SESSION_COOKIE]) {
            state.sessions.delete(cookies[SESSION_COOKIE]);
          }
          res.statusCode = 204;
          res.setHeader('Set-Cookie', `${SESSION_COOKIE}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax`);
          res.end();
          return;
        }

        if (pathname === '/api/users/me' && req.method === 'GET') {
          const sessionId = requireSession(req, res, state);
          if (!sessionId) {
            return;
          }
          json(res, 200, { name: 'Test User', email: DEFAULT_EMAIL });
          return;
        }

        const sessionId = requireSession(req, res, state);
        if (!sessionId) {
          return;
        }

        if (pathname === '/api/journal/today' && req.method === 'GET') {
          const reference = state.entries[0];
          ensureReference(state, reference);
          json(res, 200, { reference, message_count: state.messagesByReference[reference].length });
          return;
        }

        if (pathname === '/api/journal' && req.method === 'GET') {
          json(
            res,
            200,
            state.entries.map((reference) => ({
              reference,
              message_count: (state.messagesByReference[reference] || []).length
            }))
          );
          return;
        }

        if (pathname === '/api/journal/today/messages' && req.method === 'GET') {
          const reference = state.entries[0];
          ensureReference(state, reference);
          const cursor = parseOptionalNumber(searchParams.get('cursor'));
          const limit = parseOptionalNumber(searchParams.get('limit')) ?? 50;
          json(res, 200, listMessagesDescending(state.messagesByReference[reference], cursor, limit));
          return;
        }

        if (pathname.startsWith('/api/journal/') && req.method === 'GET') {
          const reference = getReferenceFromPath(pathname);
          if (!reference) {
            json(res, 404, { detail: 'not found' });
            return;
          }
          ensureReference(state, reference);

          if (pathname.endsWith('/messages')) {
            const cursor = parseOptionalNumber(searchParams.get('cursor'));
            const limit = parseOptionalNumber(searchParams.get('limit')) ?? 50;
            json(res, 200, listMessagesDescending(state.messagesByReference[reference], cursor, limit));
            return;
          }

          json(res, 200, { reference, message_count: state.messagesByReference[reference].length });
          return;
        }

        if (pathname === '/api/chat/message' && req.method === 'POST') {
          const body = await parseBody(req);
          const reference = state.entries[0];
          ensureReference(state, reference);

          const nextSequence = state.messagesByReference[reference].length + 1;
          state.messagesByReference[reference].push({
            id: randomUUID(),
            role: 'user',
            content: String(body.message || ''),
            sequence: nextSequence
          });

          const assistantText = `Mock response: ${String(body.message || '').trim() || 'I am ready to help.'}`;
          state.messagesByReference[reference].push({
            id: randomUUID(),
            role: 'assistant',
            content: assistantText,
            sequence: nextSequence + 1
          });

          sendTextStream(res, ['Mock response: ', String(body.message || ''), '\n\n(UI-only mode)']);
          return;
        }

        json(res, 404, { detail: 'unknown mock endpoint' });
      });
    }
  };
}
