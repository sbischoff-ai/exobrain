use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use anyhow::{anyhow, Result};

#[cfg(test)]
use crate::domain::EmbeddedBlock;

use crate::{
    domain::{
        BlockNode, EntityNode, ExistingBlockContext, ExtractionUniverse, FindEntityCandidatesQuery,
        FindEntityCandidatesResult, FullSchema, GetEntityContextQuery, GetEntityContextResult,
        GraphDelta, GraphEdge, ListEntitiesByTypeQuery, ListEntitiesByTypeResult, PropertyScalar,
        PropertyValue, SchemaKind, SchemaType, TypeId, UniverseNode, UpsertSchemaTypeCommand,
        UserInitGraphNodeIds, Visibility,
    },
    ports::{Embedder, GraphRepository, SchemaRepository},
};

pub mod use_cases;

pub(crate) use use_cases::extraction_schema::{
    build_entity_type_property_context, build_extraction_edge_types_from_input,
    build_extraction_entity_types_from_input, EntityTypePropertyContext,
    EntityTypePropertyContextOptions, ExtractionEdgeType, ExtractionEntityType,
    ExtractionPropertyContext, ExtractionSchemaBuildInput, ExtractionSchemaOptions,
    ExtractionUniverseContext,
};

const EXOBRAIN_USER_ID: &str = "exobrain";
const COMMON_UNIVERSE_ID: &str = "9d7f0fa5-78c1-4805-9efb-3f8f16090d7f";
const COMMON_UNIVERSE_NAME: &str = "Real World";
const COMMON_EXOBRAIN_ENTITY_ID: &str = "8c75cc89-6204-4fed-aec1-34d032ff95ee";
const COMMON_EXOBRAIN_BLOCK_ID: &str = "ea5ca80f-346b-4f66-bff2-d307ce5d7da9";
const LIST_ENTITIES_BY_TYPE_DEFAULT_PAGE_SIZE: u32 = 50;
const LIST_ENTITIES_BY_TYPE_MAX_PAGE_SIZE: u32 = 200;
pub struct KnowledgeApplication {
    schema_repository: Arc<dyn SchemaRepository>,
    graph_repository: Arc<dyn GraphRepository>,
    embedder: Arc<dyn Embedder>,
}

impl KnowledgeApplication {
    pub fn new(
        schema_repository: Arc<dyn SchemaRepository>,
        graph_repository: Arc<dyn GraphRepository>,
        embedder: Arc<dyn Embedder>,
    ) -> Self {
        Self {
            schema_repository,
            graph_repository,
            embedder,
        }
    }

    pub async fn get_schema(&self) -> Result<FullSchema> {
        let node_types = self.schema_repository.get_by_kind(SchemaKind::Node).await?;
        let edge_types = self.schema_repository.get_by_kind(SchemaKind::Edge).await?;
        let inheritance = self.schema_repository.get_type_inheritance().await?;
        let properties = self.schema_repository.get_all_properties().await?;
        let edge_rules = self.schema_repository.get_edge_endpoint_rules().await?;

        let hydrated_nodes = node_types
            .into_iter()
            .map(|schema_type| {
                let node_id = schema_type.id.clone();
                let type_properties = properties
                    .iter()
                    .filter(|p| {
                        p.owner_type_id == node_id
                            || is_global_property_owner(&node_id, &p.owner_type_id)
                    })
                    .cloned()
                    .collect();
                let parents = inheritance
                    .iter()
                    .filter(|i| i.child_type_id == node_id)
                    .cloned()
                    .collect();

                crate::domain::SchemaNodeTypeHydrated {
                    schema_type,
                    properties: type_properties,
                    parents,
                }
            })
            .collect();

        let hydrated_edges = edge_types
            .into_iter()
            .map(|schema_type| {
                let edge_id = schema_type.id.clone();
                let type_properties = properties
                    .iter()
                    .filter(|p| {
                        p.owner_type_id == edge_id
                            || is_global_property_owner(&edge_id, &p.owner_type_id)
                    })
                    .cloned()
                    .collect();
                let rules = edge_rules
                    .iter()
                    .filter(|r| r.edge_type_id == edge_id)
                    .cloned()
                    .collect();

                crate::domain::SchemaEdgeTypeHydrated {
                    schema_type,
                    properties: type_properties,
                    rules,
                }
            })
            .collect();

        Ok(FullSchema {
            node_types: hydrated_nodes,
            edge_types: hydrated_edges,
        })
    }

    pub async fn get_entity_extraction_schema_types(
        &self,
        options: ExtractionSchemaOptions,
    ) -> Result<Vec<ExtractionEntityType>> {
        let node_types = self.schema_repository.get_by_kind(SchemaKind::Node).await?;
        let inheritance = self.schema_repository.get_type_inheritance().await?;

        Ok(build_extraction_entity_types_from_input(
            ExtractionSchemaBuildInput {
                node_types,
                edge_types: Vec::new(),
                inheritance,
                edge_rules: Vec::new(),
            },
            options,
        ))
    }

    pub async fn get_edge_extraction_schema_types(
        &self,
        first_entity_type: &str,
        second_entity_type: &str,
        options: ExtractionSchemaOptions,
    ) -> Result<Vec<ExtractionEdgeType>> {
        let node_types = self.schema_repository.get_by_kind(SchemaKind::Node).await?;
        let edge_types = self.schema_repository.get_by_kind(SchemaKind::Edge).await?;
        let inheritance = self.schema_repository.get_type_inheritance().await?;
        let edge_rules = self.schema_repository.get_edge_endpoint_rules().await?;

        Ok(build_extraction_edge_types_from_input(
            ExtractionSchemaBuildInput {
                node_types,
                edge_types,
                inheritance,
                edge_rules,
            },
            first_entity_type,
            second_entity_type,
            options,
        ))
    }

    pub async fn get_extraction_universes(
        &self,
        user_id: &str,
    ) -> Result<Vec<ExtractionUniverseContext>> {
        let trimmed_user_id = user_id.trim();
        if trimmed_user_id.is_empty() {
            return Err(anyhow!("user_id is required"));
        }

        let mut universes = self
            .graph_repository
            .get_extraction_universes(trimmed_user_id)
            .await?
            .into_iter()
            .map(|universe: ExtractionUniverse| ExtractionUniverseContext {
                id: universe.id,
                name: universe.name,
                described_by_text: universe.described_by_text,
            })
            .collect::<Vec<_>>();
        universes.sort_by(|a, b| a.id.cmp(&b.id));
        Ok(universes)
    }

    pub async fn get_entity_type_property_context(
        &self,
        type_id: &str,
        options: EntityTypePropertyContextOptions,
    ) -> Result<EntityTypePropertyContext> {
        let schema = self.get_schema().await?;
        build_entity_type_property_context(schema, type_id, options)
    }

    pub async fn upsert_schema_type(&self, command: UpsertSchemaTypeCommand) -> Result<SchemaType> {
        let schema_type = command.schema_type;

        let schema_kind = schema_type
            .schema_kind()
            .ok_or_else(|| anyhow!("schema kind must be one of: node, edge"))?;

        if matches!(schema_kind, SchemaKind::Edge) && command.parent_type_id.is_some() {
            return Err(anyhow!("edge inheritance is out of scope"));
        }

        if matches!(schema_kind, SchemaKind::Node) {
            if schema_type.id == "node.entity" {
                if command.parent_type_id.is_some() {
                    return Err(anyhow!("node.entity cannot declare a parent"));
                }
            } else {
                let parent_type_id = command.parent_type_id.clone().ok_or_else(|| {
                    anyhow!("node types (except node.entity) must declare parent_type_id")
                })?;

                let parent_schema = self
                    .schema_repository
                    .get_schema_type(&parent_type_id)
                    .await?
                    .ok_or_else(|| anyhow!("parent type does not exist"))?;

                if !matches!(parent_schema.schema_kind(), Some(SchemaKind::Node)) {
                    return Err(anyhow!("parent type must be a node"));
                }

                if !self
                    .schema_repository
                    .is_descendant_of_entity(&parent_type_id)
                    .await?
                {
                    return Err(anyhow!("node parent must descend from node.entity"));
                }

                if let Some(existing_parent) = self
                    .schema_repository
                    .get_parent_for_child(&schema_type.id)
                    .await?
                {
                    if existing_parent != parent_type_id {
                        return Err(anyhow!("a node type cannot have multiple parents"));
                    }
                }
            }
        }

        let upserted = self.schema_repository.upsert(&schema_type).await?;

        if matches!(upserted.schema_kind(), Some(SchemaKind::Node)) && upserted.id != "node.entity"
        {
            let parent = command
                .parent_type_id
                .as_ref()
                .ok_or_else(|| anyhow!("parent_type_id required for node subtype"))?;
            self.schema_repository
                .upsert_inheritance(
                    &upserted.id,
                    parent,
                    "Parent relation created via UpsertSchemaType",
                )
                .await?;
        }

        for property in &command.properties {
            self.schema_repository
                .upsert_type_property(&upserted.id, property)
                .await?;
        }

        Ok(upserted)
    }

    pub async fn ensure_common_root_graph(&self) -> Result<()> {
        if self.graph_repository.common_root_graph_exists().await? {
            return Ok(());
        }

        self.upsert_graph_delta(Self::common_root_delta()).await
    }

    pub async fn get_user_init_graph(
        &self,
        user_id: &str,
        user_name: &str,
    ) -> Result<UserInitGraphNodeIds> {
        let trimmed_user_id = user_id.trim();
        if trimmed_user_id.is_empty() {
            return Err(anyhow!("user_id is required"));
        }

        let trimmed_user_name = user_name.trim();
        if trimmed_user_name.is_empty() {
            return Err(anyhow!("user_name is required"));
        }

        if self
            .graph_repository
            .user_graph_needs_initialization(trimmed_user_id)
            .await?
        {
            let delta = Self::user_init_delta(trimmed_user_id, trimmed_user_name);
            let node_ids = Self::user_init_graph_node_ids(&delta)?;
            self.apply_user_initialization_delta(trimmed_user_id, delta, &node_ids)
                .await?;
            return Ok(node_ids);
        }

        let node_ids = self
            .graph_repository
            .get_user_init_graph_node_ids(trimmed_user_id)
            .await?
            .ok_or_else(|| anyhow!("user graph marker missing node ids"))?;

        self.graph_repository
            .update_person_name(&node_ids.person_entity_id, trimmed_user_name)
            .await?;

        Ok(node_ids)
    }

    fn common_root_delta() -> GraphDelta {
        GraphDelta {
            universes: vec![UniverseNode {
                id: COMMON_UNIVERSE_ID.to_string(),
                name: COMMON_UNIVERSE_NAME.to_string(),
                user_id: EXOBRAIN_USER_ID.to_string(),
                visibility: Visibility::Shared,
            }],
            entities: vec![EntityNode {
                id: COMMON_EXOBRAIN_ENTITY_ID.to_string(),
                type_id: "node.concept".to_string(),
                universe_id: Some(COMMON_UNIVERSE_ID.to_string()),
                user_id: EXOBRAIN_USER_ID.to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Exobrain".to_string()),
                }],
                resolved_labels: vec![],
            }],
            blocks: vec![BlockNode {
                id: COMMON_EXOBRAIN_BLOCK_ID.to_string(),
                type_id: "node.block".to_string(),
                user_id: EXOBRAIN_USER_ID.to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Exobrain is the shared platform for capturing and organizing knowledge, powering assistants and knowledge workflows.".to_string()),
                }],
                resolved_labels: vec![],
            }],
            edges: vec![
                GraphEdge {
                    from_id: COMMON_EXOBRAIN_ENTITY_ID.to_string(),
                    to_id: COMMON_UNIVERSE_ID.to_string(),
                    edge_type: "IS_PART_OF".to_string(),
                    user_id: EXOBRAIN_USER_ID.to_string(),
                    visibility: Visibility::Shared,
                    properties: default_edge_properties("bootstrap universe assignment"),
                },
                GraphEdge {
                    from_id: COMMON_EXOBRAIN_ENTITY_ID.to_string(),
                    to_id: COMMON_EXOBRAIN_BLOCK_ID.to_string(),
                    edge_type: "DESCRIBED_BY".to_string(),
                    user_id: EXOBRAIN_USER_ID.to_string(),
                    visibility: Visibility::Shared,
                    properties: default_edge_properties("bootstrap description link"),
                },
            ],
        }
    }

    fn user_init_delta(user_id: &str, user_name: &str) -> GraphDelta {
        let person_entity_id = uuid::Uuid::new_v5(
            &uuid::Uuid::NAMESPACE_OID,
            format!("person:{user_id}").as_bytes(),
        )
        .to_string();
        let assistant_entity_id = uuid::Uuid::new_v5(
            &uuid::Uuid::NAMESPACE_OID,
            format!("assistant:{user_id}").as_bytes(),
        )
        .to_string();
        let assistant_block_id = uuid::Uuid::new_v5(
            &uuid::Uuid::NAMESPACE_OID,
            format!("assistant-block:{user_id}").as_bytes(),
        )
        .to_string();

        GraphDelta {
            universes: vec![],
            entities: vec![
                EntityNode {
                    id: person_entity_id.clone(),
                    type_id: "node.person".to_string(),
                    universe_id: Some(COMMON_UNIVERSE_ID.to_string()),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: vec![
                        PropertyValue {
                            key: "name".to_string(),
                            value: PropertyScalar::String(user_name.to_string()),
                        },
                        PropertyValue {
                            key: "aliases".to_string(),
                            value: PropertyScalar::Json("[\"me\",\"I\",\"myself\"]".to_string()),
                        },
                    ],
                    resolved_labels: vec![],
                },
                EntityNode {
                    id: assistant_entity_id.clone(),
                    type_id: "node.ai_agent".to_string(),
                    universe_id: Some(COMMON_UNIVERSE_ID.to_string()),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: vec![PropertyValue {
                        key: "name".to_string(),
                        value: PropertyScalar::String("Exobrain Assistant".to_string()),
                    }],
                    resolved_labels: vec![],
                },
            ],
            blocks: vec![BlockNode {
                id: assistant_block_id.clone(),
                type_id: "node.block".to_string(),
                user_id: user_id.to_string(),
                visibility: Visibility::Private,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Exobrain Assistant is your personal assistant in Exobrain. It chats with you and helps organize your knowledge graph.".to_string()),
                }],
                resolved_labels: vec![],
            }],
            edges: vec![
                GraphEdge {
                    from_id: person_entity_id.clone(),
                    to_id: COMMON_UNIVERSE_ID.to_string(),
                    edge_type: "IS_PART_OF".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: default_edge_properties("user universe assignment"),
                },
                GraphEdge {
                    from_id: assistant_entity_id.clone(),
                    to_id: COMMON_UNIVERSE_ID.to_string(),
                    edge_type: "IS_PART_OF".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: default_edge_properties("assistant universe assignment"),
                },
                GraphEdge {
                    from_id: assistant_entity_id.clone(),
                    to_id: person_entity_id,
                    edge_type: "RELATED_TO".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: default_edge_properties("assistant relationship"),
                },
                GraphEdge {
                    from_id: assistant_entity_id,
                    to_id: assistant_block_id,
                    edge_type: "DESCRIBED_BY".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Private,
                    properties: default_edge_properties("assistant description link"),
                },
            ],
        }
    }

    fn user_init_graph_node_ids(delta: &GraphDelta) -> Result<UserInitGraphNodeIds> {
        let person_entity_id = delta
            .entities
            .iter()
            .find(|entity| entity.type_id == "node.person")
            .map(|entity| entity.id.clone())
            .ok_or_else(|| anyhow!("missing person entity in user init delta"))?;
        let assistant_entity_id = delta
            .entities
            .iter()
            .find(|entity| entity.type_id == "node.ai_agent")
            .map(|entity| entity.id.clone())
            .ok_or_else(|| anyhow!("missing assistant entity in user init delta"))?;

        Ok(UserInitGraphNodeIds {
            person_entity_id,
            assistant_entity_id,
        })
    }

    pub async fn find_entity_candidates(
        &self,
        query: FindEntityCandidatesQuery,
    ) -> Result<FindEntityCandidatesResult> {
        use_cases::entity_search::find_entity_candidates(self, query).await
    }

    pub async fn list_entities_by_type(
        &self,
        query: ListEntitiesByTypeQuery,
    ) -> Result<ListEntitiesByTypeResult> {
        use_cases::entity_listing::list_entities_by_type(self, query).await
    }

    pub async fn get_entity_context(
        &self,
        query: GetEntityContextQuery,
    ) -> Result<GetEntityContextResult> {
        use_cases::entity_context::get_entity_context(self, query).await
    }

    pub async fn upsert_graph_delta(&self, delta: GraphDelta) -> Result<()> {
        self.ensure_users_initialized_for_delta(&delta).await?;
        self.upsert_graph_delta_internal(delta).await
    }

    async fn apply_user_initialization_delta(
        &self,
        user_id: &str,
        delta: GraphDelta,
        node_ids: &UserInitGraphNodeIds,
    ) -> Result<()> {
        self.upsert_graph_delta_internal(delta).await?;
        self.graph_repository
            .mark_user_graph_initialized(user_id, node_ids)
            .await
    }

    async fn upsert_graph_delta_internal(&self, delta: GraphDelta) -> Result<()> {
        use_cases::upsert_graph_delta::upsert_graph_delta_internal(self, delta).await
    }

    async fn ensure_users_initialized_for_delta(&self, delta: &GraphDelta) -> Result<()> {
        let mut user_ids = HashSet::new();

        for universe in &delta.universes {
            user_ids.insert(universe.user_id.trim().to_string());
        }
        for entity in &delta.entities {
            user_ids.insert(entity.user_id.trim().to_string());
        }
        for block in &delta.blocks {
            user_ids.insert(block.user_id.trim().to_string());
        }
        for edge in &delta.edges {
            user_ids.insert(edge.user_id.trim().to_string());
        }

        for user_id in user_ids {
            if user_id.is_empty() || user_id == EXOBRAIN_USER_ID {
                continue;
            }
            if self
                .graph_repository
                .user_graph_needs_initialization(&user_id)
                .await?
            {
                // In implicit initialization flow, we deterministically reuse `user_id` as
                // `user_name` when no richer user profile is available in the request.
                let delta = Self::user_init_delta(&user_id, &user_id);
                let node_ids = Self::user_init_graph_node_ids(&delta)?;
                self.apply_user_initialization_delta(&user_id, delta, &node_ids)
                    .await?;
            }
        }

        Ok(())
    }
}

fn resolve_labels_for_type(
    type_id: &str,
    inheritance: &[crate::domain::TypeInheritance],
) -> Vec<String> {
    let mut chain = vec![type_id.to_string()];
    let mut current = type_id.to_string();
    loop {
        let parent = inheritance
            .iter()
            .find(|edge| edge.child_type_id == current)
            .map(|edge| edge.parent_type_id.clone());
        match parent {
            Some(next) => {
                chain.push(next.clone());
                current = next;
            }
            None => break,
        }
    }

    chain
        .into_iter()
        .rev()
        .map(|id| id.trim_start_matches("node.").to_string())
        .map(|label| {
            let mut chars = label.chars();
            match chars.next() {
                Some(first) => format!(
                    "{}{}",
                    first.to_ascii_uppercase(),
                    chars.collect::<String>()
                ),
                None => label,
            }
        })
        .collect()
}

fn default_edge_properties(provenance_hint: &str) -> Vec<PropertyValue> {
    vec![
        PropertyValue {
            key: "confidence".to_string(),
            value: PropertyScalar::Float(1.0),
        },
        PropertyValue {
            key: "status".to_string(),
            value: PropertyScalar::String("asserted".to_string()),
        },
        PropertyValue {
            key: "provenance_hint".to_string(),
            value: PropertyScalar::String(provenance_hint.to_string()),
        },
    ]
}

fn validate_internal_timestamps_not_provided(
    subject_id: &str,
    provided: &[PropertyValue],
    errors: &mut Vec<String>,
) {
    for prop in provided {
        if prop.key == "created_at" || prop.key == "updated_at" {
            errors.push(format!(
                "{} cannot set internal property '{}'",
                subject_id, prop.key
            ));
        }
    }
}

fn schema_kind_for_type_id(value: &str) -> Option<SchemaKind> {
    let id = TypeId::parse(value).ok()?;
    let raw = id.as_str();
    let prefix = raw.split('.').next().unwrap_or(raw);
    SchemaKind::from_db_str(prefix)
}

fn is_global_property_owner(owner_type_id: &str, property_owner_type_id: &str) -> bool {
    let Some(owner_kind) = schema_kind_for_type_id(owner_type_id) else {
        return false;
    };

    property_owner_type_id == owner_kind.as_db_str()
}

fn validate_graph_id(id: &str, kind: &str) -> std::result::Result<(), String> {
    match kind {
        "entity" => crate::domain::EntityId::parse(id).map(|_| ()),
        "universe" => crate::domain::UniverseId::parse(id).map(|_| ()),
        _ => {
            if id.trim().is_empty() {
                return Err(format!("{kind} id is required"));
            }
            if uuid::Uuid::parse_str(id).is_err() {
                return Err(format!("{kind} id '{}' must be a valid UUID", id));
            }
            Ok(())
        }
    }
}

fn validate_properties(
    subject_id: &str,
    owner_type_id: &str,
    provided: &[PropertyValue],
    all_properties: &[crate::domain::TypeProperty],
    inheritance: &[crate::domain::TypeInheritance],
    errors: &mut Vec<String>,
) {
    let allowed = collect_allowed_properties(owner_type_id, all_properties, inheritance);
    let required: HashSet<String> = all_properties
        .iter()
        .filter(|p| {
            p.required
                && (p.owner_type_id == owner_type_id
                    || is_assignable(owner_type_id, &p.owner_type_id, inheritance)
                    || is_global_property_owner(owner_type_id, &p.owner_type_id))
        })
        .map(|p| p.prop_name.clone())
        .collect();

    for property in provided {
        if !allowed.contains_key(&property.key) {
            errors.push(format!(
                "{} property '{}' is not allowed for {}",
                subject_id, property.key, owner_type_id
            ));
        }
    }

    for req in required {
        if req == "id" {
            continue;
        }
        if !provided.iter().any(|p| p.key == req) {
            errors.push(format!(
                "{} is missing required property '{}'",
                subject_id, req
            ));
        }
    }
}

fn collect_allowed_properties(
    owner_type_id: &str,
    all_properties: &[crate::domain::TypeProperty],
    inheritance: &[crate::domain::TypeInheritance],
) -> HashMap<String, String> {
    all_properties
        .iter()
        .filter(|prop| {
            prop.owner_type_id == owner_type_id
                || is_assignable(owner_type_id, &prop.owner_type_id, inheritance)
                || is_global_property_owner(owner_type_id, &prop.owner_type_id)
        })
        .map(|prop| (prop.prop_name.clone(), prop.value_type.clone()))
        .collect()
}

fn is_assignable(
    actual: &str,
    expected: &str,
    inheritance: &[crate::domain::TypeInheritance],
) -> bool {
    if actual == expected {
        return true;
    }

    let mut stack = vec![actual.to_string()];
    let mut seen = HashSet::new();
    while let Some(current) = stack.pop() {
        if !seen.insert(current.clone()) {
            continue;
        }
        for parent in inheritance.iter().filter(|i| i.child_type_id == current) {
            if parent.parent_type_id == expected {
                return true;
            }
            stack.push(parent.parent_type_id.clone());
        }
    }
    false
}

fn extract_text(properties: &[crate::domain::PropertyValue]) -> String {
    properties
        .iter()
        .find_map(|prop| match (&prop.key[..], &prop.value) {
            ("text", PropertyScalar::String(value)) => Some(value.clone()),
            _ => None,
        })
        .unwrap_or_default()
}

async fn block_levels_for_blocks(
    blocks: &[BlockNode],
    edges: &[GraphEdge],
    graph_repository: &dyn GraphRepository,
) -> Result<HashMap<String, i64>> {
    let contexts =
        existing_block_context_for_referenced_summarize_parents(blocks, edges, graph_repository)
            .await?;

    let block_ids: HashSet<&str> = blocks.iter().map(|b| b.id.as_str()).collect();
    let mut levels: HashMap<String, i64> = HashMap::new();

    for edge in edges {
        if edge.edge_type.eq_ignore_ascii_case("DESCRIBED_BY")
            && block_ids.contains(edge.to_id.as_str())
        {
            levels.entry(edge.to_id.clone()).or_insert(0);
        }
    }

    for (block_id, context) in &contexts {
        levels
            .entry(block_id.clone())
            .or_insert(context.block_level);
    }

    for block in blocks {
        if levels.contains_key(&block.id) {
            continue;
        }
        if let Some(existing) = graph_repository
            .get_existing_block_context(&block.id, &block.user_id, block.visibility)
            .await?
        {
            levels.insert(block.id.clone(), existing.block_level);
        }
    }

    let summarize_edges: Vec<(&str, &str)> = edges
        .iter()
        .filter(|edge| {
            edge.edge_type.eq_ignore_ascii_case("SUMMARIZES")
                && (block_ids.contains(edge.from_id.as_str())
                    || contexts.contains_key(edge.from_id.as_str()))
                && block_ids.contains(edge.to_id.as_str())
        })
        .map(|edge| (edge.from_id.as_str(), edge.to_id.as_str()))
        .collect();

    let mut changed = true;
    while changed {
        changed = false;
        for (from_id, to_id) in &summarize_edges {
            if let Some(from_level) = levels.get(*from_id) {
                let candidate = from_level + 1;
                let existing = levels.get(*to_id).copied();
                if existing.is_none() || candidate < existing.unwrap_or(i64::MAX) {
                    levels.insert((*to_id).to_string(), candidate);
                    changed = true;
                }
            }
        }
    }

    levels.retain(|id, _| block_ids.contains(id.as_str()));

    Ok(levels)
}

async fn root_entity_ids_for_blocks(
    blocks: &[BlockNode],
    edges: &[GraphEdge],
    graph_repository: &dyn GraphRepository,
) -> Result<HashMap<String, String>> {
    let contexts =
        existing_block_context_for_referenced_summarize_parents(blocks, edges, graph_repository)
            .await?;

    let block_ids: HashSet<&str> = blocks.iter().map(|b| b.id.as_str()).collect();
    let described_by_parents: HashMap<&str, &str> = edges
        .iter()
        .filter(|e| {
            e.edge_type.eq_ignore_ascii_case("DESCRIBED_BY") && block_ids.contains(e.to_id.as_str())
        })
        .map(|e| (e.to_id.as_str(), e.from_id.as_str()))
        .collect();
    let summarize_parents: HashMap<&str, &str> = edges
        .iter()
        .filter(|e| {
            e.edge_type.eq_ignore_ascii_case("SUMMARIZES") && block_ids.contains(e.to_id.as_str())
        })
        .map(|e| (e.to_id.as_str(), e.from_id.as_str()))
        .collect();

    let mut out = HashMap::new();
    for block in blocks {
        let mut current = block.id.as_str();
        let mut seen = HashSet::new();
        loop {
            if !seen.insert(current) {
                return Err(anyhow!(
                    "cycle detected while resolving root_entity_id for block {}",
                    block.id
                ));
            }
            if let Some(root_entity) = described_by_parents.get(current) {
                out.insert(block.id.clone(), (*root_entity).to_string());
                break;
            }
            if let Some(parent_block) = summarize_parents.get(current) {
                if let Some(parent_context) = contexts.get(*parent_block) {
                    out.insert(block.id.clone(), parent_context.root_entity_id.clone());
                    break;
                }
                current = parent_block;
                continue;
            }
            if let Some(context) = contexts.get(current) {
                out.insert(block.id.clone(), context.root_entity_id.clone());
                break;
            }
            if let Some(existing) = graph_repository
                .get_existing_block_context(current, &block.user_id, block.visibility)
                .await?
            {
                out.insert(block.id.clone(), existing.root_entity_id);
                break;
            }
            return Err(anyhow!(
                "unable to resolve root_entity_id for block {} from DESCRIBED_BY/SUMMARIZES edges",
                block.id
            ));
        }
    }
    Ok(out)
}

async fn existing_block_context_for_referenced_summarize_parents(
    blocks: &[BlockNode],
    edges: &[GraphEdge],
    graph_repository: &dyn GraphRepository,
) -> Result<HashMap<String, ExistingBlockContext>> {
    let block_ids: HashSet<&str> = blocks.iter().map(|b| b.id.as_str()).collect();
    let parent_scopes: HashMap<&str, (&str, Visibility)> = edges
        .iter()
        .filter(|edge| {
            edge.edge_type.eq_ignore_ascii_case("SUMMARIZES")
                && block_ids.contains(edge.to_id.as_str())
                && !block_ids.contains(edge.from_id.as_str())
        })
        .map(|edge| {
            (
                edge.from_id.as_str(),
                (edge.user_id.as_str(), edge.visibility),
            )
        })
        .collect();

    let mut contexts = HashMap::new();
    for (parent_id, (user_id, visibility)) in parent_scopes {
        let context = graph_repository
            .get_existing_block_context(parent_id, user_id, visibility)
            .await?
            .ok_or_else(|| {
                anyhow!(
                    "unable to resolve root_entity_id for block {} from DESCRIBED_BY/SUMMARIZES edges",
                    parent_id
                )
            })?;
        contexts.insert(parent_id.to_string(), context);
    }

    Ok(contexts)
}

fn resolve_block_universe_id<'a>(
    root_entity_ids: &HashMap<String, String>,
    block: &BlockNode,
    entities: &'a [EntityNode],
) -> &'a str {
    if let Some(root_entity_id) = root_entity_ids.get(&block.id) {
        if let Some(entity) = entities.iter().find(|entity| &entity.id == root_entity_id) {
            return entity.universe_id.as_deref().unwrap_or(COMMON_UNIVERSE_ID);
        }
    }

    COMMON_UNIVERSE_ID
}

#[cfg(test)]
mod tests;
