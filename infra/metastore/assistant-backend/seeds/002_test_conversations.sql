WITH conversation_seed AS (
  SELECT
    '11111111-1111-1111-1111-111111111111'::uuid AS user_id,
    reference,
    created_at::timestamptz,
    updated_at::timestamptz
  FROM (
    VALUES
      ('2025/01/14', '2025-01-14T09:00:00Z', '2025-01-14T09:20:00Z'),
      ('2025/01/19', '2025-01-19T08:30:00Z', '2025-01-19T09:40:00Z'),
      ('2025/02/03', '2025-02-03T07:50:00Z', '2025-02-03T08:30:00Z'),
      ('2025/02/11', '2025-02-11T12:00:00Z', '2025-02-11T12:35:00Z'),
      ('2025/02/16', '2025-02-16T10:10:00Z', '2025-02-16T11:25:00Z'),
      ('2025/02/18', '2025-02-18T06:45:00Z', '2025-02-18T07:50:00Z'),
      ('2025/02/19', '2025-02-19T07:15:00Z', '2025-02-19T07:15:00Z')
  ) AS rows(reference, created_at, updated_at)
  UNION ALL
  SELECT
    '77777777-7777-7777-7777-777777777777'::uuid,
    reference,
    created_at::timestamptz,
    updated_at::timestamptz
  FROM (
    VALUES
      ('2025/02/17', '2025-02-17T14:00:00Z', '2025-02-17T14:35:00Z'),
      ('2025/02/18', '2025-02-18T09:10:00Z', '2025-02-18T09:55:00Z')
  ) AS rows(reference, created_at, updated_at)
),
upserted_conversations AS (
  INSERT INTO conversations (id, user_id, reference, created_at, updated_at)
  SELECT
    (
      substr(md5(format('%s:%s:conversation', user_id::text, reference)), 1, 8) || '-' ||
      substr(md5(format('%s:%s:conversation', user_id::text, reference)), 9, 4) || '-' ||
      substr(md5(format('%s:%s:conversation', user_id::text, reference)), 13, 4) || '-' ||
      substr(md5(format('%s:%s:conversation', user_id::text, reference)), 17, 4) || '-' ||
      substr(md5(format('%s:%s:conversation', user_id::text, reference)), 21, 12)
    )::uuid,
    user_id,
    reference,
    created_at,
    updated_at
  FROM conversation_seed
  ON CONFLICT (user_id, reference)
  DO UPDATE SET
    created_at = EXCLUDED.created_at,
    updated_at = EXCLUDED.updated_at
  RETURNING id, user_id, reference
),
message_rows AS (
  SELECT * FROM (
    VALUES
      -- Preserve original short seeded journal expected by tests.
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/01/14', 1, 'user', 'Can you summarize my notes from yesterday?'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/01/14', 2, 'assistant', 'You focused on migration planning and sketched three rollout steps.'),

      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/01/19', 1, 'user', 'I want Exobrain to become my daily architecture cockpit. Help me split goals into platform milestones.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/01/19', 2, 'assistant', 'Great direction. I suggest milestones for reliability, retrieval quality, and observability with explicit owner checklists.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/01/19', 3, 'user', 'For reliability, I need deterministic startup: infra check, migrations, then app boot.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/01/19', 4, 'assistant', 'Then encode that as scripts and CI gates so every environment follows the same order.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/01/19', 5, 'user', 'What should I monitor first in assistant-backend?'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/01/19', 6, 'assistant', 'Start with request latency, chat error rate, Redis session errors, and journal query timings.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/01/19', 7, 'user', 'Add a note: frontend pagination should default to 50 newest messages.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/01/19', 8, 'assistant', 'Noted. Keep the limit centralized in one constant and use cursor pagination for older history.'),

      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/03', 1, 'user', 'I am refactoring journal endpoints. Remind me why references use YYYY/MM/DD slash format.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/03', 2, 'assistant', 'Slash references make journals human-readable and naturally sortable; routes should use /{reference:path}.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/03', 3, 'user', 'And static routes must come before dynamic to avoid shadowing, right?'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/03', 4, 'assistant', 'Exactly. Keep /search and /today/messages declared before the dynamic reference route.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/03', 5, 'user', 'What belongs in frontend services vs routes?'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/03', 6, 'assistant', 'Routes stay thin; API/business flow goes in src/lib/services and persistence mechanics in src/lib/stores.'),

      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/11', 1, 'user', 'I plan to tighten docs. Which docs should I keep as index-first?'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/11', 2, 'assistant', 'Keep root README as index-first and move procedural setup into docs/development local setup guides.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/11', 3, 'user', 'Should logging defaults be verbose in production for debugging?'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/11', 4, 'assistant', 'Prefer conservative defaults like warn in production unless a task explicitly needs verbose telemetry.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/11', 5, 'user', 'Capture that in the frontend README and deployment notes.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/11', 6, 'assistant', 'Done conceptually: update app README and Helm/docker manifests together to avoid drift.'),

      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/16', 1, 'user', 'I want Exobrain to help me stage a zero-downtime schema rollout for assistant messages.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/16', 2, 'assistant', 'Use Reshape start/app rollout/complete and keep both schema versions readable during transition.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/16', 3, 'user', 'What is the safest way to backfill sequence cursors per conversation?'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/16', 4, 'assistant', 'Rank rows by created_at plus id per conversation with ROW_NUMBER and update only mismatched rows.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/16', 5, 'user', 'Should we keep a default sequence of 0 after migration?'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/16', 6, 'assistant', 'No. Drop that default to avoid invalid cursor values and enforce sequence assignment in application inserts.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/16', 7, 'user', 'I also want journal test data with short and long threads for pagination checks.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/16', 8, 'assistant', 'Seed mixed journal depths and include at least one conversation over 50 messages for load-older scenarios.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/16', 9, 'user', 'Great, include realistic architect-assistant prompts around roadmap, infra, and retrieval quality.'),
      ('11111111-1111-1111-1111-111111111111'::uuid, '2025/02/16', 10, 'assistant', 'Acknowledged. I will include strategy prompts, implementation details, and concise assistant summaries.'),

      ('77777777-7777-7777-7777-777777777777'::uuid, '2025/02/17', 1, 'user', 'I am architecting multi-agent orchestration. How should Exobrain split planner and executor duties?'),
      ('77777777-7777-7777-7777-777777777777'::uuid, '2025/02/17', 2, 'assistant', 'Use a planner for task decomposition and executors for bounded operations; keep shared state in explicit stores.'),
      ('77777777-7777-7777-7777-777777777777'::uuid, '2025/02/17', 3, 'user', 'And guardrails?'),
      ('77777777-7777-7777-7777-777777777777'::uuid, '2025/02/17', 4, 'assistant', 'Add scoped permissions, deterministic test fixtures, and mandatory citations for user-facing summaries.'),

      ('77777777-7777-7777-7777-777777777777'::uuid, '2025/02/18', 1, 'user', 'Give me a compact brief of Exobrain architecture layers for investor notes.'),
      ('77777777-7777-7777-7777-777777777777'::uuid, '2025/02/18', 2, 'assistant', 'Exobrain separates typed models, business services, state stores, and thin route handlers for fast iteration.'),
      ('77777777-7777-7777-7777-777777777777'::uuid, '2025/02/18', 3, 'user', 'Highlight reliability posture too.'),
      ('77777777-7777-7777-7777-777777777777'::uuid, '2025/02/18', 4, 'assistant', 'Reliability comes from scripted infra setup, migration checks, deterministic seeds, and integration smoke tests.'),
      ('77777777-7777-7777-7777-777777777777'::uuid, '2025/02/18', 5, 'user', 'Perfect, keep this style for future status reports.'),
      ('77777777-7777-7777-7777-777777777777'::uuid, '2025/02/18', 6, 'assistant', 'Will do. I can generate concise weekly summaries from journal history on demand.')
  ) AS manual_rows(user_id, reference, ord, role, content)
  UNION ALL
  -- Long journal (> 50 messages) to exercise frontend pagination and load-older controls.
  SELECT
    '11111111-1111-1111-1111-111111111111'::uuid AS user_id,
    '2025/02/18' AS reference,
    100 + gs AS ord,
    CASE WHEN gs % 2 = 1 THEN 'user' ELSE 'assistant' END AS role,
    CASE
      WHEN gs % 2 = 1 THEN format(
        'Roadmap checkpoint %s: I am prioritizing Exobrain milestone %s around %s. Keep this tied to shipping outcomes.',
        gs,
        ((gs + 1) / 2),
        (ARRAY['journal UX', 'assistant-backend reliability', 'schema migration safety', 'knowledge retrieval quality', 'observability dashboards'])[1 + (gs % 5)]
      )
      ELSE format(
        'Acknowledged checkpoint %s. Summary: lock scope, validate with tests, and capture rollout notes for Exobrain milestone %s.',
        gs,
        (gs / 2)
      )
    END AS content
  FROM generate_series(1, 70) AS gs
),
upserted_messages AS (
  INSERT INTO messages (
    id,
    conversation_id,
    user_id,
    role,
    content,
    sequence,
    client_message_id,
    created_at
  )
  SELECT
    (
      substr(md5(format('%s:%s:%s:message', m.user_id::text, m.reference, m.ord)), 1, 8) || '-' ||
      substr(md5(format('%s:%s:%s:message', m.user_id::text, m.reference, m.ord)), 9, 4) || '-' ||
      substr(md5(format('%s:%s:%s:message', m.user_id::text, m.reference, m.ord)), 13, 4) || '-' ||
      substr(md5(format('%s:%s:%s:message', m.user_id::text, m.reference, m.ord)), 17, 4) || '-' ||
      substr(md5(format('%s:%s:%s:message', m.user_id::text, m.reference, m.ord)), 21, 12)
    )::uuid AS id,
    c.id AS conversation_id,
    m.user_id,
    m.role,
    m.content,
    ROW_NUMBER() OVER (PARTITION BY m.user_id, m.reference ORDER BY m.ord)::int AS sequence,
    (
      substr(md5(format('%s:%s:%s:client', m.user_id::text, m.reference, m.ord)), 1, 8) || '-' ||
      substr(md5(format('%s:%s:%s:client', m.user_id::text, m.reference, m.ord)), 9, 4) || '-' ||
      substr(md5(format('%s:%s:%s:client', m.user_id::text, m.reference, m.ord)), 13, 4) || '-' ||
      substr(md5(format('%s:%s:%s:client', m.user_id::text, m.reference, m.ord)), 17, 4) || '-' ||
      substr(md5(format('%s:%s:%s:client', m.user_id::text, m.reference, m.ord)), 21, 12)
    )::uuid AS client_message_id,
    c.reference::date::timestamptz + make_interval(mins => (ROW_NUMBER() OVER (PARTITION BY m.user_id, m.reference ORDER BY m.ord))::int)
  FROM message_rows m
  INNER JOIN upserted_conversations c
    ON c.user_id = m.user_id
   AND c.reference = m.reference
  ON CONFLICT (conversation_id, client_message_id)
  DO UPDATE SET
    role = EXCLUDED.role,
    content = EXCLUDED.content,
    sequence = EXCLUDED.sequence,
    created_at = EXCLUDED.created_at
  RETURNING conversation_id
)
UPDATE conversations c
SET updated_at = latest.latest_message_at
FROM (
  SELECT conversation_id, MAX(created_at) AS latest_message_at
  FROM messages
  GROUP BY conversation_id
) latest
WHERE c.id = latest.conversation_id;
