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
    domain::{
        EdgeEndpointRule, EmbeddedBlock, GraphDelta, PropertyScalar, PropertyValue, SchemaType,
        TypeInheritance, TypeProperty, UpsertSchemaTypePropertyInput, Visibility,
    },
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
    async fn get_by_kind(&self, kind: &str) -> Result<Vec<SchemaType>> {
        let rows = sqlx::query(
            "SELECT id, kind, name, description, active FROM knowledge_graph_schema_types WHERE kind = $1 AND active = TRUE ORDER BY name",
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

    async fn get_type_inheritance(&self) -> Result<Vec<TypeInheritance>> {
        let rows = sqlx::query(
            "SELECT child_type_id, parent_type_id, description, active FROM knowledge_graph_schema_type_inheritance WHERE active = TRUE ORDER BY child_type_id, parent_type_id",
        )
        .fetch_all(&self.pool)
        .await?;

        Ok(rows
            .into_iter()
            .map(|row| TypeInheritance {
                child_type_id: row.get("child_type_id"),
                parent_type_id: row.get("parent_type_id"),
                description: row.get("description"),
                active: row.get("active"),
            })
            .collect())
    }

    async fn get_all_properties(&self) -> Result<Vec<TypeProperty>> {
        let rows = sqlx::query(
            "SELECT owner_type_id, prop_name, value_type, required, readable, writable, active, description FROM knowledge_graph_schema_type_properties WHERE active = TRUE ORDER BY owner_type_id, prop_name",
        )
        .fetch_all(&self.pool)
        .await?;

        Ok(rows
            .into_iter()
            .map(|row| TypeProperty {
                owner_type_id: row.get("owner_type_id"),
                prop_name: row.get("prop_name"),
                value_type: row.get("value_type"),
                required: row.get("required"),
                readable: row.get("readable"),
                writable: row.get("writable"),
                active: row.get("active"),
                description: row.get("description"),
            })
            .collect())
    }

    async fn get_edge_endpoint_rules(&self) -> Result<Vec<EdgeEndpointRule>> {
        let rows = sqlx::query(
            "SELECT edge_type_id, from_node_type_id, to_node_type_id, active, description FROM knowledge_graph_schema_edge_rules WHERE active = TRUE ORDER BY edge_type_id, from_node_type_id, to_node_type_id",
        )
        .fetch_all(&self.pool)
        .await?;

        Ok(rows
            .into_iter()
            .map(|row| EdgeEndpointRule {
                edge_type_id: row.get("edge_type_id"),
                from_node_type_id: row.get("from_node_type_id"),
                to_node_type_id: row.get("to_node_type_id"),
                active: row.get("active"),
                description: row.get("description"),
            })
            .collect())
    }

    async fn get_schema_type(&self, id: &str) -> Result<Option<SchemaType>> {
        let row = sqlx::query(
            "SELECT id, kind, name, description, active FROM knowledge_graph_schema_types WHERE id = $1",
        )
        .bind(id)
        .fetch_optional(&self.pool)
        .await?;

        Ok(row.map(|row| SchemaType {
            id: row.get("id"),
            kind: row.get("kind"),
            name: row.get("name"),
            description: row.get("description"),
            active: row.get("active"),
        }))
    }

    async fn get_parent_for_child(&self, child_type_id: &str) -> Result<Option<String>> {
        let row = sqlx::query(
            "SELECT parent_type_id FROM knowledge_graph_schema_type_inheritance WHERE child_type_id = $1 AND active = TRUE LIMIT 1",
        )
        .bind(child_type_id)
        .fetch_optional(&self.pool)
        .await?;

        Ok(row.map(|r| r.get("parent_type_id")))
    }

    async fn is_descendant_of_entity(&self, node_type_id: &str) -> Result<bool> {
        if node_type_id == "node.entity" {
            return Ok(true);
        }

        let row = sqlx::query(
            r#"WITH RECURSIVE lineage AS (
                SELECT child_type_id, parent_type_id
                FROM knowledge_graph_schema_type_inheritance
                WHERE child_type_id = $1 AND active = TRUE
                UNION ALL
                SELECT i.child_type_id, i.parent_type_id
                FROM knowledge_graph_schema_type_inheritance i
                JOIN lineage l ON i.child_type_id = l.parent_type_id
                WHERE i.active = TRUE
            )
            SELECT 1 AS found FROM lineage WHERE parent_type_id = 'node.entity' LIMIT 1"#,
        )
        .bind(node_type_id)
        .fetch_optional(&self.pool)
        .await?;

        Ok(row.is_some())
    }

    async fn upsert_inheritance(
        &self,
        child_type_id: &str,
        parent_type_id: &str,
        description: &str,
    ) -> Result<()> {
        sqlx::query(
            r#"INSERT INTO knowledge_graph_schema_type_inheritance (child_type_id, parent_type_id, active, description, universe_id)
            VALUES ($1, $2, TRUE, $3, NULL)
            ON CONFLICT (child_type_id, parent_type_id)
            DO UPDATE SET active = TRUE, description = EXCLUDED.description"#,
        )
        .bind(child_type_id)
        .bind(parent_type_id)
        .bind(description)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    async fn upsert_type_property(
        &self,
        owner_type_id: &str,
        property: &UpsertSchemaTypePropertyInput,
    ) -> Result<()> {
        sqlx::query(
            r#"INSERT INTO knowledge_graph_schema_type_properties (owner_type_id, prop_name, value_type, required, readable, writable, active, description)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (owner_type_id, prop_name)
            DO UPDATE SET
              value_type = EXCLUDED.value_type,
              required = EXCLUDED.required,
              readable = EXCLUDED.readable,
              writable = EXCLUDED.writable,
              active = EXCLUDED.active,
              description = EXCLUDED.description"#,
        )
        .bind(owner_type_id)
        .bind(&property.prop_name)
        .bind(&property.value_type)
        .bind(property.required)
        .bind(property.readable)
        .bind(property.writable)
        .bind(property.active)
        .bind(&property.description)
        .execute(&self.pool)
        .await?;

        Ok(())
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
                row.insert(
                    "name",
                    prop_as_string(&entity.properties, "name").unwrap_or_default(),
                );
                row.insert("universe_id", entity.universe_id.clone());
                row.insert("user_id", entity.user_id.clone());
                row.insert(
                    "visibility",
                    visibility_as_str(entity.visibility).to_string(),
                );
                row
            })
            .collect();

        if !entity_rows.is_empty() {
            self.graph
                .run(
                    query(
                        "UNWIND $rows AS row MERGE (e:Entity {id: row.id}) SET e.name = row.name, e.user_id = row.user_id, e.visibility = row.visibility MERGE (u:Universe {id: row.universe_id}) MERGE (e)-[:IS_PART_OF]->(u)",
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
                row.insert(
                    "text",
                    prop_as_string(&block.properties, "text").unwrap_or_default(),
                );
                row.insert("root_entity_id", block.root_entity_id.clone());
                row.insert("user_id", block.user_id.clone());
                row.insert(
                    "visibility",
                    visibility_as_str(block.visibility).to_string(),
                );
                row
            })
            .collect();

        if !block_rows.is_empty() {
            self.graph
                .run(
                    query(
                        "UNWIND $rows AS row MERGE (b:Block {id: row.id}) SET b.text = row.text, b.user_id = row.user_id, b.visibility = row.visibility WITH row, b MATCH (e:Entity {id: row.root_entity_id}) WHERE e.user_id = row.user_id AND e.visibility = row.visibility MERGE (e)-[:DESCRIBED_BY]->(b)",
                    )
                    .param("rows", block_rows),
                )
                .await
                .context("failed to upsert blocks")?;
        }

        for edge in &delta.edges {
            validate_edge_type(&edge.edge_type)?;
            let cypher = format!(
                "MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) WHERE a.user_id = $user_id AND b.user_id = $user_id AND a.visibility = $visibility AND b.visibility = $visibility MERGE (a)-[r:{}]->(b) SET r.confidence = $confidence, r.status = $status, r.context = $context, r.user_id = $user_id, r.visibility = $visibility",
                edge.edge_type
            );
            self.graph
                .run(
                    query(&cypher)
                        .param("from_id", edge.from_id.clone())
                        .param("to_id", edge.to_id.clone())
                        .param("user_id", edge.user_id.clone())
                        .param("visibility", visibility_as_str(edge.visibility))
                        .param(
                            "confidence",
                            prop_as_float(&edge.properties, "confidence").unwrap_or(1.0),
                        )
                        .param(
                            "status",
                            prop_as_string(&edge.properties, "status")
                                .unwrap_or_else(|| "asserted".to_string()),
                        )
                        .param(
                            "context",
                            prop_as_string(&edge.properties, "context").unwrap_or_default(),
                        ),
                )
                .await
                .context("failed to upsert edge")?;
        }

        Ok(())
    }
}

fn prop_as_string(props: &[PropertyValue], key: &str) -> Option<String> {
    props.iter().find_map(|p| {
        if p.key != key {
            return None;
        }
        match &p.value {
            PropertyScalar::String(v) | PropertyScalar::Datetime(v) | PropertyScalar::Json(v) => {
                Some(v.clone())
            }
            _ => None,
        }
    })
}

fn prop_as_float(props: &[PropertyValue], key: &str) -> Option<f64> {
    props.iter().find_map(|p| {
        if p.key != key {
            return None;
        }
        match p.value {
            PropertyScalar::Float(v) => Some(v),
            PropertyScalar::Int(v) => Some(v as f64),
            _ => None,
        }
    })
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
                payload.insert("user_id".to_string(), Value::from(embedded.user_id.clone()));
                payload.insert(
                    "visibility".to_string(),
                    Value::from(visibility_as_str(embedded.visibility).to_string()),
                );
                payload.insert("text".to_string(), Value::from(embedded.text.clone()));
                payload.insert(
                    "root_entity_id".to_string(),
                    Value::from(embedded.block.root_entity_id.clone()),
                );
                payload.insert(
                    "entity_ids".to_string(),
                    Value::from(embedded.entity_ids.clone()),
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

fn visibility_as_str(visibility: Visibility) -> &'static str {
    match visibility {
        Visibility::Private => "PRIVATE",
        Visibility::Shared => "SHARED",
    }
}

fn validate_edge_type(edge_type: &str) -> Result<()> {
    let valid = !edge_type.is_empty()
        && edge_type
            .chars()
            .all(|ch| ch.is_ascii_uppercase() || ch.is_ascii_digit() || ch == '_');

    if !valid {
        anyhow::bail!("edge_type must be uppercase letters, numbers, or underscore");
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::validate_edge_type;

    #[test]
    fn validates_good_edge_type() {
        assert!(validate_edge_type("RELATED_TO").is_ok());
        assert!(validate_edge_type("PART_OF_2").is_ok());
    }

    #[test]
    fn rejects_unsafe_edge_type() {
        assert!(validate_edge_type("RELATED_TO); MATCH (n)").is_err());
        assert!(validate_edge_type("related_to").is_err());
    }
}
