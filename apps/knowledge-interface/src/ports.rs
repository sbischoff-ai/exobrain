use anyhow::Result;
use async_trait::async_trait;

use crate::domain::{
    EdgeEndpointRule, EmbeddedBlock, GraphDelta, SchemaType, TypeInheritance, TypeProperty,
};

#[async_trait]
pub trait SchemaRepository: Send + Sync {
    async fn get_by_kind(&self, kind: &str) -> Result<Vec<SchemaType>>;
    async fn upsert(&self, schema_type: &SchemaType) -> Result<SchemaType>;
    async fn get_type_inheritance(&self) -> Result<Vec<TypeInheritance>>;
    async fn get_all_properties(&self) -> Result<Vec<TypeProperty>>;
    async fn get_edge_endpoint_rules(&self) -> Result<Vec<EdgeEndpointRule>>;
}

#[async_trait]
pub trait GraphStore: Send + Sync {
    async fn apply_delta(&self, delta: &GraphDelta) -> Result<()>;
}

#[async_trait]
pub trait Embedder: Send + Sync {
    async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;
}

#[async_trait]
pub trait VectorStore: Send + Sync {
    async fn upsert_blocks(&self, blocks: &[EmbeddedBlock]) -> Result<()>;
}
