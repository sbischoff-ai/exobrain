use std::collections::HashMap;

use anyhow::{Context, Result};
use async_trait::async_trait;
use qdrant_client::{
    qdrant::{
        value::Kind, Condition, CreateCollectionBuilder, DeletePointsBuilder, Distance, Filter,
        PointId, PointStruct, ScoredPoint, SearchPointsBuilder, UpsertPointsBuilder, Value,
        VectorParamsBuilder,
    },
    Qdrant,
};

use crate::domain::{EmbeddedBlock, SchemaKind, SchemaType};
use crate::ports::TypeVectorRepository;

const QDRANT_VECTOR_SIZE: u64 = 3072;
pub(crate) const SCHEMA_NODE_TYPES_COLLECTION: &str = "schema_node_types";
pub(crate) const SCHEMA_EDGE_TYPES_COLLECTION: &str = "schema_edge_types";

pub struct QdrantVectorStore {
    client: Qdrant,
    collection: String,
    vector_size: u64,
}

pub struct QdrantTypeVectorStore {
    client: Qdrant,
    node_collection: String,
    edge_collection: String,
    vector_size: u64,
}

#[derive(Debug, Clone)]
pub struct TypeScoredCandidate {
    pub type_id: String,
    pub score: f32,
    pub payload: HashMap<String, Value>,
}

impl QdrantVectorStore {
    pub fn new(url: &str, collection: &str) -> Result<Self> {
        let normalized = normalize_qdrant_grpc_url(url);
        let client = Qdrant::from_url(&normalized).build()?;
        Ok(Self {
            client,
            collection: collection.to_string(),
            vector_size: QDRANT_VECTOR_SIZE,
        })
    }

    async fn ensure_collection(&self) -> Result<()> {
        if self.client.collection_exists(&self.collection).await? {
            return Ok(());
        }

        self.client
            .create_collection(
                CreateCollectionBuilder::new(&self.collection)
                    .vectors_config(VectorParamsBuilder::new(self.vector_size, Distance::Cosine)),
            )
            .await
            .with_context(|| format!("failed to create qdrant collection {}", self.collection))?;
        Ok(())
    }

    pub(crate) async fn upsert_blocks(&self, blocks: &[EmbeddedBlock]) -> Result<()> {
        if blocks.is_empty() {
            return Ok(());
        }

        for block in blocks {
            if block.vector.is_empty() {
                anyhow::bail!(
                    "block {} produced an empty embedding vector; cannot upsert to qdrant",
                    block.block.id
                );
            }
            if block.vector.len() as u64 != self.vector_size {
                anyhow::bail!(
                    "block {} embedding dimension {} does not match configured qdrant dimension {}",
                    block.block.id,
                    block.vector.len(),
                    self.vector_size
                );
            }
        }

        self.ensure_collection().await?;

        let points: Vec<PointStruct> = blocks.iter().map(to_point).collect();
        self.client
            .upsert_points(UpsertPointsBuilder::new(&self.collection, points).wait(true))
            .await?;

        Ok(())
    }

    pub(crate) async fn rollback_points(&self, blocks: &[EmbeddedBlock]) -> Result<()> {
        if blocks.is_empty() {
            return Ok(());
        }

        let ids: Vec<PointId> = blocks
            .iter()
            .map(|b| PointId::from(b.block.id.clone()))
            .collect();
        self.client
            .delete_points(
                DeletePointsBuilder::new(&self.collection)
                    .points(ids)
                    .wait(true),
            )
            .await?;
        Ok(())
    }

    pub(crate) async fn search(
        &self,
        vector: &[f32],
        limit: u64,
        user_id: &str,
    ) -> Result<Vec<ScoredPoint>> {
        let search = SearchPointsBuilder::new(&self.collection, vector.to_vec(), limit)
            .with_payload(true)
            .filter(qdrant_user_or_shared_access_filter(user_id));

        let response = self.client.search_points(search).await?;
        Ok(response.result)
    }
}

impl QdrantTypeVectorStore {
    pub fn new(url: &str) -> Result<Self> {
        let normalized = normalize_qdrant_grpc_url(url);
        let client = Qdrant::from_url(&normalized).build()?;
        Ok(Self {
            client,
            node_collection: SCHEMA_NODE_TYPES_COLLECTION.to_string(),
            edge_collection: SCHEMA_EDGE_TYPES_COLLECTION.to_string(),
            vector_size: QDRANT_VECTOR_SIZE,
        })
    }

    async fn ensure_collection(&self, collection: &str) -> Result<()> {
        if self.client.collection_exists(collection).await? {
            return Ok(());
        }

        self.client
            .create_collection(
                CreateCollectionBuilder::new(collection)
                    .vectors_config(VectorParamsBuilder::new(self.vector_size, Distance::Cosine)),
            )
            .await
            .with_context(|| format!("failed to create qdrant collection {collection}"))?;
        Ok(())
    }

    async fn ensure_collections(&self) -> Result<()> {
        self.ensure_collection(&self.node_collection).await?;
        self.ensure_collection(&self.edge_collection).await?;
        Ok(())
    }

    pub(crate) async fn upsert_schema_type(
        &self,
        schema_type: &SchemaType,
        vector: &[f32],
    ) -> Result<()> {
        if vector.is_empty() {
            anyhow::bail!(
                "schema type {} produced an empty embedding vector; cannot upsert to qdrant",
                schema_type.id
            );
        }
        if vector.len() as u64 != self.vector_size {
            anyhow::bail!(
                "schema type {} embedding dimension {} does not match configured qdrant dimension {}",
                schema_type.id,
                vector.len(),
                self.vector_size
            );
        }

        self.ensure_collections().await?;

        let collection = self.collection_for_kind(&schema_type.kind)?;
        let point = to_schema_type_point(schema_type, vector.to_vec())?;

        self.client
            .upsert_points(UpsertPointsBuilder::new(collection, vec![point]).wait(true))
            .await?;
        Ok(())
    }

    pub(crate) async fn search_node_types(
        &self,
        vector: &[f32],
        limit: u64,
    ) -> Result<Vec<TypeScoredCandidate>> {
        self.search_collection(&self.node_collection, vector, limit)
            .await
    }

    pub(crate) async fn search_edge_types(
        &self,
        vector: &[f32],
        limit: u64,
    ) -> Result<Vec<TypeScoredCandidate>> {
        self.search_collection(&self.edge_collection, vector, limit)
            .await
    }

    async fn search_collection(
        &self,
        collection: &str,
        vector: &[f32],
        limit: u64,
    ) -> Result<Vec<TypeScoredCandidate>> {
        self.ensure_collection(collection).await?;

        let search =
            SearchPointsBuilder::new(collection, vector.to_vec(), limit).with_payload(true);
        let response = self.client.search_points(search).await?;

        Ok(response
            .result
            .into_iter()
            .filter_map(|point| {
                let type_id = payload_string(&point.payload, "type_id")?;
                Some(TypeScoredCandidate {
                    type_id,
                    score: point.score,
                    payload: point.payload,
                })
            })
            .collect())
    }

    fn collection_for_kind(&self, kind: &str) -> Result<&str> {
        match SchemaKind::from_db_str(kind) {
            Some(SchemaKind::Node) => Ok(&self.node_collection),
            Some(SchemaKind::Edge) => Ok(&self.edge_collection),
            None => anyhow::bail!("unsupported schema type kind '{kind}'"),
        }
    }
}

pub(crate) fn payload_string(payload: &HashMap<String, Value>, key: &str) -> Option<String> {
    payload
        .get(key)
        .and_then(|value| value.kind.as_ref())
        .and_then(|kind| match kind {
            Kind::StringValue(value) => Some(value.clone()),
            _ => None,
        })
}

pub(crate) fn payload_i64(payload: &HashMap<String, Value>, key: &str) -> Option<i64> {
    payload
        .get(key)
        .and_then(|value| value.kind.as_ref())
        .and_then(|kind| match kind {
            Kind::IntegerValue(value) => Some(*value),
            Kind::DoubleValue(value) => Some(*value as i64),
            _ => None,
        })
}

pub(crate) fn normalize_qdrant_grpc_url(url: &str) -> String {
    let mut normalized = if url.starts_with("http://") || url.starts_with("https://") {
        url.to_string()
    } else {
        format!("http://{url}")
    };

    if normalized.ends_with(":6333") {
        normalized = format!("{}:6334", &normalized[..normalized.len() - 5]);
    } else if normalized.ends_with(":16333") {
        normalized = format!("{}:16334", &normalized[..normalized.len() - 6]);
    }

    normalized
}

pub(crate) fn qdrant_user_or_shared_access_filter(user_id: &str) -> Filter {
    Filter::should([
        Condition::matches("user_id", user_id.to_string()),
        Condition::matches("visibility", "SHARED".to_string()),
    ])
}

fn to_point(embedded: &EmbeddedBlock) -> PointStruct {
    let mut payload = HashMap::new();
    payload.insert(
        "block_id".to_string(),
        Value::from(embedded.block.id.clone()),
    );
    payload.insert(
        "universe_id".to_string(),
        Value::from(embedded.universe_id.clone()),
    );
    payload.insert("user_id".to_string(), Value::from(embedded.user_id.clone()));
    payload.insert(
        "visibility".to_string(),
        Value::from(match embedded.visibility {
            crate::domain::Visibility::Private => "PRIVATE".to_string(),
            crate::domain::Visibility::Shared => "SHARED".to_string(),
        }),
    );
    payload.insert("text".to_string(), Value::from(embedded.text.clone()));
    payload.insert(
        "root_entity_id".to_string(),
        Value::from(embedded.root_entity_id.clone()),
    );
    payload.insert("block_level".to_string(), Value::from(embedded.block_level));
    PointStruct::new(embedded.block.id.clone(), embedded.vector.clone(), payload)
}

fn to_schema_type_point(schema_type: &SchemaType, vector: Vec<f32>) -> Result<PointStruct> {
    let kind = match SchemaKind::from_db_str(&schema_type.kind) {
        Some(SchemaKind::Node) => "node",
        Some(SchemaKind::Edge) => "edge",
        None => anyhow::bail!("unsupported schema type kind '{}'", schema_type.kind),
    };

    let mut payload = HashMap::new();
    payload.insert("type_id".to_string(), Value::from(schema_type.id.clone()));
    payload.insert("kind".to_string(), Value::from(kind.to_string()));
    payload.insert("name".to_string(), Value::from(schema_type.name.clone()));
    payload.insert(
        "description".to_string(),
        Value::from(schema_type.description.clone()),
    );
    payload.insert("active".to_string(), Value::from(schema_type.active));

    Ok(PointStruct::new(schema_type.id.clone(), vector, payload))
}

pub(crate) fn render_schema_type_embedding_input(schema_type: &SchemaType) -> Result<String> {
    match SchemaKind::from_db_str(&schema_type.kind) {
        Some(SchemaKind::Node) => Ok(format!(
            "entity type: {}\n\ndescription:\n{}",
            schema_type.name, schema_type.description
        )),
        Some(SchemaKind::Edge) => Ok(format!(
            "relationship type: {}\n\ndescription:\n{}",
            schema_type.name, schema_type.description
        )),
        None => anyhow::bail!("unsupported schema type kind '{}'", schema_type.kind),
    }
}

#[async_trait]
impl TypeVectorRepository for QdrantTypeVectorStore {
    async fn upsert_schema_type_vector(
        &self,
        schema_type: &SchemaType,
        vector: &[f32],
    ) -> Result<()> {
        self.upsert_schema_type(schema_type, vector).await
    }
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_node_type_embedding_input() {
        let schema_type = SchemaType {
            id: "node.person".to_string(),
            kind: "node".to_string(),
            name: "person".to_string(),
            description: "A person entity".to_string(),
            active: true,
        };

        let input = render_schema_type_embedding_input(&schema_type).expect("input should render");
        assert_eq!(
            input,
            "entity type: person\n\ndescription:\nA person entity"
        );
    }

    #[test]
    fn renders_edge_type_embedding_input() {
        let schema_type = SchemaType {
            id: "edge.related_to".to_string(),
            kind: "edge".to_string(),
            name: "related_to".to_string(),
            description: "Connects related entities".to_string(),
            active: true,
        };

        let input = render_schema_type_embedding_input(&schema_type).expect("input should render");
        assert_eq!(
            input,
            "relationship type: related_to\n\ndescription:\nConnects related entities"
        );
    }

    #[test]
    fn creates_schema_point_payload_with_type_metadata() {
        let schema_type = SchemaType {
            id: "edge.related_to".to_string(),
            kind: "edge".to_string(),
            name: "related_to".to_string(),
            description: "Connects related entities".to_string(),
            active: false,
        };

        let point = to_schema_type_point(&schema_type, vec![0.1, 0.2]).expect("point should build");
        assert_eq!(
            payload_string(&point.payload, "type_id"),
            Some(schema_type.id)
        );
        assert_eq!(
            payload_string(&point.payload, "kind"),
            Some("edge".to_string())
        );
        assert_eq!(
            payload_string(&point.payload, "name"),
            Some(schema_type.name)
        );
        assert_eq!(
            payload_string(&point.payload, "description"),
            Some(schema_type.description)
        );
    }
}
