use std::sync::Arc;

use anyhow::{anyhow, Result};

use crate::{
    domain::{
        EmbeddedBlock, FullSchema, GraphDelta, PropertyScalar, SchemaType, UpsertSchemaTypeCommand,
    },
    ports::{Embedder, GraphStore, SchemaRepository, VectorStore},
};

pub struct KnowledgeApplication {
    schema_repository: Arc<dyn SchemaRepository>,
    graph_store: Arc<dyn GraphStore>,
    embedder: Arc<dyn Embedder>,
    vector_store: Arc<dyn VectorStore>,
}

impl KnowledgeApplication {
    pub fn new(
        schema_repository: Arc<dyn SchemaRepository>,
        graph_store: Arc<dyn GraphStore>,
        embedder: Arc<dyn Embedder>,
        vector_store: Arc<dyn VectorStore>,
    ) -> Self {
        Self {
            schema_repository,
            graph_store,
            embedder,
            vector_store,
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

    pub async fn ingest_graph_delta(&self, delta: GraphDelta) -> Result<()> {
        validate_delta_access_scope(&delta)?;

        self.graph_store.apply_delta(&delta).await?;

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

        self.vector_store.upsert_blocks(&blocks).await
    }
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
        ports::{Embedder, GraphStore, SchemaRepository, VectorStore},
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
            Ok(vec![SchemaType {
                id: format!("{kind}.default"),
                kind: kind.to_string(),
                name: format!("default-{kind}"),
                description: String::new(),
                active: true,
            }])
        }

        async fn upsert(&self, schema_type: &SchemaType) -> Result<SchemaType> {
            self.types
                .lock()
                .expect("lock")
                .insert(schema_type.id.clone(), schema_type.clone());
            Ok(schema_type.clone())
        }

        async fn get_type_inheritance(&self) -> Result<Vec<TypeInheritance>> {
            Ok(vec![])
        }

        async fn get_all_properties(&self) -> Result<Vec<TypeProperty>> {
            Ok(vec![])
        }

        async fn get_edge_endpoint_rules(&self) -> Result<Vec<EdgeEndpointRule>> {
            Ok(vec![])
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

    struct FakeGraphStore;

    #[async_trait]
    impl GraphStore for FakeGraphStore {
        async fn apply_delta(&self, _delta: &GraphDelta) -> Result<()> {
            Ok(())
        }
    }

    struct FakeEmbedder;

    #[async_trait]
    impl Embedder for FakeEmbedder {
        async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
            Ok(texts.iter().map(|_| vec![0.1_f32, 0.2_f32]).collect())
        }
    }

    struct CapturingVectorStore {
        seen: Arc<Mutex<Vec<EmbeddedBlock>>>,
    }

    #[async_trait]
    impl VectorStore for CapturingVectorStore {
        async fn upsert_blocks(&self, blocks: &[EmbeddedBlock]) -> Result<()> {
            let mut guard = self.seen.lock().expect("lock should be available");
            guard.extend(blocks.to_vec());
            Ok(())
        }
    }

    #[tokio::test]
    async fn rejects_invalid_schema_kind() {
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo::new()),
            Arc::new(FakeGraphStore),
            Arc::new(FakeEmbedder),
            Arc::new(CapturingVectorStore {
                seen: Arc::new(Mutex::new(vec![])),
            }),
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
            Arc::new(FakeGraphStore),
            Arc::new(FakeEmbedder),
            Arc::new(CapturingVectorStore {
                seen: Arc::new(Mutex::new(vec![])),
            }),
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
            Arc::new(FakeGraphStore),
            Arc::new(FakeEmbedder),
            Arc::new(CapturingVectorStore {
                seen: captured.clone(),
            }),
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
    async fn rejects_mismatched_scope_on_entities() {
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo::new()),
            Arc::new(FakeGraphStore),
            Arc::new(FakeEmbedder),
            Arc::new(CapturingVectorStore {
                seen: Arc::new(Mutex::new(vec![])),
            }),
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

        assert!(err
            .to_string()
            .contains("entity user_id must match request user_id"));
    }
}
