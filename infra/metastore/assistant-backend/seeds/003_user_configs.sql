WITH upsert_definition AS (
  INSERT INTO user_config_definitions (
    key,
    name,
    description,
    config_type,
    default_value,
    display_order,
    is_active,
    updated_at
  )
  VALUES (
    'frontend.theme',
    'Theme',
    'Select the assistant frontend theme',
    'choice',
    '{"kind":"choice","value":"gruvbox-dark"}'::jsonb,
    10,
    TRUE,
    NOW()
  )
  ON CONFLICT (key)
  DO UPDATE SET
    description = EXCLUDED.description,
    name = EXCLUDED.name,
    config_type = EXCLUDED.config_type,
    default_value = EXCLUDED.default_value,
    display_order = EXCLUDED.display_order,
    is_active = EXCLUDED.is_active,
    updated_at = NOW()
  RETURNING id
), definition AS (
  SELECT id FROM upsert_definition
  UNION ALL
  SELECT id FROM user_config_definitions WHERE key = 'frontend.theme'
  LIMIT 1
)
INSERT INTO user_config_choice_options (definition_id, option_value, option_label, display_order, is_active)
SELECT definition.id, v.option_value, v.option_label, v.display_order, TRUE
FROM definition
JOIN (
  VALUES
    ('gruvbox-dark', 'Gruvbox Dark', 10),
    ('purple-intelligence', 'Purple Intelligence', 20)
) AS v(option_value, option_label, display_order)
  ON TRUE
ON CONFLICT (definition_id, option_value)
DO UPDATE SET
  option_label = EXCLUDED.option_label,
  display_order = EXCLUDED.display_order,
  is_active = EXCLUDED.is_active;
