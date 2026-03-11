use std::collections::HashMap;

use anyhow::{Context, Result};
use qdrant_client::{
    qdrant::{
        value::Kind, Condition, CreateCollectionBuilder, DeletePointsBuilder, Distance, Filter,
        PointId, PointStruct, ScoredPoint, SearchPointsBuilder, UpsertPointsBuilder, Value,
        VectorParamsBuilder,
    },
    Qdrant,
};

use crate::domain::EmbeddedBlock;

pub struct QdrantVectorStore {
    client: Qdrant,
    collection: String,
    vector_size: u64,
}

impl QdrantVectorStore {
    pub fn new(url: &str, collection: &str) -> Result<Self> {
        let normalized = normalize_qdrant_grpc_url(url);
        let client = Qdrant::from_url(&normalized).build()?;
        Ok(Self {
            client,
            collection: collection.to_string(),
            vector_size: 3072,
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
