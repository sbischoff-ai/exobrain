use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use anyhow::{anyhow, Result};

use crate::{
    domain::{
        BlockNode, EmbeddedBlock, EntityNode, ExistingBlockContext, FullSchema, GraphDelta,
        GraphEdge, PropertyScalar, PropertyValue, SchemaType, UniverseNode,
        UpsertSchemaTypeCommand, Visibility,
    },
    ports::{Embedder, GraphRepository, SchemaRepository},
};

const EXOBRAIN_USER_ID: &str = "exobrain";
const COMMON_UNIVERSE_ID: &str = "9d7f0fa5-78c1-4805-9efb-3f8f16090d7f";
const COMMON_UNIVERSE_NAME: &str = "Real World";
const COMMON_EXOBRAIN_ENTITY_ID: &str = "8c75cc89-6204-4fed-aec1-34d032ff95ee";
const COMMON_EXOBRAIN_BLOCK_ID: &str = "ea5ca80f-346b-4f66-bff2-d307ce5d7da9";

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
        let node_types = self.schema_repository.get_by_kind("node").await?;
        let edge_types = self.schema_repository.get_by_kind("edge").await?;
        let inheritance = self.schema_repository.get_type_inheritance().await?;
        let properties = self.schema_repository.get_all_properties().await?;
        let edge_rules = self.schema_repository.get_edge_endpoint_rules().await?;

        let hydrated_nodes = node_types
            .into_iter()
            .map(|schema_type| {
                let node_id = schema_type.id.clone();
                let type_properties = properties
                    .iter()
                    .filter(|p| p.owner_type_id == node_id)
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
                    .filter(|p| p.owner_type_id == edge_id)
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

    pub async fn upsert_schema_type(&self, command: UpsertSchemaTypeCommand) -> Result<SchemaType> {
        let schema_type = command.schema_type;

        if !matches!(schema_type.kind.as_str(), "node" | "edge") {
            return Err(anyhow!("schema kind must be one of: node, edge"));
        }

        if schema_type.kind == "edge" && command.parent_type_id.is_some() {
            return Err(anyhow!("edge inheritance is out of scope"));
        }

        if schema_type.kind == "node" {
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

                if parent_schema.kind != "node" {
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

        if upserted.kind == "node" && upserted.id != "node.entity" {
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

    pub async fn initialize_user_graph(
        &self,
        user_id: &str,
        user_name: &str,
    ) -> Result<GraphDelta> {
        let trimmed_user_id = user_id.trim();
        if trimmed_user_id.is_empty() {
            return Err(anyhow!("user_id is required"));
        }

        let trimmed_user_name = user_name.trim();
        if trimmed_user_name.is_empty() {
            return Err(anyhow!("user_name is required"));
        }

        let delta = Self::user_init_delta(trimmed_user_id, trimmed_user_name);
        self.upsert_graph_delta(delta.clone()).await?;
        Ok(delta)
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
                    properties: vec![],
                },
                GraphEdge {
                    from_id: COMMON_EXOBRAIN_ENTITY_ID.to_string(),
                    to_id: COMMON_EXOBRAIN_BLOCK_ID.to_string(),
                    edge_type: "DESCRIBED_BY".to_string(),
                    user_id: EXOBRAIN_USER_ID.to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![],
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
                    visibility: Visibility::Shared,
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
                    type_id: "node.object".to_string(),
                    universe_id: Some(COMMON_UNIVERSE_ID.to_string()),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Shared,
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
                visibility: Visibility::Shared,
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
                    visibility: Visibility::Shared,
                    properties: vec![],
                },
                GraphEdge {
                    from_id: assistant_entity_id.clone(),
                    to_id: COMMON_UNIVERSE_ID.to_string(),
                    edge_type: "IS_PART_OF".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![],
                },
                GraphEdge {
                    from_id: assistant_entity_id.clone(),
                    to_id: person_entity_id,
                    edge_type: "RELATED_TO".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![],
                },
                GraphEdge {
                    from_id: assistant_entity_id,
                    to_id: assistant_block_id,
                    edge_type: "DESCRIBED_BY".to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![],
                },
            ],
        }
    }

    pub async fn upsert_graph_delta(&self, mut delta: GraphDelta) -> Result<()> {
        let inheritance = self.validate_delta_against_schema(&delta).await?;
        validate_delta_access_scope(&delta)?;

        for entity in &mut delta.entities {
            entity.resolved_labels = resolve_labels_for_type(&entity.type_id, &inheritance);
        }
        for block in &mut delta.blocks {
            block.resolved_labels = resolve_labels_for_type(&block.type_id, &inheritance);
        }

        let texts: Vec<String> = delta
            .blocks
            .iter()
            .map(|block| extract_text(&block.properties))
            .collect();
        let vectors = self.embedder.embed_texts(&texts).await?;

        let block_levels = block_levels_for_blocks(
            &delta.blocks,
            &delta.edges,
            self.graph_repository.as_ref(),
            &delta,
        )
        .await?;
        let root_entity_ids = root_entity_ids_for_blocks(
            &delta.blocks,
            &delta.edges,
            self.graph_repository.as_ref(),
            &delta,
        )
        .await?;

        let blocks: Vec<EmbeddedBlock> = delta
            .blocks
            .iter()
            .zip(vectors.into_iter())
            .zip(texts.into_iter())
            .map(|((block, vector), text)| EmbeddedBlock {
                block: block.clone(),
                root_entity_id: root_entity_ids.get(&block.id).cloned().unwrap_or_default(),
                universe_id: resolve_block_universe_id(&root_entity_ids, block, &delta.entities)
                    .to_string(),
                user_id: block.user_id.clone(),
                visibility: block.visibility,
                vector,
                block_level: block_levels.get(&block.id).copied().unwrap_or(0),
                text,
            })
            .collect();

        self.graph_repository
            .apply_delta_with_blocks(&delta, &blocks)
            .await
    }

    async fn validate_delta_against_schema(
        &self,
        delta: &GraphDelta,
    ) -> Result<Vec<crate::domain::TypeInheritance>> {
        let schema_types = self
            .schema_repository
            .get_by_kind("node")
            .await?
            .into_iter()
            .map(|t| (t.id.clone(), t))
            .collect::<HashMap<_, _>>();
        let edge_types = self
            .schema_repository
            .get_by_kind("edge")
            .await?
            .into_iter()
            .map(|t| (t.id.clone(), t))
            .collect::<HashMap<_, _>>();
        let inheritance = self.schema_repository.get_type_inheritance().await?;
        let properties = self.schema_repository.get_all_properties().await?;
        let edge_rules = self.schema_repository.get_edge_endpoint_rules().await?;

        let mut node_type_by_id = HashMap::new();
        let mut errors = vec![];

        for universe in &delta.universes {
            if let Err(err) = validate_graph_id(&universe.id, "universe") {
                errors.push(err);
                continue;
            }
            if universe.name.trim().is_empty() {
                errors.push(format!("universe {} name is required", universe.id));
            }
            node_type_by_id.insert(universe.id.clone(), "node.universe".to_string());
        }

        for entity in &delta.entities {
            if let Err(err) = validate_graph_id(&entity.id, "entity") {
                errors.push(err);
                continue;
            }
            let node_type = entity.type_id.clone();
            node_type_by_id.insert(entity.id.clone(), node_type.clone());
            if let Some(universe_id) = &entity.universe_id {
                if !node_type_by_id.contains_key(universe_id)
                    && !delta.universes.iter().any(|u| &u.id == universe_id)
                    && universe_id != COMMON_UNIVERSE_ID
                {
                    errors.push(format!(
                        "entity {} references unknown universe {}",
                        entity.id, universe_id
                    ));
                }
            }
            if !schema_types.contains_key(&node_type) {
                errors.push(format!(
                    "entity {} uses unknown schema type {}",
                    entity.id, node_type
                ));
            } else if !is_assignable(&node_type, "node.entity", &inheritance) {
                errors.push(format!(
                    "entity {} type {} must descend from node.entity",
                    entity.id, node_type
                ));
            }
            validate_properties(
                &entity.id,
                &node_type,
                &entity.properties,
                &properties,
                &inheritance,
                &mut errors,
            );
        }

        for block in &delta.blocks {
            if let Err(err) = validate_graph_id(&block.id, "block") {
                errors.push(err);
                continue;
            }
            let node_type = block.type_id.clone();
            node_type_by_id.insert(block.id.clone(), node_type.clone());
            if !schema_types.contains_key(&node_type) {
                errors.push(format!(
                    "block {} uses unknown schema type {}",
                    block.id, node_type
                ));
            } else if !is_assignable(&node_type, "node.block", &inheritance) {
                errors.push(format!(
                    "block {} type {} must descend from node.block",
                    block.id, node_type
                ));
            }
            validate_properties(
                &block.id,
                &node_type,
                &block.properties,
                &properties,
                &inheritance,
                &mut errors,
            );
        }

        for edge in &delta.edges {
            if let Err(err) = validate_graph_id(&edge.from_id, "edge.from_id") {
                errors.push(err);
            }
            if let Err(err) = validate_graph_id(&edge.to_id, "edge.to_id") {
                errors.push(err);
            }
            let edge_type_id = format!("edge.{}", edge.edge_type.to_lowercase());
            if !edge_types.contains_key(&edge_type_id) {
                errors.push(format!(
                    "edge {}->{} references unknown edge type {}",
                    edge.from_id, edge.to_id, edge.edge_type
                ));
                continue;
            }
            validate_properties(
                &format!("{}:{}->{}", edge.edge_type, edge.from_id, edge.to_id),
                &edge_type_id,
                &edge.properties,
                &properties,
                &inheritance,
                &mut errors,
            );
            if let (Some(from_type), Some(to_type)) = (
                node_type_by_id.get(&edge.from_id),
                node_type_by_id.get(&edge.to_id),
            ) {
                let involves_universe = from_type == "node.universe" || to_type == "node.universe";
                let valid_rule = involves_universe
                    || edge_rules.iter().any(|rule| {
                        rule.edge_type_id == edge_type_id
                            && is_assignable(from_type, &rule.from_node_type_id, &inheritance)
                            && is_assignable(to_type, &rule.to_node_type_id, &inheritance)
                    });
                if !valid_rule {
                    errors.push(format!(
                        "edge {} ({}) violates schema endpoint rules for {} -> {}",
                        edge.edge_type, edge_type_id, from_type, to_type
                    ));
                }
            }
        }

        enforce_relationship_rules(delta, &mut errors);

        if errors.is_empty() {
            return Ok(inheritance);
        }

        Err(anyhow!(
            "graph delta validation failed:\n- {}",
            errors.join("\n- ")
        ))
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

fn validate_graph_id(id: &str, kind: &str) -> std::result::Result<(), String> {
    if id.trim().is_empty() {
        return Err(format!("{kind} id is required"));
    }
    if uuid::Uuid::parse_str(id).is_err() {
        return Err(format!("{kind} id '{}' must be a valid UUID", id));
    }
    Ok(())
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
                    || is_assignable(owner_type_id, &p.owner_type_id, inheritance))
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

fn validate_delta_access_scope(delta: &GraphDelta) -> Result<()> {
    for universe in &delta.universes {
        if universe.user_id.trim().is_empty() {
            return Err(anyhow!("universe user_id is required"));
        }
    }

    for entity in &delta.entities {
        if entity.user_id.trim().is_empty() {
            return Err(anyhow!("entity user_id is required"));
        }
    }

    for block in &delta.blocks {
        if block.user_id.trim().is_empty() {
            return Err(anyhow!("block user_id is required"));
        }
    }

    for edge in &delta.edges {
        if edge.user_id.trim().is_empty() {
            return Err(anyhow!("edge user_id is required"));
        }
    }

    Ok(())
}

fn enforce_relationship_rules(delta: &GraphDelta, errors: &mut Vec<String>) {
    let mut incoming_by_node: HashMap<&str, usize> = HashMap::new();
    let mut outgoing_by_node: HashMap<&str, usize> = HashMap::new();
    let mut entity_is_part_of: HashMap<&str, usize> = HashMap::new();
    let mut block_parent_edges: HashMap<&str, usize> = HashMap::new();

    // Explicit relationships in edges[]
    for edge in &delta.edges {
        *incoming_by_node.entry(edge.to_id.as_str()).or_insert(0) += 1;
        *outgoing_by_node.entry(edge.from_id.as_str()).or_insert(0) += 1;

        if edge.edge_type.eq_ignore_ascii_case("IS_PART_OF") {
            *entity_is_part_of.entry(edge.from_id.as_str()).or_insert(0) += 1;
        }
        if edge.edge_type.eq_ignore_ascii_case("DESCRIBED_BY")
            || edge.edge_type.eq_ignore_ascii_case("SUMMARIZES")
        {
            *block_parent_edges.entry(edge.to_id.as_str()).or_insert(0) += 1;
        }
    }

    // Implicit IS_PART_OF relationships from EntityNode.universe_id (or Real World default).
    for entity in &delta.entities {
        let target_universe_id = entity.universe_id.as_deref().unwrap_or(COMMON_UNIVERSE_ID);
        *outgoing_by_node.entry(entity.id.as_str()).or_insert(0) += 1;
        *incoming_by_node.entry(target_universe_id).or_insert(0) += 1;
        *entity_is_part_of.entry(entity.id.as_str()).or_insert(0) += 1;
    }

    for universe in &delta.universes {
        let total = incoming_by_node
            .get(universe.id.as_str())
            .copied()
            .unwrap_or(0)
            + outgoing_by_node
                .get(universe.id.as_str())
                .copied()
                .unwrap_or(0);
        if total == 0 {
            errors.push(format!(
                "universe {} must have at least one relationship",
                universe.id
            ));
        }
    }

    for entity in &delta.entities {
        let total = incoming_by_node
            .get(entity.id.as_str())
            .copied()
            .unwrap_or(0)
            + outgoing_by_node
                .get(entity.id.as_str())
                .copied()
                .unwrap_or(0);
        if total == 0 {
            errors.push(format!(
                "entity {} must have at least one relationship",
                entity.id
            ));
        }
        if entity_is_part_of
            .get(entity.id.as_str())
            .copied()
            .unwrap_or(0)
            == 0
        {
            errors.push(format!(
                "entity {} must have IS_PART_OF edge to a universe",
                entity.id
            ));
        }
    }

    for block in &delta.blocks {
        let total = incoming_by_node
            .get(block.id.as_str())
            .copied()
            .unwrap_or(0)
            + outgoing_by_node
                .get(block.id.as_str())
                .copied()
                .unwrap_or(0);
        if total == 0 {
            errors.push(format!(
                "block {} must have at least one relationship",
                block.id
            ));
        }
        let count = block_parent_edges
            .get(block.id.as_str())
            .copied()
            .unwrap_or(0);
        if count != 1 {
            errors.push(format!(
                "block {} must have exactly one incoming DESCRIBED_BY or SUMMARIZES edge",
                block.id
            ));
        }
    }
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
    delta: &GraphDelta,
) -> Result<HashMap<String, i64>> {
    let contexts = existing_block_context_for_referenced_summarize_parents(
        blocks,
        edges,
        graph_repository,
        delta,
    )
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
    delta: &GraphDelta,
) -> Result<HashMap<String, String>> {
    let contexts = existing_block_context_for_referenced_summarize_parents(
        blocks,
        edges,
        graph_repository,
        delta,
    )
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
    _delta: &GraphDelta,
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
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::sync::{Arc, Mutex};

    use async_trait::async_trait;

    use crate::{
        domain::{
            BlockNode, EdgeEndpointRule, EntityNode, GraphEdge, PropertyValue, TypeInheritance,
            TypeProperty, UpsertSchemaTypePropertyInput, Visibility,
        },
        ports::{Embedder, GraphRepository, SchemaRepository},
    };

    struct FakeSchemaRepo {
        types: Mutex<HashMap<String, SchemaType>>,
        parents: Mutex<HashMap<String, String>>,
    }

    impl FakeSchemaRepo {
        fn new() -> Self {
            let mut types = HashMap::new();
            types.insert(
                "node.entity".to_string(),
                SchemaType {
                    id: "node.entity".to_string(),
                    kind: "node".to_string(),
                    name: "Entity".to_string(),
                    description: "".to_string(),
                    active: true,
                },
            );
            Self {
                types: Mutex::new(types),
                parents: Mutex::new(HashMap::new()),
            }
        }
    }

    #[async_trait]
    impl SchemaRepository for FakeSchemaRepo {
        async fn get_by_kind(&self, kind: &str) -> Result<Vec<SchemaType>> {
            let values = match kind {
                "node" => vec![
                    SchemaType {
                        id: "node.entity".to_string(),
                        kind: "node".to_string(),
                        name: "Entity".to_string(),
                        description: String::new(),
                        active: true,
                    },
                    SchemaType {
                        id: "node.person".to_string(),
                        kind: "node".to_string(),
                        name: "Person".to_string(),
                        description: String::new(),
                        active: true,
                    },
                    SchemaType {
                        id: "node.object".to_string(),
                        kind: "node".to_string(),
                        name: "Object".to_string(),
                        description: String::new(),
                        active: true,
                    },
                    SchemaType {
                        id: "node.concept".to_string(),
                        kind: "node".to_string(),
                        name: "Concept".to_string(),
                        description: String::new(),
                        active: true,
                    },
                    SchemaType {
                        id: "node.block".to_string(),
                        kind: "node".to_string(),
                        name: "Block".to_string(),
                        description: String::new(),
                        active: true,
                    },
                ],
                "edge" => vec![
                    SchemaType {
                        id: "edge.related_to".to_string(),
                        kind: "edge".to_string(),
                        name: "RELATED_TO".to_string(),
                        description: String::new(),
                        active: true,
                    },
                    SchemaType {
                        id: "edge.described_by".to_string(),
                        kind: "edge".to_string(),
                        name: "DESCRIBED_BY".to_string(),
                        description: String::new(),
                        active: true,
                    },
                    SchemaType {
                        id: "edge.is_part_of".to_string(),
                        kind: "edge".to_string(),
                        name: "IS_PART_OF".to_string(),
                        description: String::new(),
                        active: true,
                    },
                ],
                _ => vec![],
            };
            Ok(values)
        }

        async fn upsert(&self, schema_type: &SchemaType) -> Result<SchemaType> {
            self.types
                .lock()
                .expect("lock")
                .insert(schema_type.id.clone(), schema_type.clone());
            Ok(schema_type.clone())
        }

        async fn get_type_inheritance(&self) -> Result<Vec<TypeInheritance>> {
            Ok(vec![
                TypeInheritance {
                    child_type_id: "node.person".to_string(),
                    parent_type_id: "node.entity".to_string(),
                    description: String::new(),
                    active: true,
                },
                TypeInheritance {
                    child_type_id: "node.object".to_string(),
                    parent_type_id: "node.entity".to_string(),
                    description: String::new(),
                    active: true,
                },
                TypeInheritance {
                    child_type_id: "node.concept".to_string(),
                    parent_type_id: "node.entity".to_string(),
                    description: String::new(),
                    active: true,
                },
            ])
        }

        async fn get_all_properties(&self) -> Result<Vec<TypeProperty>> {
            Ok(vec![
                TypeProperty {
                    owner_type_id: "node.entity".to_string(),
                    prop_name: "name".to_string(),
                    value_type: "string".to_string(),
                    required: true,
                    readable: true,
                    writable: true,
                    active: true,
                    description: String::new(),
                },
                TypeProperty {
                    owner_type_id: "node.entity".to_string(),
                    prop_name: "aliases".to_string(),
                    value_type: "json".to_string(),
                    required: false,
                    readable: true,
                    writable: true,
                    active: true,
                    description: String::new(),
                },
                TypeProperty {
                    owner_type_id: "node.block".to_string(),
                    prop_name: "text".to_string(),
                    value_type: "string".to_string(),
                    required: true,
                    readable: true,
                    writable: true,
                    active: true,
                    description: String::new(),
                },
            ])
        }

        async fn get_edge_endpoint_rules(&self) -> Result<Vec<EdgeEndpointRule>> {
            Ok(vec![
                EdgeEndpointRule {
                    edge_type_id: "edge.related_to".to_string(),
                    from_node_type_id: "node.entity".to_string(),
                    to_node_type_id: "node.entity".to_string(),
                    active: true,
                    description: String::new(),
                },
                EdgeEndpointRule {
                    edge_type_id: "edge.described_by".to_string(),
                    from_node_type_id: "node.entity".to_string(),
                    to_node_type_id: "node.block".to_string(),
                    active: true,
                    description: String::new(),
                },
                EdgeEndpointRule {
                    edge_type_id: "edge.is_part_of".to_string(),
                    from_node_type_id: "node.entity".to_string(),
                    to_node_type_id: "node.universe".to_string(),
                    active: true,
                    description: String::new(),
                },
            ])
        }

        async fn get_schema_type(&self, id: &str) -> Result<Option<SchemaType>> {
            Ok(self.types.lock().expect("lock").get(id).cloned())
        }

        async fn get_parent_for_child(&self, child_type_id: &str) -> Result<Option<String>> {
            Ok(self
                .parents
                .lock()
                .expect("lock")
                .get(child_type_id)
                .cloned())
        }

        async fn is_descendant_of_entity(&self, node_type_id: &str) -> Result<bool> {
            if node_type_id == "node.entity" {
                return Ok(true);
            }
            let parents = self.parents.lock().expect("lock");
            Ok(matches!(parents.get(node_type_id), Some(v) if v == "node.entity"))
        }

        async fn upsert_inheritance(
            &self,
            child_type_id: &str,
            parent_type_id: &str,
            _description: &str,
        ) -> Result<()> {
            self.parents
                .lock()
                .expect("lock")
                .insert(child_type_id.to_string(), parent_type_id.to_string());
            Ok(())
        }

        async fn upsert_type_property(
            &self,
            _owner_type_id: &str,
            _property: &UpsertSchemaTypePropertyInput,
        ) -> Result<()> {
            Ok(())
        }
    }

    struct FakeGraphRepository {
        root_exists: bool,
    }

    #[async_trait]
    impl GraphRepository for FakeGraphRepository {
        async fn apply_delta_with_blocks(
            &self,
            _delta: &GraphDelta,
            _blocks: &[EmbeddedBlock],
        ) -> Result<()> {
            Ok(())
        }

        async fn common_root_graph_exists(&self) -> Result<bool> {
            Ok(self.root_exists)
        }

        async fn get_existing_block_context(
            &self,
            _block_id: &str,
            _user_id: &str,
            _visibility: Visibility,
        ) -> Result<Option<ExistingBlockContext>> {
            Ok(None)
        }
    }

    struct FakeEmbedder;

    #[async_trait]
    impl Embedder for FakeEmbedder {
        async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
            Ok(texts.iter().map(|_| vec![0.1_f32, 0.2_f32]).collect())
        }
    }

    struct CapturingGraphRepository {
        seen: Arc<Mutex<Vec<EmbeddedBlock>>>,
        root_exists: bool,
        block_contexts: HashMap<String, ExistingBlockContext>,
    }

    #[async_trait]
    impl GraphRepository for CapturingGraphRepository {
        async fn apply_delta_with_blocks(
            &self,
            _delta: &GraphDelta,
            blocks: &[EmbeddedBlock],
        ) -> Result<()> {
            let mut guard = self.seen.lock().expect("lock should be available");
            guard.extend(blocks.to_vec());
            Ok(())
        }

        async fn common_root_graph_exists(&self) -> Result<bool> {
            Ok(self.root_exists)
        }

        async fn get_existing_block_context(
            &self,
            block_id: &str,
            _user_id: &str,
            _visibility: Visibility,
        ) -> Result<Option<ExistingBlockContext>> {
            Ok(self.block_contexts.get(block_id).cloned())
        }
    }

    #[tokio::test]
    async fn rejects_invalid_schema_kind() {
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo::new()),
            Arc::new(FakeGraphRepository { root_exists: false }),
            Arc::new(FakeEmbedder),
        );

        let err = app
            .upsert_schema_type(UpsertSchemaTypeCommand {
                schema_type: SchemaType {
                    id: "x".to_string(),
                    kind: "invalid".to_string(),
                    name: "x".to_string(),
                    description: String::new(),
                    active: true,
                },
                parent_type_id: None,
                properties: vec![],
            })
            .await
            .expect_err("invalid schema kind should fail");

        assert!(err.to_string().contains("schema kind must be one of"));
    }

    #[tokio::test]
    async fn rejects_node_without_parent() {
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo::new()),
            Arc::new(FakeGraphRepository { root_exists: false }),
            Arc::new(FakeEmbedder),
        );

        let err = app
            .upsert_schema_type(UpsertSchemaTypeCommand {
                schema_type: SchemaType {
                    id: "node.person".to_string(),
                    kind: "node".to_string(),
                    name: "Person".to_string(),
                    description: String::new(),
                    active: true,
                },
                parent_type_id: None,
                properties: vec![],
            })
            .await
            .expect_err("missing parent should fail");

        assert!(err.to_string().contains("must declare parent_type_id"));
    }

    #[tokio::test]
    async fn ingests_blocks_and_creates_embeddings() {
        let captured = Arc::new(Mutex::new(vec![]));
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo::new()),
            Arc::new(CapturingGraphRepository {
                seen: captured.clone(),
                root_exists: false,
                block_contexts: HashMap::new(),
            }),
            Arc::new(FakeEmbedder),
        );

        app.upsert_graph_delta(GraphDelta {
            universes: vec![],
            entities: vec![EntityNode {
                id: "550e8400-e29b-41d4-a716-446655440001".to_string(),
                type_id: "node.person".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                universe_id: None,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Alex".to_string()),
                }],
                resolved_labels: vec![],
            }],
            blocks: vec![BlockNode {
                id: "550e8400-e29b-41d4-a716-446655440002".to_string(),
                type_id: "node.block".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Alex is a close friend.".to_string()),
                }],
                resolved_labels: vec![],
            }],
            edges: vec![
                GraphEdge {
                    from_id: "550e8400-e29b-41d4-a716-446655440001".to_string(),
                    to_id: "9d7f0fa5-78c1-4805-9efb-3f8f16090d7f".to_string(),
                    edge_type: "IS_PART_OF".to_string(),
                    user_id: "user-1".to_string(),
                    visibility: Visibility::Private,
                    properties: vec![],
                },
                GraphEdge {
                    from_id: "550e8400-e29b-41d4-a716-446655440001".to_string(),
                    to_id: "550e8400-e29b-41d4-a716-446655440002".to_string(),
                    edge_type: "DESCRIBED_BY".to_string(),
                    user_id: "user-1".to_string(),
                    visibility: Visibility::Private,
                    properties: vec![],
                },
            ],
        })
        .await
        .expect("ingestion should succeed");

        let guard = captured.lock().expect("lock should be available");
        assert_eq!(guard.len(), 1);
        assert_eq!(guard[0].block.id, "550e8400-e29b-41d4-a716-446655440002");
        assert_eq!(guard[0].vector.len(), 2);
        assert_eq!(guard[0].block_level, 0);
        assert_eq!(guard[0].text, "Alex is a close friend.");
        assert_eq!(guard[0].user_id, "user-1");
        assert_eq!(guard[0].visibility, Visibility::Private);
    }

    #[tokio::test]
    async fn seeds_common_root_when_missing() {
        let captured = Arc::new(Mutex::new(vec![]));
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo::new()),
            Arc::new(CapturingGraphRepository {
                seen: captured.clone(),
                root_exists: false,
                block_contexts: HashMap::new(),
            }),
            Arc::new(FakeEmbedder),
        );

        app.ensure_common_root_graph()
            .await
            .expect("root graph seeding should succeed");

        let guard = captured.lock().expect("lock should be available");
        assert_eq!(guard.len(), 1);
        assert_eq!(guard[0].block.id, "ea5ca80f-346b-4f66-bff2-d307ce5d7da9");
        assert_eq!(guard[0].user_id, "exobrain");
        assert_eq!(guard[0].visibility, Visibility::Shared);
    }

    #[tokio::test]
    async fn initializes_user_graph() {
        let captured = Arc::new(Mutex::new(vec![]));
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo::new()),
            Arc::new(CapturingGraphRepository {
                seen: captured.clone(),
                root_exists: true,
                block_contexts: HashMap::new(),
            }),
            Arc::new(FakeEmbedder),
        );

        let delta = app
            .initialize_user_graph("user-1", "Alex")
            .await
            .expect("user graph init should succeed");

        assert_eq!(delta.entities.len(), 2);
        assert_eq!(delta.blocks.len(), 1);
        assert_eq!(delta.edges.len(), 4);

        let guard = captured.lock().expect("lock should be available");
        assert_eq!(guard.len(), 1);
        assert_eq!(guard[0].block_level, 0);
    }

    #[tokio::test]
    async fn computes_block_levels_from_described_by_and_summarizes_edges() {
        let root_block_id = "550e8400-e29b-41d4-a716-446655440099";
        let child_block_id = "550e8400-e29b-41d4-a716-446655440098";
        let blocks = vec![
            BlockNode {
                id: root_block_id.to_string(),
                type_id: "node.block".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: vec![],
                resolved_labels: vec![],
            },
            BlockNode {
                id: child_block_id.to_string(),
                type_id: "node.block".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: vec![],
                resolved_labels: vec![],
            },
        ];
        let edges = vec![
            GraphEdge {
                from_id: "550e8400-e29b-41d4-a716-446655440001".to_string(),
                to_id: root_block_id.to_string(),
                edge_type: "DESCRIBED_BY".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: vec![],
            },
            GraphEdge {
                from_id: root_block_id.to_string(),
                to_id: child_block_id.to_string(),
                edge_type: "SUMMARIZES".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: vec![],
            },
        ];

        let delta = GraphDelta {
            universes: vec![],
            entities: vec![],
            blocks: blocks.clone(),
            edges: edges.clone(),
        };
        let levels = block_levels_for_blocks(
            &blocks,
            &edges,
            &FakeGraphRepository { root_exists: false },
            &delta,
        )
        .await
        .expect("levels should be computed");
        assert_eq!(levels.get(root_block_id).copied(), Some(0));
        assert_eq!(levels.get(child_block_id).copied(), Some(1));
    }

    #[tokio::test]
    async fn resolves_root_entity_and_level_from_existing_summarize_parent_block() {
        let existing_parent_block_id = "9a8c589c-51ea-4e36-b60e-505769f19b7a";
        let new_block_id = "0fdfb642-1ec0-48c9-a8e1-3120e8da5d0f";
        let blocks = vec![BlockNode {
            id: new_block_id.to_string(),
            type_id: "node.block".to_string(),
            user_id: "exobrain".to_string(),
            visibility: Visibility::Shared,
            properties: vec![PropertyValue {
                key: "text".to_string(),
                value: PropertyScalar::String("child".to_string()),
            }],
            resolved_labels: vec![],
        }];
        let edges = vec![GraphEdge {
            from_id: existing_parent_block_id.to_string(),
            to_id: new_block_id.to_string(),
            edge_type: "SUMMARIZES".to_string(),
            user_id: "exobrain".to_string(),
            visibility: Visibility::Shared,
            properties: vec![],
        }];
        let delta = GraphDelta {
            universes: vec![],
            entities: vec![],
            blocks: blocks.clone(),
            edges: edges.clone(),
        };
        let graph_repo = CapturingGraphRepository {
            seen: Arc::new(Mutex::new(vec![])),
            root_exists: false,
            block_contexts: HashMap::from([(
                existing_parent_block_id.to_string(),
                ExistingBlockContext {
                    root_entity_id: "8c75cc89-6204-4fed-aec1-34d032ff95ee".to_string(),
                    universe_id: COMMON_UNIVERSE_ID.to_string(),
                    block_level: 0,
                },
            )]),
        };

        let root_ids = root_entity_ids_for_blocks(&blocks, &edges, &graph_repo, &delta)
            .await
            .expect("root entity id should resolve from existing summarize parent");
        assert_eq!(
            root_ids.get(new_block_id).map(String::as_str),
            Some("8c75cc89-6204-4fed-aec1-34d032ff95ee")
        );

        let levels = block_levels_for_blocks(&blocks, &edges, &graph_repo, &delta)
            .await
            .expect("level should resolve from existing summarize parent");
        assert_eq!(levels.get(new_block_id).copied(), Some(1));
    }
    #[tokio::test]
    async fn accepts_implicit_is_part_of_from_entity_universe_assignment() {
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo::new()),
            Arc::new(FakeGraphRepository { root_exists: false }),
            Arc::new(FakeEmbedder),
        );

        app.upsert_graph_delta(GraphDelta {
            universes: vec![UniverseNode {
                id: "26bcdef7-41ce-4dc5-81e2-d2ba786270c1".to_string(),
                name: "Fake World".to_string(),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
            }],
            entities: vec![
                EntityNode {
                    id: "7ca59d34-ec3f-42a5-9500-0342f1690680".to_string(),
                    type_id: "node.person".to_string(),
                    universe_id: Some("26bcdef7-41ce-4dc5-81e2-d2ba786270c1".to_string()),
                    user_id: "exobrain".to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![PropertyValue {
                        key: "name".to_string(),
                        value: PropertyScalar::String("Fake Person".to_string()),
                    }],
                    resolved_labels: vec![],
                },
                EntityNode {
                    id: "f78e0747-8948-4a2b-9540-06dc46a868f8".to_string(),
                    type_id: "node.object".to_string(),
                    universe_id: None,
                    user_id: "exobrain".to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![PropertyValue {
                        key: "name".to_string(),
                        value: PropertyScalar::String("Real Object".to_string()),
                    }],
                    resolved_labels: vec![],
                },
            ],
            blocks: vec![],
            edges: vec![],
        })
        .await
        .expect("implicit IS_PART_OF relationships should satisfy topology rules");
    }

    #[tokio::test]
    async fn rejects_empty_entity_user_id() {
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo::new()),
            Arc::new(FakeGraphRepository { root_exists: false }),
            Arc::new(FakeEmbedder),
        );

        let err = app
            .upsert_graph_delta(GraphDelta {
                universes: vec![],
                entities: vec![EntityNode {
                    id: "550e8400-e29b-41d4-a716-4466554400ab".to_string(),
                    type_id: "node.person".to_string(),
                    universe_id: Some("550e8400-e29b-41d4-a716-4466554400ff".to_string()),
                    user_id: "   ".to_string(),
                    visibility: Visibility::Private,
                    properties: vec![],
                    resolved_labels: vec![],
                }],
                blocks: vec![],
                edges: vec![],
            })
            .await
            .expect_err("empty entity user_id should fail");

        assert!(
            err.to_string().contains("entity user_id is required")
                || err.to_string().contains("validation failed")
        );
    }
}
