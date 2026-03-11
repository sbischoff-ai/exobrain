use std::collections::{HashMap, HashSet};

use anyhow::{Context, Result};
use async_trait::async_trait;
use qdrant_client::{
    qdrant::{
        value::Kind, Condition, CreateCollectionBuilder, DeletePointsBuilder, Distance, Filter,
        PointId, PointStruct, ScoredPoint, ScrollPointsBuilder, SearchPointsBuilder,
        UpsertPointsBuilder, Value, VectorParamsBuilder,
    },
    Qdrant,
};
use uuid::{uuid, Uuid};

use crate::domain::{EmbeddedBlock, SchemaKind, SchemaType, TypeCandidate};
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
    ) -> Result<Vec<TypeCandidate>> {
        self.search_collection(&self.node_collection, vector, limit)
            .await
    }

    pub(crate) async fn search_edge_types(
        &self,
        vector: &[f32],
        limit: u64,
    ) -> Result<Vec<TypeCandidate>> {
        self.search_collection(&self.edge_collection, vector, limit)
            .await
    }

    async fn search_collection(
        &self,
        collection: &str,
        vector: &[f32],
        limit: u64,
    ) -> Result<Vec<TypeCandidate>> {
        self.ensure_collection(collection).await?;

        let search =
            SearchPointsBuilder::new(collection, vector.to_vec(), limit).with_payload(true);
        let response = self.client.search_points(search).await?;

        Ok(type_candidates_from_scored_points(response.result))
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

    let point_id = schema_type_point_uuid(&schema_type.id);

    Ok(PointStruct::new(point_id.to_string(), vector, payload))
}

// Qdrant point IDs must be UUID or u64, so business IDs like `node.*` cannot be used directly.
fn schema_type_point_uuid(type_id: &str) -> Uuid {
    const SCHEMA_TYPE_VECTOR_NAMESPACE: Uuid = uuid!("4eb19fec-bee2-5362-a80f-fe43dcf0ed08");
    Uuid::new_v5(&SCHEMA_TYPE_VECTOR_NAMESPACE, type_id.as_bytes())
}

fn type_candidates_from_scored_points(mut points: Vec<ScoredPoint>) -> Vec<TypeCandidate> {
    points.sort_by(|left, right| right.score.total_cmp(&left.score));

    points
        .into_iter()
        .filter_map(|point| {
            let type_id = payload_string(&point.payload, "type_id")?;
            let name = payload_string(&point.payload, "name")?;
            let description = payload_string(&point.payload, "description")?;
            Some(TypeCandidate {
                type_id,
                name,
                description,
                score: point.score as f64,
            })
        })
        .collect()
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

    async fn search_node_type_candidates(
        &self,
        vector: &[f32],
        limit: u64,
    ) -> Result<Vec<TypeCandidate>> {
        self.search_node_types(vector, limit).await
    }

    async fn search_edge_type_candidates(
        &self,
        vector: &[f32],
        limit: u64,
    ) -> Result<Vec<TypeCandidate>> {
        self.search_edge_types(vector, limit).await
    }

    async fn get_schema_type_ids_by_kind(&self, kind: SchemaKind) -> Result<HashSet<String>> {
        let collection = match kind {
            SchemaKind::Node => &self.node_collection,
            SchemaKind::Edge => &self.edge_collection,
        };

        self.ensure_collection(collection).await?;

        let mut type_ids = HashSet::new();
        let mut next_offset = None;

        loop {
            let mut request = ScrollPointsBuilder::new(collection)
                .limit(256)
                .with_payload(true);
            if let Some(offset) = next_offset.clone() {
                request = request.offset(offset);
            }

            let response = self.client.scroll(request).await?;

            for point in response.result {
                if let Some(type_id) = payload_string(&point.payload, "type_id") {
                    type_ids.insert(type_id);
                }
            }

            match response.next_page_offset {
                Some(offset) => next_offset = Some(offset),
                None => break,
            }
        }

        Ok(type_ids)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use qdrant_client::qdrant::{point_id::PointIdOptions, PointId, Value};

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
        let point_id = point
            .id
            .as_ref()
            .and_then(|id| id.point_id_options.as_ref())
            .and_then(|id| match id {
                PointIdOptions::Uuid(value) => Some(value.clone()),
                _ => None,
            })
            .expect("schema type point should use UUID id");

        assert!(Uuid::parse_str(&point_id).is_ok());
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

    #[test]
    fn decodes_schema_type_payload_fields_from_point() {
        let schema_type = SchemaType {
            id: "node.person".to_string(),
            kind: "node".to_string(),
            name: "Person".to_string(),
            description: "A human being".to_string(),
            active: true,
        };

        let point = to_schema_type_point(&schema_type, vec![0.1, 0.2]).expect("point should build");
        assert_eq!(
            payload_string(&point.payload, "type_id"),
            Some("node.person".to_string())
        );
        assert_eq!(
            payload_string(&point.payload, "name"),
            Some("Person".to_string())
        );
        assert_eq!(
            payload_string(&point.payload, "description"),
            Some("A human being".to_string())
        );
    }

    #[test]
    fn maps_schema_type_id_to_deterministic_point_uuid() {
        let type_id = "node.ai_agent";
        let left = schema_type_point_uuid(type_id);
        let right = schema_type_point_uuid(type_id);

        assert_eq!(left, right);
    }

    #[test]
    fn maps_type_candidates_and_orders_by_descending_score() {
        let mut high_payload = HashMap::new();
        high_payload.insert(
            "type_id".to_string(),
            Value::from("edge.assigned_to".to_string()),
        );
        high_payload.insert("name".to_string(), Value::from("ASSIGNED_TO".to_string()));
        high_payload.insert(
            "description".to_string(),
            Value::from("assignment".to_string()),
        );

        let mut low_payload = HashMap::new();
        low_payload.insert(
            "type_id".to_string(),
            Value::from("edge.related_to".to_string()),
        );
        low_payload.insert("name".to_string(), Value::from("RELATED_TO".to_string()));
        low_payload.insert(
            "description".to_string(),
            Value::from("relation".to_string()),
        );

        let points = vec![
            ScoredPoint {
                id: Some(PointId {
                    point_id_options: Some(PointIdOptions::Uuid("2".to_string())),
                }),
                payload: low_payload,
                score: 0.2,
                vectors: None,
                shard_key: None,
                order_value: None,
                version: 0,
            },
            ScoredPoint {
                id: Some(PointId {
                    point_id_options: Some(PointIdOptions::Uuid("1".to_string())),
                }),
                payload: high_payload,
                score: 0.9,
                vectors: None,
                shard_key: None,
                order_value: None,
                version: 0,
            },
        ];

        let mapped = type_candidates_from_scored_points(points);
        assert_eq!(mapped.len(), 2);
        assert_eq!(mapped[0].type_id, "edge.assigned_to");
        assert_eq!(mapped[0].name, "ASSIGNED_TO");
        assert_eq!(mapped[0].description, "assignment");
        assert!((mapped[0].score - 0.9).abs() < 1e-6);
        assert_eq!(mapped[1].type_id, "edge.related_to");
        assert!((mapped[1].score - 0.2).abs() < 1e-6);
    }
}
