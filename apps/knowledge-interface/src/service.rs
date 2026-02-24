use std::sync::Arc;

use anyhow::{anyhow, Result};

use crate::{
    domain::{
        EdgeEndpointRule, EmbeddedBlock, GraphDelta, SchemaType, TypeInheritance, TypeProperty,
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

    pub async fn get_schema(&self) -> Result<(Vec<SchemaType>, Vec<SchemaType>, Vec<SchemaType>)> {
        let node_types = self.schema_repository.get_by_kind("node").await?;
        let edge_types = self.schema_repository.get_by_kind("edge").await?;
        let block_types = self
            .schema_repository
            .get_block_compatibility_types()
            .await?;
        Ok((node_types, edge_types, block_types))
    }

    pub async fn upsert_schema_type(&self, schema_type: SchemaType) -> Result<SchemaType> {
        let canonical_kind = match schema_type.kind.as_str() {
            "node" => "node",
            "edge" => "edge",
            "block" => "node",
            _ => return Err(anyhow!("schema kind must be one of: node, edge, block")),
        };

        let canonical_id = if schema_type.id.starts_with("block.") {
            format!("node.{}", schema_type.id.trim_start_matches("block."))
        } else {
            schema_type.id
        };

        self.schema_repository
            .upsert(&SchemaType {
                id: canonical_id,
                kind: canonical_kind.to_string(),
                name: schema_type.name,
                description: schema_type.description,
                active: schema_type.active,
            })
            .await
    }

    pub async fn get_schema_inheritance(&self) -> Result<Vec<TypeInheritance>> {
        self.schema_repository.get_type_inheritance().await
    }

    pub async fn get_type_properties(&self, owner_type_id: &str) -> Result<Vec<TypeProperty>> {
        self.schema_repository
            .get_properties_for_type(owner_type_id)
            .await
    }

    pub async fn get_edge_endpoint_rules(&self) -> Result<Vec<EdgeEndpointRule>> {
        self.schema_repository.get_edge_endpoint_rules().await
    }

    pub async fn ingest_graph_delta(&self, delta: GraphDelta) -> Result<()> {
        self.graph_store.apply_delta(&delta).await?;

        let texts: Vec<String> = delta
            .blocks
            .iter()
            .map(|block| block.text.clone())
            .collect();
        let vectors = self.embedder.embed_texts(&texts).await?;

        let blocks: Vec<EmbeddedBlock> = delta
            .blocks
            .iter()
            .zip(vectors.into_iter())
            .map(|(block, vector)| EmbeddedBlock {
                block: block.clone(),
                universe_id: delta.universe_id.clone(),
                vector,
                entity_ids: vec![block.root_entity_id.clone()],
            })
            .collect();

        self.vector_store.upsert_blocks(&blocks).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};

    use async_trait::async_trait;

    use crate::{
        domain::{BlockNode, EntityNode, GraphEdge},
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

        async fn get_block_compatibility_types(&self) -> Result<Vec<SchemaType>> {
            Ok(vec![SchemaType {
                id: "node.block".to_string(),
                kind: "block".to_string(),
                name: "Block".to_string(),
                description: "compatibility".to_string(),
                active: true,
            }])
        }

        async fn upsert(&self, schema_type: &SchemaType) -> Result<SchemaType> {
            Ok(schema_type.clone())
        }

        async fn get_type_inheritance(&self) -> Result<Vec<TypeInheritance>> {
            Ok(vec![])
        }

        async fn get_properties_for_type(&self, _owner_type_id: &str) -> Result<Vec<TypeProperty>> {
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
    async fn canonicalizes_legacy_block_kind_and_id() {
        let app = KnowledgeApplication::new(
            Arc::new(FakeSchemaRepo),
            Arc::new(FakeGraphStore),
            Arc::new(FakeEmbedder),
            Arc::new(CapturingVectorStore {
                seen: Arc::new(Mutex::new(vec![])),
            }),
        );

        let schema = app
            .upsert_schema_type(SchemaType {
                id: "block.quote".to_string(),
                kind: "block".to_string(),
                name: "Quote".to_string(),
                description: "legacy".to_string(),
                active: true,
            })
            .await
            .expect("legacy block input should canonicalize");

        assert_eq!(schema.id, "node.quote");
        assert_eq!(schema.kind, "node");
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
                name: "Alex".to_string(),
                labels: vec!["Entity".to_string(), "Person".to_string()],
                universe_id: "real-life".to_string(),
                time_window: None,
            }],
            blocks: vec![BlockNode {
                id: "block.alex.root".to_string(),
                text: "Alex is a close friend from university.".to_string(),
                labels: vec!["Block".to_string()],
                root_entity_id: "person.alex".to_string(),
                confidence: Some(0.9),
                status: Some("asserted".to_string()),
            }],
            edges: vec![GraphEdge {
                from_id: "person.alex".to_string(),
                to_id: "person.alex".to_string(),
                edge_type: "RELATED_TO".to_string(),
                confidence: Some(0.4),
                status: Some("asserted".to_string()),
                context: Some("basic seed".to_string()),
            }],
        })
        .await
        .expect("ingestion should succeed");

        let guard = captured.lock().expect("lock should be available");
        assert_eq!(guard.len(), 1);
        assert_eq!(guard[0].block.id, "block.alex.root");
        assert_eq!(guard[0].vector.len(), 2);
        assert_eq!(guard[0].entity_ids, vec!["person.alex".to_string()]);
    }
}
