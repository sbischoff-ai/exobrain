use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use anyhow::{anyhow, Result};

use crate::{
    domain::{
        BlockNode, EmbeddedBlock, EntityNode, FullSchema, GraphDelta, GraphEdge, PropertyScalar,
        PropertyValue, SchemaType, UpsertSchemaTypeCommand, Visibility,
    },
    ports::{Embedder, GraphRepository, SchemaRepository},
};

const EXOBRAIN_USER_ID: &str = "exobrain";
const COMMON_UNIVERSE_ID: &str = "universe.real_world";
const COMMON_EXOBRAIN_ENTITY_ID: &str = "concept.exobrain";
const COMMON_EXOBRAIN_BLOCK_ID: &str = "block.concept.exobrain";

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

        self.ingest_graph_delta(Self::common_root_delta()).await
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
        self.ingest_graph_delta(delta.clone()).await?;
        Ok(delta)
    }

    fn common_root_delta() -> GraphDelta {
        GraphDelta {
            universe_id: COMMON_UNIVERSE_ID.to_string(),
            user_id: EXOBRAIN_USER_ID.to_string(),
            visibility: Visibility::Shared,
            entities: vec![EntityNode {
                id: COMMON_EXOBRAIN_ENTITY_ID.to_string(),
                labels: vec!["Entity".to_string(), "Concept".to_string()],
                universe_id: COMMON_UNIVERSE_ID.to_string(),
                user_id: EXOBRAIN_USER_ID.to_string(),
                visibility: Visibility::Shared,
                properties: vec![
                    PropertyValue {
                        key: "name".to_string(),
                        value: PropertyScalar::String("Exobrain".to_string()),
                    },
                    PropertyValue {
                        key: "kind".to_string(),
                        value: PropertyScalar::String("platform".to_string()),
                    },
                ],
            }],
            blocks: vec![BlockNode {
                id: COMMON_EXOBRAIN_BLOCK_ID.to_string(),
                labels: vec!["Block".to_string()],
                root_entity_id: COMMON_EXOBRAIN_ENTITY_ID.to_string(),
                user_id: EXOBRAIN_USER_ID.to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Exobrain is the shared platform for capturing and organizing knowledge, powering assistants and knowledge workflows.".to_string()),
                }],
            }],
            edges: vec![],
        }
    }

    fn user_init_delta(user_id: &str, user_name: &str) -> GraphDelta {
        let person_entity_id = format!("person.{user_id}");
        let assistant_entity_id = format!("assistant.{user_id}");

        GraphDelta {
            universe_id: COMMON_UNIVERSE_ID.to_string(),
            user_id: user_id.to_string(),
            visibility: Visibility::Shared,
            entities: vec![
                EntityNode {
                    id: person_entity_id.clone(),
                    labels: vec!["Entity".to_string(), "Person".to_string()],
                    universe_id: COMMON_UNIVERSE_ID.to_string(),
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
                },
                EntityNode {
                    id: assistant_entity_id.clone(),
                    labels: vec!["Entity".to_string(), "Object".to_string()],
                    universe_id: COMMON_UNIVERSE_ID.to_string(),
                    user_id: user_id.to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![PropertyValue {
                        key: "name".to_string(),
                        value: PropertyScalar::String("Exobrain Assistant".to_string()),
                    }],
                },
            ],
            blocks: vec![BlockNode {
                id: format!("block.assistant.{user_id}"),
                labels: vec!["Block".to_string()],
                root_entity_id: assistant_entity_id.clone(),
                user_id: user_id.to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Exobrain Assistant is your personal assistant in Exobrain. It chats with you and helps organize your knowledge graph.".to_string()),
                }],
            }],
            edges: vec![GraphEdge {
                from_id: assistant_entity_id,
                to_id: person_entity_id,
                edge_type: "RELATED_TO".to_string(),
                user_id: user_id.to_string(),
                visibility: Visibility::Shared,
                properties: vec![],
            }],
        }
    }

    pub async fn ingest_graph_delta(&self, delta: GraphDelta) -> Result<()> {
        self.validate_delta_against_schema(&delta).await?;
        validate_delta_access_scope(&delta)?;

        let texts: Vec<String> = delta
            .blocks
            .iter()
            .map(|block| extract_text(&block.properties))
            .collect();
        let vectors = self.embedder.embed_texts(&texts).await?;

        let blocks: Vec<EmbeddedBlock> = delta
            .blocks
            .iter()
            .zip(vectors.into_iter())
            .zip(texts.into_iter())
            .map(|((block, vector), text)| EmbeddedBlock {
                block: block.clone(),
                universe_id: delta.universe_id.clone(),
                user_id: delta.user_id.clone(),
                visibility: delta.visibility,
                vector,
                entity_ids: vec![block.root_entity_id.clone()],
                text,
            })
            .collect();

        self.graph_repository
            .apply_delta_with_blocks(&delta, &blocks)
            .await
    }

    async fn validate_delta_against_schema(&self, delta: &GraphDelta) -> Result<()> {
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

        for entity in &delta.entities {
            if let Err(err) = validate_graph_id(&entity.id, "entity") {
                errors.push(err);
                continue;
            }
            let node_type = infer_node_type("node.entity", &entity.labels);
            node_type_by_id.insert(entity.id.clone(), node_type.clone());
            if !schema_types.contains_key(&node_type) {
                errors.push(format!(
                    "entity {} uses unknown schema type {}",
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
            let node_type = infer_node_type("node.block", &block.labels);
            node_type_by_id.insert(block.id.clone(), node_type.clone());
            if !schema_types.contains_key(&node_type) {
                errors.push(format!(
                    "block {} uses unknown schema type {}",
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
                let valid_rule = edge_rules.iter().any(|rule| {
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

        if errors.is_empty() {
            return Ok(());
        }

        Err(anyhow!(
            "graph delta validation failed:\n- {}",
            errors.join("\n- ")
        ))
    }
}

fn infer_node_type(base_type: &str, labels: &[String]) -> String {
    labels
        .iter()
        .find_map(|label| {
            if label.eq_ignore_ascii_case("entity") || label.eq_ignore_ascii_case("block") {
                return None;
            }
            Some(format!("node.{}", label.to_lowercase()))
        })
        .unwrap_or_else(|| base_type.to_string())
}

fn validate_graph_id(id: &str, kind: &str) -> std::result::Result<(), String> {
    if id.trim().is_empty() {
        return Err(format!("{kind} id is required"));
    }
    let valid = id.chars().all(|ch| {
        ch.is_ascii_lowercase() || ch.is_ascii_digit() || ch == '.' || ch == '-' || ch == '_'
    });
    if !valid || !id.contains('.') {
        return Err(format!(
            "{kind} id '{}' must use lowercase dot-separated format (e.g. person.alex or block.note.1)",
            id
        ));
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
    if delta.user_id.trim().is_empty() {
        return Err(anyhow!("user_id is required"));
    }

    for entity in &delta.entities {
        if entity.user_id != delta.user_id {
            return Err(anyhow!("entity user_id must match request user_id"));
        }
        if entity.visibility != delta.visibility {
            return Err(anyhow!("entity visibility must match request visibility"));
        }
    }

    for block in &delta.blocks {
        if block.user_id != delta.user_id {
            return Err(anyhow!("block user_id must match request user_id"));
        }
        if block.visibility != delta.visibility {
            return Err(anyhow!("block visibility must match request visibility"));
        }
    }

    for edge in &delta.edges {
        if edge.user_id != delta.user_id {
            return Err(anyhow!("edge user_id must match request user_id"));
        }
        if edge.visibility != delta.visibility {
            return Err(anyhow!("edge visibility must match request visibility"));
        }
    }

    Ok(())
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
                "edge" => vec![SchemaType {
                    id: "edge.related_to".to_string(),
                    kind: "edge".to_string(),
                    name: "RELATED_TO".to_string(),
                    description: String::new(),
                    active: true,
                }],
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
                    owner_type_id: "node.concept".to_string(),
                    prop_name: "kind".to_string(),
                    value_type: "string".to_string(),
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
            Ok(vec![EdgeEndpointRule {
                edge_type_id: "edge.related_to".to_string(),
                from_node_type_id: "node.entity".to_string(),
                to_node_type_id: "node.entity".to_string(),
                active: true,
                description: String::new(),
            }])
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
            }),
            Arc::new(FakeEmbedder),
        );

        app.ingest_graph_delta(GraphDelta {
            universe_id: "real-life".to_string(),
            user_id: "user-1".to_string(),
            visibility: Visibility::Private,
            entities: vec![EntityNode {
                id: "person.alex".to_string(),
                labels: vec!["Entity".to_string(), "Person".to_string()],
                universe_id: "real-life".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Alex".to_string()),
                }],
            }],
            blocks: vec![BlockNode {
                id: "block.alex.root".to_string(),
                labels: vec!["Block".to_string()],
                root_entity_id: "person.alex".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Alex is a close friend.".to_string()),
                }],
            }],
            edges: vec![GraphEdge {
                from_id: "person.alex".to_string(),
                to_id: "person.alex".to_string(),
                edge_type: "RELATED_TO".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: vec![],
            }],
        })
        .await
        .expect("ingestion should succeed");

        let guard = captured.lock().expect("lock should be available");
        assert_eq!(guard.len(), 1);
        assert_eq!(guard[0].block.id, "block.alex.root");
        assert_eq!(guard[0].vector.len(), 2);
        assert_eq!(guard[0].entity_ids, vec!["person.alex".to_string()]);
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
            }),
            Arc::new(FakeEmbedder),
        );

        app.ensure_common_root_graph()
            .await
            .expect("root graph seeding should succeed");

        let guard = captured.lock().expect("lock should be available");
        assert_eq!(guard.len(), 1);
        assert_eq!(guard[0].block.id, "block.concept.exobrain");
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
            }),
            Arc::new(FakeEmbedder),
        );

        let delta = app
            .initialize_user_graph("user-1", "Alex")
            .await
            .expect("user graph init should succeed");

        assert_eq!(delta.user_id, "user-1");
        assert_eq!(delta.visibility, Visibility::Shared);
        assert_eq!(delta.entities.len(), 2);
        assert_eq!(delta.blocks.len(), 1);
        assert_eq!(delta.edges.len(), 1);

        let guard = captured.lock().expect("lock should be available");
        assert_eq!(guard.len(), 1);
        assert_eq!(guard[0].block.root_entity_id, "assistant.user-1");
    }

    #[tokio::test]
    async fn rejects_mismatched_scope_on_entities() {
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo::new()),
            Arc::new(FakeGraphRepository { root_exists: false }),
            Arc::new(FakeEmbedder),
        );

        let err = app
            .ingest_graph_delta(GraphDelta {
                universe_id: "real-life".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                entities: vec![EntityNode {
                    id: "person.alex".to_string(),
                    labels: vec![],
                    universe_id: "real-life".to_string(),
                    user_id: "user-2".to_string(),
                    visibility: Visibility::Private,
                    properties: vec![],
                }],
                blocks: vec![],
                edges: vec![],
            })
            .await
            .expect_err("mismatched user_id should fail");

        assert!(
            err.to_string()
                .contains("entity user_id must match request user_id")
                || err.to_string().contains("validation failed")
        );
    }
}
