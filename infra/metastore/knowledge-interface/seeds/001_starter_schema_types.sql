INSERT INTO knowledge_graph_schema_types (id, kind, name, description, active, universe_id)
VALUES
  ('node', 'node', 'Node', 'Abstract base type whose properties apply to all node types.', TRUE, NULL),
  ('node.universe', 'node', 'Universe', 'Top-level world scope that groups entities into a coherent setting.', TRUE, NULL),
  ('node.entity', 'node', 'Entity', 'Base world-model node for people, places, things, events, and concepts.', TRUE, NULL),
  ('node.person', 'node', 'Person', 'A person entity representing an individual actor in the world model.', TRUE, NULL),
  ('node.group', 'node', 'Group', 'A social or organizational group such as a faction, family, or team.', TRUE, NULL),
  ('node.institution', 'node', 'Institution', 'A formal organization such as a company, school, guild, or government.', TRUE, NULL),
  ('node.place', 'node', 'Place', 'A location node for rooms, buildings, cities, regions, and other places.', TRUE, NULL),
  ('node.country', 'node', 'Country', 'A place subtype representing countries and sovereign states.', TRUE, NULL),
  ('node.city', 'node', 'City', 'A place subtype representing cities and metropolitan areas.', TRUE, NULL),
  ('node.object', 'node', 'Object', 'A tangible object, item, artifact, or household thing.', TRUE, NULL),
  ('node.concept', 'node', 'Concept', 'An abstract concept, topic, theme, skill, or mechanic.', TRUE, NULL),
  ('node.species', 'node', 'Species', 'A species or taxonomy-like concept used in fiction, games, or real-world biology.', TRUE, NULL),
  ('node.event', 'node', 'Event', 'A time-bound occurrence with optional start and end timestamps.', TRUE, NULL),
  ('node.recurring_event', 'node', 'Recurring Event', 'An event pattern that recurs over time and is defined by a canonical recurrence rule.', TRUE, NULL),
  ('node.task', 'node', 'Task', 'An intended or actionable event that may include a due time.', TRUE, NULL),
  ('node.message', 'node', 'Message', 'A communication event exchanged between participants.', TRUE, NULL),
  ('node.chat_message', 'node', 'Chat Message', 'A conversational message event exchanged within a chat thread.', TRUE, NULL),
  ('node.ai_agent', 'node', 'AI Agent', 'A person subtype representing a software-based autonomous agent.', TRUE, NULL),
  ('node.document', 'node', 'Document', 'An entity representing a document artifact described by a block tree.', TRUE, NULL),
  ('node.note', 'node', 'Note', 'A concise document used for captured thoughts, observations, or working memory.', TRUE, NULL),
  ('node.report', 'node', 'Report', 'A structured document intended to communicate findings, analysis, or status.', TRUE, NULL),
  ('node.company', 'node', 'Company', 'An institution subtype for businesses and other commercial organizations.', TRUE, NULL),
  ('node.rule', 'node', 'Rule', 'A concept subtype representing a normative or operational rule that can apply to entities.', TRUE, NULL),
  ('node.block', 'node', 'Block', 'A content-bearing narrative block used to describe entities.', TRUE, NULL),
  ('node.quote', 'node', 'Quote', 'A block subtype representing quoted speech or text.', TRUE, NULL),
  ('edge', 'edge', 'Edge', 'Abstract base type whose properties apply to all edge types.', TRUE, NULL),
  ('edge.is_part_of', 'edge', 'IS_PART_OF', 'Connects an entity to the single universe it belongs to.', TRUE, NULL),
  ('edge.described_by', 'edge', 'DESCRIBED_BY', 'Connects an entity to its root intro block.', TRUE, NULL),
  ('edge.summarizes', 'edge', 'SUMMARIZES', 'Connects a summary block to a deeper detail block.', TRUE, NULL),
  ('edge.mentions', 'edge', 'MENTIONS', 'Connects a block to an entity referenced in that block.', TRUE, NULL),
  ('edge.quoted_person', 'edge', 'QUOTED_PERSON', 'Connects a quote block to the person who is quoted.', TRUE, NULL),
  ('edge.related_to', 'edge', 'RELATED_TO', 'Generic relation fallback used when a specific edge type is unavailable.', TRUE, NULL),
  ('edge.located_at', 'edge', 'LOCATED_AT', 'Connects an event, task, or message to the place where it occurs.', TRUE, NULL),
  ('edge.lies_in', 'edge', 'LIES_IN', 'Place hierarchy relation such as room in building or city in region.', TRUE, NULL),
  ('edge.contains', 'edge', 'CONTAINS', 'Containment relation for inventories, rooms, and nested objects.', TRUE, NULL),
  ('edge.knows', 'edge', 'KNOWS', 'Social relation indicating one person knows another.', TRUE, NULL),
  ('edge.partner_of', 'edge', 'PARTNER_OF', 'Mutual partner relation connecting two people.', TRUE, NULL),
  ('edge.member_of', 'edge', 'MEMBER_OF', 'Membership relation connecting a person to a group.', TRUE, NULL),
  ('edge.affiliated_with', 'edge', 'AFFILIATED_WITH', 'Affiliation relation connecting a person to an institution.', TRUE, NULL),
  ('edge.participated_in', 'edge', 'PARTICIPATED_IN', 'Participation relation connecting a person to an event.', TRUE, NULL),
  ('edge.involves', 'edge', 'INVOLVES', 'Relation connecting an event to any involved entity.', TRUE, NULL),
  ('edge.causes', 'edge', 'CAUSES', 'Causal relation between two events.', TRUE, NULL),
  ('edge.assigned_to', 'edge', 'ASSIGNED_TO', 'Task assignment relation from task to person.', TRUE, NULL),
  ('edge.done_for', 'edge', 'DONE_FOR', 'Task beneficiary relation from task to related entity.', TRUE, NULL),
  ('edge.depends_on', 'edge', 'DEPENDS_ON', 'Task dependency relation from task to prerequisite task.', TRUE, NULL),
  ('edge.sent_to', 'edge', 'SENT_TO', 'Message recipient relation from message to person.', TRUE, NULL),
  ('edge.sent_by', 'edge', 'SENT_BY', 'Message sender relation from message to person.', TRUE, NULL),
  ('edge.about', 'edge', 'ABOUT', 'Classification relation linking entities to concepts they are about.', TRUE, NULL),
  ('edge.instance_of', 'edge', 'INSTANCE_OF', 'Classification relation linking entities to concept classes.', TRUE, NULL),
  ('edge.also_known_as', 'edge', 'ALSO_KNOWN_AS', 'Alias relation for alternative names and identities.', TRUE, NULL),
  ('edge.same_as', 'edge', 'SAME_AS', 'Strong identity equivalence relation for deduplication.', TRUE, NULL),
  ('edge.contradicts', 'edge', 'CONTRADICTS', 'Connects one block to another block that it contradicts.', TRUE, NULL),
  ('edge.authored', 'edge', 'AUTHORED', 'Authorship relation linking an entity author to a document.', TRUE, NULL),
  ('edge.owns', 'edge', 'OWNS', 'Ownership relation linking an entity owner to an owned entity.', TRUE, NULL),
  ('edge.applies_to', 'edge', 'APPLIES_TO', 'Applicability relation linking a rule-like concept to relevant entities.', TRUE, NULL)
ON CONFLICT (id) DO UPDATE
SET
  kind = EXCLUDED.kind,
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  active = EXCLUDED.active,
  universe_id = EXCLUDED.universe_id,
  updated_at = NOW();

UPDATE knowledge_graph_schema_types
SET active = FALSE, updated_at = NOW()
WHERE id IN ('node.image', 'block.image', 'block.default', 'block.quote', 'edge.at', 'edge.before')
   OR kind = 'block';

UPDATE knowledge_graph_schema_type_inheritance
SET active = FALSE
WHERE child_type_id = 'node.species' AND parent_type_id = 'node.entity';

INSERT INTO knowledge_graph_schema_type_inheritance (child_type_id, parent_type_id, active, description, universe_id)
VALUES
  ('node.person', 'node.entity', TRUE, 'Person is a subtype of Entity for human actors.', NULL),
  ('node.group', 'node.entity', TRUE, 'Group is a subtype of Entity for collective actors.', NULL),
  ('node.institution', 'node.entity', TRUE, 'Institution is a subtype of Entity for formal organizations.', NULL),
  ('node.place', 'node.entity', TRUE, 'Place is a subtype of Entity for location-like nodes.', NULL),
  ('node.country', 'node.place', TRUE, 'Country is a subtype of Place for sovereign regions.', NULL),
  ('node.city', 'node.place', TRUE, 'City is a subtype of Place for urban settlements.', NULL),
  ('node.object', 'node.entity', TRUE, 'Object is a subtype of Entity for physical items.', NULL),
  ('node.concept', 'node.entity', TRUE, 'Concept is a subtype of Entity for abstract topics.', NULL),
  ('node.species', 'node.entity', FALSE, 'Species no longer directly inherits Entity; use Concept inheritance.', NULL),
  ('node.event', 'node.entity', TRUE, 'Event is a subtype of Entity for time-bound occurrences.', NULL),
  ('node.document', 'node.entity', TRUE, 'Document is a direct subtype of Entity for document artifacts.', NULL),
  ('node.task', 'node.event', TRUE, 'Task is a subtype of Event that adds due-date intent.', NULL),
  ('node.recurring_event', 'node.event', TRUE, 'Recurring Event is a subtype of Event defined by a recurrence rule.', NULL),
  ('node.message', 'node.event', TRUE, 'Message is a subtype of Event for participant communication.', NULL),
  ('node.chat_message', 'node.message', TRUE, 'Chat Message is a subtype of Message for threaded conversations.', NULL),
  ('node.ai_agent', 'node.person', TRUE, 'AI Agent is a subtype of Person for autonomous software actors.', NULL),
  ('node.company', 'node.institution', TRUE, 'Company is a subtype of Institution for commercial organizations.', NULL),
  ('node.rule', 'node.concept', TRUE, 'Rule is a subtype of Concept for normative statements.', NULL),
  ('node.note', 'node.document', TRUE, 'Note is a subtype of Document for concise textual artifacts.', NULL),
  ('node.report', 'node.document', TRUE, 'Report is a subtype of Document for structured findings.', NULL),
  ('node.species', 'node.concept', TRUE, 'Species is a subtype of Concept for taxonomy-like classes.', NULL),
  ('node.quote', 'node.block', TRUE, 'Quote is a subtype of Block for attributed quotations.', NULL)
ON CONFLICT (child_type_id, parent_type_id) DO UPDATE
SET
  active = EXCLUDED.active,
  description = EXCLUDED.description,
  universe_id = EXCLUDED.universe_id;

INSERT INTO knowledge_graph_schema_type_properties (
  owner_type_id, prop_name, value_type, required, readable, writable, active, description, enum_values, pattern, numeric_min, numeric_max, universe_id
)
VALUES
  ('node.entity', 'id', 'string', TRUE, TRUE, FALSE, TRUE, 'Stable global identifier for the entity; should never be rewritten by ingestion clients.', NULL, NULL, NULL, NULL, NULL),
  ('node.entity', 'name', 'string', TRUE, TRUE, TRUE, TRUE, 'Human-readable canonical display name for the entity.', NULL, NULL, NULL, NULL, NULL),
  ('node.entity', 'aliases', 'json', FALSE, TRUE, TRUE, TRUE, 'Optional array of alternative names for the entity.', NULL, NULL, NULL, NULL, NULL),
  ('node.universe', 'id', 'string', TRUE, TRUE, FALSE, TRUE, 'Stable global identifier for the universe scope.', NULL, NULL, NULL, NULL, NULL),
  ('node.universe', 'name', 'string', TRUE, TRUE, TRUE, TRUE, 'Human-readable name of the universe scope.', NULL, NULL, NULL, NULL, NULL),
  ('node.universe', 'aliases', 'json', FALSE, TRUE, TRUE, TRUE, 'Optional array of alternative human-readable names for the universe.', NULL, NULL, NULL, NULL, NULL),
  ('node.event', 'start', 'datetime', FALSE, TRUE, TRUE, TRUE, 'Optional event start time used for chronology and temporal filtering.', NULL, NULL, NULL, NULL, NULL),
  ('node.event', 'end', 'datetime', FALSE, TRUE, TRUE, TRUE, 'Optional event end time used for duration and sequencing hints.', NULL, NULL, NULL, NULL, NULL),
  ('node.recurring_event', 'recurrence_rule', 'string', TRUE, TRUE, TRUE, TRUE, 'Canonical recurrence rule (RFC 5545 RRULE style) used as the recurrence source of truth.', NULL, NULL, NULL, NULL, NULL),
  ('node.recurring_event', 'recurrence_exceptions', 'json', FALSE, TRUE, TRUE, TRUE, 'Optional list of excluded occurrence timestamps.', NULL, NULL, NULL, NULL, NULL),
  ('node.task', 'due', 'datetime', FALSE, TRUE, TRUE, TRUE, 'Optional task due timestamp indicating intended completion time.', NULL, NULL, NULL, NULL, NULL),
  ('node.person', 'email', 'string', FALSE, TRUE, TRUE, TRUE, 'Optional email address for contactable real-world people.', NULL, NULL, NULL, NULL, NULL),
  ('node.person', 'phone', 'string', FALSE, TRUE, TRUE, TRUE, 'Optional phone number for contactable real-world people.', NULL, NULL, NULL, NULL, NULL),
  ('node.person', 'role', 'string', FALSE, TRUE, TRUE, TRUE, 'Optional role or title describing the person in context.', NULL, NULL, NULL, NULL, NULL),
  ('node.document', 'genre', 'string', FALSE, TRUE, TRUE, TRUE, 'Optional genre or category label for a document artifact.', NULL, NULL, NULL, NULL, NULL),
  ('node.document', 'source_uri', 'string', FALSE, TRUE, TRUE, TRUE, 'Optional URI or canonical source reference for the document artifact.', NULL, NULL, NULL, NULL, NULL),
  ('node.document', 'published_at', 'datetime', FALSE, TRUE, TRUE, TRUE, 'Optional publication timestamp for the document artifact.', NULL, NULL, NULL, NULL, NULL),
  ('node.place', 'lat', 'float', FALSE, TRUE, TRUE, TRUE, 'Optional latitude for geospatially anchored places.', NULL, NULL, -90, 90, NULL),
  ('node.place', 'lon', 'float', FALSE, TRUE, TRUE, TRUE, 'Optional longitude for geospatially anchored places.', NULL, NULL, -180, 180, NULL),
  ('node.block', 'id', 'string', TRUE, TRUE, FALSE, TRUE, 'Stable global identifier for the block node.', NULL, NULL, NULL, NULL, NULL),
  ('node.block', 'text', 'string', TRUE, TRUE, TRUE, TRUE, 'Primary content text for the block used for reading and embeddings.', NULL, NULL, NULL, NULL, NULL),
  ('edge', 'confidence', 'float', TRUE, TRUE, TRUE, TRUE, 'Required confidence score from 0.0 to 1.0 representing trust in this relation.', NULL, NULL, 0, 1, NULL),
  ('edge', 'status', 'string', TRUE, TRUE, TRUE, TRUE, 'Required truth status of the relation.', 'asserted|disputed|falsified', NULL, NULL, NULL, NULL),
  ('edge', 'provenance_hint', 'string', TRUE, TRUE, TRUE, TRUE, 'Required provenance hint describing where the relation came from.', NULL, NULL, NULL, NULL, NULL),
  ('edge', 'valid_from', 'datetime', FALSE, TRUE, TRUE, TRUE, 'Optional timestamp from which this relation is valid.', NULL, NULL, NULL, NULL, NULL),
  ('edge', 'valid_to', 'datetime', FALSE, TRUE, TRUE, TRUE, 'Optional timestamp until which this relation is valid.', NULL, NULL, NULL, NULL, NULL)
ON CONFLICT (owner_type_id, prop_name) DO UPDATE
SET
  value_type = EXCLUDED.value_type,
  required = EXCLUDED.required,
  readable = EXCLUDED.readable,
  writable = EXCLUDED.writable,
  active = EXCLUDED.active,
  description = EXCLUDED.description,
  enum_values = EXCLUDED.enum_values,
  pattern = EXCLUDED.pattern,
  numeric_min = EXCLUDED.numeric_min,
  numeric_max = EXCLUDED.numeric_max,
  universe_id = EXCLUDED.universe_id;

INSERT INTO knowledge_graph_schema_edge_rules (edge_type_id, from_node_type_id, to_node_type_id, active, description, universe_id)
VALUES
  ('edge.is_part_of', 'node.entity', 'node.universe', TRUE, 'Each entity should point to exactly one universe via IS_PART_OF.', NULL),
  ('edge.described_by', 'node.entity', 'node.block', TRUE, 'Each entity should point to exactly one root block via DESCRIBED_BY.', NULL),
  ('edge.described_by', 'node.universe', 'node.block', TRUE, 'A universe may point to at most one root block via DESCRIBED_BY.', NULL),
  ('edge.summarizes', 'node.block', 'node.block', TRUE, 'Summary blocks point to deeper detail blocks; no cycles should be introduced.', NULL),
  ('edge.mentions', 'node.block', 'node.entity', TRUE, 'Blocks mention entities referenced in their text.', NULL),
  ('edge.quoted_person', 'node.quote', 'node.person', TRUE, 'Quote blocks can attribute quoted text to a person.', NULL),
  ('edge.located_at', 'node.event', 'node.place', TRUE, 'Events can be located at places.', NULL),
  ('edge.located_at', 'node.task', 'node.place', TRUE, 'Tasks can be located at places.', NULL),
  ('edge.located_at', 'node.message', 'node.place', TRUE, 'Messages can be located at places.', NULL),
  ('edge.lies_in', 'node.place', 'node.place', TRUE, 'Places may nest within other places.', NULL),
  ('edge.contains', 'node.entity', 'node.entity', TRUE, 'Containment relation between two entity subtypes.', NULL),
  ('edge.knows', 'node.person', 'node.person', TRUE, 'People may know other people.', NULL),
  ('edge.partner_of', 'node.person', 'node.person', TRUE, 'People may have a partner relationship with each other.', NULL),
  ('edge.participated_in', 'node.person', 'node.event', TRUE, 'People may participate in events.', NULL),
  ('edge.involves', 'node.event', 'node.entity', TRUE, 'Events may involve any entity subtype.', NULL),
  ('edge.causes', 'node.event', 'node.event', TRUE, 'Events may causally influence other events.', NULL),
  ('edge.assigned_to', 'node.task', 'node.person', TRUE, 'Tasks may be assigned to people.', NULL),
  ('edge.done_for', 'node.task', 'node.entity', TRUE, 'Tasks may be completed for an entity beneficiary.', NULL),
  ('edge.sent_to', 'node.message', 'node.person', TRUE, 'Messages may target recipient people.', NULL),
  ('edge.sent_by', 'node.message', 'node.person', TRUE, 'Messages may identify sender people.', NULL),
  ('edge.member_of', 'node.person', 'node.group', TRUE, 'People may belong to groups.', NULL),
  ('edge.affiliated_with', 'node.person', 'node.institution', TRUE, 'People may affiliate with institutions.', NULL),
  ('edge.depends_on', 'node.task', 'node.task', TRUE, 'Tasks may depend on other tasks.', NULL),
  ('edge.about', 'node.entity', 'node.concept', TRUE, 'Entities may be about concepts.', NULL),
  ('edge.instance_of', 'node.entity', 'node.concept', TRUE, 'Entities may be instances of concept classes.', NULL),
  ('edge.also_known_as', 'node.entity', 'node.entity', TRUE, 'Entities may have alternative identities.', NULL),
  ('edge.same_as', 'node.entity', 'node.entity', TRUE, 'Entities may have strong identity equivalence.', NULL),
  ('edge.contradicts', 'node.block', 'node.block', TRUE, 'Blocks may contradict other blocks.', NULL),
  ('edge.related_to', 'node.entity', 'node.entity', TRUE, 'Generic relation between any two entity subtypes.', NULL),
  ('edge.authored', 'node.entity', 'node.document', TRUE, 'Entity authors can be linked to authored document entities.', NULL),
  ('edge.owns', 'node.entity', 'node.entity', TRUE, 'Entities may own other entities.', NULL),
  ('edge.applies_to', 'node.rule', 'node.entity', TRUE, 'Rules may apply to any entity subtype.', NULL)
ON CONFLICT (edge_type_id, from_node_type_id, to_node_type_id) DO UPDATE
SET
  active = EXCLUDED.active,
  description = EXCLUDED.description,
  universe_id = EXCLUDED.universe_id;
