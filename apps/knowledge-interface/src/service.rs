use std::sync::Arc;

use anyhow::{anyhow, Result};

use crate::{
    domain::{EmbeddedBlock, GraphDelta, SchemaType},
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

    pub async fn ensure_schema(&self) -> Result<()> {
        self.schema_repository.ensure_schema().await
    }

    pub async fn get_schema(&self) -> Result<(Vec<SchemaType>, Vec<SchemaType>, Vec<SchemaType>)> {
        let node_types = self.schema_repository.get_by_kind("node").await?;
        let edge_types = self.schema_repository.get_by_kind("edge").await?;
        let block_types = self.schema_repository.get_by_kind("block").await?;
        Ok((node_types, edge_types, block_types))
    }

    pub async fn upsert_schema_type(&self, schema_type: SchemaType) -> Result<SchemaType> {
        if !matches!(schema_type.kind.as_str(), "node" | "edge" | "block") {
            return Err(anyhow!("schema kind must be one of: node, edge, block"));
        }
        self.schema_repository.upsert(&schema_type).await
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
        async fn ensure_schema(&self) -> Result<()> {
            Ok(())
        }

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
