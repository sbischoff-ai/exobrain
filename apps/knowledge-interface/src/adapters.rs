use std::collections::HashMap;

use anyhow::{Context, Result};
use async_trait::async_trait;
use neo4rs::{query, Graph};
use qdrant_client::{
    qdrant::{PointStruct, UpsertPointsBuilder, Value},
    Qdrant,
};
use reqwest::header::{AUTHORIZATION, CONTENT_TYPE};
use serde::{Deserialize, Serialize};
use sqlx::{postgres::PgPoolOptions, PgPool, Row};

use crate::{
    domain::{EmbeddedBlock, GraphDelta, SchemaType},
    ports::{Embedder, GraphStore, SchemaRepository, VectorStore},
};

pub struct PostgresSchemaRepository {
    pool: PgPool,
}

impl PostgresSchemaRepository {
    pub async fn new(dsn: &str) -> Result<Self> {
        let pool = PgPoolOptions::new().max_connections(5).connect(dsn).await?;
        Ok(Self { pool })
    }
}

#[async_trait]
impl SchemaRepository for PostgresSchemaRepository {
    async fn ensure_schema(&self) -> Result<()> {
        sqlx::query(
            r#"CREATE TABLE IF NOT EXISTS knowledge_graph_schema_types (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                active BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"#,
        )
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    async fn get_by_kind(&self, kind: &str) -> Result<Vec<SchemaType>> {
        let rows = sqlx::query(
            "SELECT id, kind, name, description, active FROM knowledge_graph_schema_types WHERE kind = $1 ORDER BY name",
        )
        .bind(kind)
        .fetch_all(&self.pool)
        .await?;

        Ok(rows
            .into_iter()
            .map(|row| SchemaType {
                id: row.get("id"),
                kind: row.get("kind"),
                name: row.get("name"),
                description: row.get("description"),
                active: row.get("active"),
            })
            .collect())
    }

    async fn upsert(&self, schema_type: &SchemaType) -> Result<SchemaType> {
        let row = sqlx::query(
            r#"INSERT INTO knowledge_graph_schema_types (id, kind, name, description, active)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id)
            DO UPDATE SET kind = EXCLUDED.kind, name = EXCLUDED.name, description = EXCLUDED.description, active = EXCLUDED.active, updated_at = NOW()
            RETURNING id, kind, name, description, active"#,
        )
        .bind(&schema_type.id)
        .bind(&schema_type.kind)
        .bind(&schema_type.name)
        .bind(&schema_type.description)
        .bind(schema_type.active)
        .fetch_one(&self.pool)
        .await?;

        Ok(SchemaType {
            id: row.get("id"),
            kind: row.get("kind"),
            name: row.get("name"),
            description: row.get("description"),
            active: row.get("active"),
        })
    }
}

pub struct Neo4jGraphStore {
    graph: Graph,
}

impl Neo4jGraphStore {
    pub async fn new(uri: &str) -> Result<Self> {
        let graph = Graph::new(uri, "", "").await?;
        Ok(Self { graph })
    }
}

#[async_trait]
impl GraphStore for Neo4jGraphStore {
    async fn apply_delta(&self, delta: &GraphDelta) -> Result<()> {
        let entity_rows: Vec<HashMap<&str, String>> = delta
            .entities
            .iter()
            .map(|entity| {
                let mut row = HashMap::new();
                row.insert("id", entity.id.clone());
                row.insert("name", entity.name.clone());
                row.insert("universe_id", entity.universe_id.clone());
                row
            })
            .collect();

        if !entity_rows.is_empty() {
            self.graph
                .run(
                    query(
                        "UNWIND $rows AS row MERGE (e:Entity {id: row.id}) SET e.name = row.name MERGE (u:Universe {id: row.universe_id}) MERGE (e)-[:IS_PART_OF]->(u)",
                    )
                    .param("rows", entity_rows),
                )
                .await
                .context("failed to upsert entities")?;
        }

        let block_rows: Vec<HashMap<&str, String>> = delta
            .blocks
            .iter()
            .map(|block| {
                let mut row = HashMap::new();
                row.insert("id", block.id.clone());
                row.insert("text", block.text.clone());
                row.insert("root_entity_id", block.root_entity_id.clone());
                row
            })
            .collect();

        if !block_rows.is_empty() {
            self.graph
                .run(
                    query(
                        "UNWIND $rows AS row MERGE (b:Block {id: row.id}) SET b.text = row.text WITH row, b MATCH (e:Entity {id: row.root_entity_id}) MERGE (e)-[:DESCRIBED_BY]->(b)",
                    )
                    .param("rows", block_rows),
                )
                .await
                .context("failed to upsert blocks")?;
        }

        for edge in &delta.edges {
            let cypher = format!(
                "MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) MERGE (a)-[r:{}]->(b) SET r.confidence = $confidence, r.status = $status, r.context = $context",
                edge.edge_type
            );
            self.graph
                .run(
                    query(&cypher)
                        .param("from_id", edge.from_id.clone())
                        .param("to_id", edge.to_id.clone())
                        .param("confidence", edge.confidence.unwrap_or(1.0))
                        .param(
                            "status",
                            edge.status
                                .clone()
                                .unwrap_or_else(|| "asserted".to_string()),
                        )
                        .param("context", edge.context.clone().unwrap_or_default()),
                )
                .await
                .context("failed to upsert edge")?;
        }

        Ok(())
    }
}

pub struct OpenAiEmbedder {
    client: reqwest::Client,
    api_key: String,
    model: String,
}

impl OpenAiEmbedder {
    pub fn new(api_key: String, model: String) -> Self {
        Self {
            client: reqwest::Client::new(),
            api_key,
            model,
        }
    }
}

#[derive(Debug, Serialize)]
struct EmbeddingRequest<'a> {
    input: &'a [String],
    model: &'a str,
}

#[derive(Debug, Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingDatum>,
}

#[derive(Debug, Deserialize)]
struct EmbeddingDatum {
    embedding: Vec<f32>,
}

#[async_trait]
impl Embedder for OpenAiEmbedder {
    async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(vec![]);
        }

        let response: EmbeddingResponse = self
            .client
            .post("https://api.openai.com/v1/embeddings")
            .header(AUTHORIZATION, format!("Bearer {}", self.api_key))
            .header(CONTENT_TYPE, "application/json")
            .json(&EmbeddingRequest {
                input: texts,
                model: &self.model,
            })
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;

        Ok(response.data.into_iter().map(|d| d.embedding).collect())
    }
}

pub struct QdrantVectorStore {
    client: Qdrant,
    collection: String,
}

impl QdrantVectorStore {
    pub fn new(url: &str, collection: &str) -> Result<Self> {
        let client = Qdrant::from_url(url).build()?;
        Ok(Self {
            client,
            collection: collection.to_string(),
        })
    }
}

#[async_trait]
impl VectorStore for QdrantVectorStore {
    async fn upsert_blocks(&self, blocks: &[EmbeddedBlock]) -> Result<()> {
        if blocks.is_empty() {
            return Ok(());
        }

        let points: Vec<PointStruct> = blocks
            .iter()
            .map(|embedded| {
                let mut payload = HashMap::new();
                payload.insert(
                    "block_id".to_string(),
                    Value::from(embedded.block.id.clone()),
                );
                payload.insert(
                    "universe_id".to_string(),
                    Value::from(embedded.universe_id.clone()),
                );
                payload.insert("text".to_string(), Value::from(embedded.block.text.clone()));
                payload.insert(
                    "root_entity_id".to_string(),
                    Value::from(embedded.block.root_entity_id.clone()),
                );
                payload.insert(
                    "entity_ids".to_string(),
                    Value::from(embedded.entity_ids.join(",")),
                );

                PointStruct::new(embedded.block.id.clone(), embedded.vector.clone(), payload)
            })
            .collect();

        self.client
            .upsert_points(UpsertPointsBuilder::new(&self.collection, points).wait(true))
            .await?;
        Ok(())
    }
}
