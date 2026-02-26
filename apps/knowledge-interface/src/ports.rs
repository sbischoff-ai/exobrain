use anyhow::Result;
use async_trait::async_trait;

use crate::domain::{
    EdgeEndpointRule, EmbeddedBlock, ExistingBlockContext, GraphDelta, SchemaType, TypeInheritance,
    TypeProperty, UpsertSchemaTypePropertyInput,
};

#[async_trait]
pub trait SchemaRepository: Send + Sync {
    async fn get_by_kind(&self, kind: &str) -> Result<Vec<SchemaType>>;
    async fn upsert(&self, schema_type: &SchemaType) -> Result<SchemaType>;
    async fn get_type_inheritance(&self) -> Result<Vec<TypeInheritance>>;
    async fn get_all_properties(&self) -> Result<Vec<TypeProperty>>;
    async fn get_edge_endpoint_rules(&self) -> Result<Vec<EdgeEndpointRule>>;

    async fn get_schema_type(&self, id: &str) -> Result<Option<SchemaType>>;
    async fn get_parent_for_child(&self, child_type_id: &str) -> Result<Option<String>>;
    async fn is_descendant_of_entity(&self, node_type_id: &str) -> Result<bool>;
    async fn upsert_inheritance(
        &self,
        child_type_id: &str,
        parent_type_id: &str,
        description: &str,
    ) -> Result<()>;
    async fn upsert_type_property(
        &self,
        owner_type_id: &str,
        property: &UpsertSchemaTypePropertyInput,
    ) -> Result<()>;
}

#[async_trait]
pub trait GraphRepository: Send + Sync {
    async fn apply_delta_with_blocks(
        &self,
        delta: &GraphDelta,
        blocks: &[EmbeddedBlock],
    ) -> Result<()>;
    async fn common_root_graph_exists(&self) -> Result<bool>;
    async fn get_existing_block_context(
        &self,
        block_id: &str,
        user_id: &str,
        visibility: crate::domain::Visibility,
    ) -> Result<Option<ExistingBlockContext>>;
}

#[async_trait]
pub trait Embedder: Send + Sync {
    async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;
}
