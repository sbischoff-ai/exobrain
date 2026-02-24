use std::sync::Arc;

use anyhow::{anyhow, Result};

use crate::{
    domain::{EmbeddedBlock, FullSchema, GraphDelta, PropertyScalar, SchemaType},
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
        Ok(FullSchema {
            node_types: self.schema_repository.get_by_kind("node").await?,
            edge_types: self.schema_repository.get_by_kind("edge").await?,
            inheritance: self.schema_repository.get_type_inheritance().await?,
            properties: self.schema_repository.get_all_properties().await?,
            edge_rules: self.schema_repository.get_edge_endpoint_rules().await?,
        })
    }

    pub async fn upsert_schema_type(&self, schema_type: SchemaType) -> Result<SchemaType> {
        if !matches!(schema_type.kind.as_str(), "node" | "edge") {
            return Err(anyhow!("schema kind must be one of: node, edge"));
        }
        self.schema_repository.upsert(&schema_type).await
    }

    pub async fn ingest_graph_delta(&self, delta: GraphDelta) -> Result<()> {
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
                vector,
                entity_ids: vec![block.root_entity_id.clone()],
                text,
            })
            .collect();

        self.vector_store.upsert_blocks(&blocks).await
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};

    use async_trait::async_trait;

    use crate::{
        domain::{
            BlockNode, EdgeEndpointRule, EntityNode, GraphEdge, PropertyValue, TypeInheritance,
            TypeProperty,
        },
        ports::{Embedder, GraphStore, SchemaRepository, VectorStore},
    };

    struct FakeSchemaRepo;

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
            Arc::new(FakeSchemaRepo),
            Arc::new(FakeGraphStore),
            Arc::new(FakeEmbedder),
            Arc::new(CapturingVectorStore {
                seen: Arc::new(Mutex::new(vec![])),
            }),
        );

        let err = app
            .upsert_schema_type(SchemaType {
                id: "x".to_string(),
                kind: "invalid".to_string(),
                name: "x".to_string(),
                description: String::new(),
                active: true,
            })
            .await
            .expect_err("invalid schema kind should fail");

        assert!(err.to_string().contains("schema kind must be one of"));
    }

    #[tokio::test]
    async fn ingests_blocks_and_creates_embeddings() {
        let captured = Arc::new(Mutex::new(vec![]));
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo),
            Arc::new(FakeGraphStore),
            Arc::new(FakeEmbedder),
            Arc::new(CapturingVectorStore {
                seen: captured.clone(),
            }),
        );

        app.ingest_graph_delta(GraphDelta {
            universe_id: "real-life".to_string(),
            entities: vec![EntityNode {
                id: "person.alex".to_string(),
                labels: vec!["Entity".to_string(), "Person".to_string()],
                universe_id: "real-life".to_string(),
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Alex".to_string()),
                }],
            }],
            blocks: vec![BlockNode {
                id: "block.alex.root".to_string(),
                labels: vec!["Block".to_string()],
                root_entity_id: "person.alex".to_string(),
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Alex is a close friend.".to_string()),
                }],
            }],
            edges: vec![GraphEdge {
                from_id: "person.alex".to_string(),
                to_id: "person.alex".to_string(),
                edge_type: "RELATED_TO".to_string(),
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
    }
}
