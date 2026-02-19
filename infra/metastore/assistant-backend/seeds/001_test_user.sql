INSERT INTO users (id, name, email)
VALUES ('11111111-1111-1111-1111-111111111111', 'Test User', 'test.user@exobrain.local')
ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name;

INSERT INTO identities (user_id, provider, provider_subject, password_hash)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'local',
    'test.user@exobrain.local',
    'scrypt$keeIhNHyw8kYpVgiZ0WKLw==$_4Y41FPbaIW85m5RS5EAYjjlpNJSzN01ORmIMwR98GdvhbjU429CavOWdedS4y8hsFeqBoBPDe36n4Z8Vsswpw=='
)
ON CONFLICT (provider, provider_subject)
DO UPDATE SET password_hash = EXCLUDED.password_hash;

WITH seeded_conversation AS (
    INSERT INTO conversations (id, user_id, reference)
    VALUES (
        '22222222-2222-2222-2222-222222222222',
        '11111111-1111-1111-1111-111111111111',
        '2025/01/14'
    )
    ON CONFLICT (user_id, reference) DO UPDATE SET updated_at = NOW()
    RETURNING id
)
INSERT INTO messages (id, conversation_id, user_id, role, content, client_message_id)
VALUES
    (
        '33333333-3333-3333-3333-333333333333',
        COALESCE((SELECT id FROM seeded_conversation), (SELECT id FROM conversations WHERE user_id = '11111111-1111-1111-1111-111111111111' AND reference = '2025/01/14')),
        '11111111-1111-1111-1111-111111111111',
        'user',
        'Can you summarize my notes from yesterday?',
        '44444444-4444-4444-4444-444444444444'
    ),
    (
        '55555555-5555-5555-5555-555555555555',
        COALESCE((SELECT id FROM seeded_conversation), (SELECT id FROM conversations WHERE user_id = '11111111-1111-1111-1111-111111111111' AND reference = '2025/01/14')),
        '11111111-1111-1111-1111-111111111111',
        'assistant',
        'You focused on migration planning and sketched three rollout steps.',
        '66666666-6666-6666-6666-666666666666'
    )
ON CONFLICT (conversation_id, client_message_id)
DO UPDATE SET content = EXCLUDED.content;
