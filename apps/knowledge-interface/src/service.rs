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
