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
