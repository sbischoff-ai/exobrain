use std::collections::HashMap;

use anyhow::{Context, Result};
use async_trait::async_trait;
use neo4rs::{query, ConfigBuilder, Graph, Txn};
use qdrant_client::{
    qdrant::{
        value::Kind, Condition, CreateCollectionBuilder, DeletePointsBuilder, Distance, Filter,
        PointId, PointStruct, SearchPointsBuilder, UpsertPointsBuilder, Value, VectorParamsBuilder,
    },
    Qdrant,
};
use reqwest::header::CONTENT_TYPE;
use serde::{Deserialize, Serialize};
use sqlx::{postgres::PgPoolOptions, PgPool, Row};
use tracing::warn;

use crate::{
    domain::{
        EdgeEndpointRule, EmbeddedBlock, EntityCandidate, ExistingBlockContext,
        FindEntityCandidatesQuery, GraphDelta, NodeRelationshipCounts, PropertyScalar,
        PropertyValue, SchemaType, TypeInheritance, TypeProperty, UpsertSchemaTypePropertyInput,
        Visibility,
    },
    ports::{Embedder, GraphRepository, SchemaRepository},
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
    pub async fn new(uri: &str, database: &str) -> Result<Self> {
        let config = ConfigBuilder::default()
            .uri(uri)
            .user("")
            .password("")
            .db(database)
            .build()?;
        let graph = Graph::connect(config).await?;
        Ok(Self { graph })
    }

    async fn apply_delta_in_tx(&self, txn: &mut Txn, delta: &GraphDelta) -> Result<()> {
        let universe_aliases = "[]".to_string();
        for universe in &delta.universes {
            txn.run(
                query("MERGE (u:Universe {id: $id}) SET u.name = $name, u.aliases = $aliases, u.user_id = $user_id, u.visibility = $visibility")
                    .param("id", universe.id.clone())
                    .param("name", universe.name.clone())
                    .param("aliases", universe_aliases.clone())
                    .param("user_id", universe.user_id.clone())
                    .param("visibility", visibility_as_str(universe.visibility)),
            )
            .await
            .context("failed to upsert universe")?;
        }

        for entity in &delta.entities {
            let labels = sanitize_labels(&entity.resolved_labels)?;
            let cypher = format!(
                "MERGE (e:{} {{id: $id}}) SET e.type_id = $type_id, e.name = $name, e.aliases = $aliases, e.user_id = $user_id, e.visibility = $visibility WITH e MATCH (u:Universe {{id: $universe_id}}) MERGE (e)-[:IS_PART_OF]->(u)",
                labels.join(":"),
            );
            txn.run(
                query(&cypher)
                    .param("id", entity.id.clone())
                    .param("type_id", entity.type_id.clone())
                    .param(
                        "name",
                        prop_as_string(&entity.properties, "name").unwrap_or_default(),
                    )
                    .param(
                        "aliases",
                        prop_as_string(&entity.properties, "aliases")
                            .unwrap_or_else(|| "[]".to_string()),
                    )
                    .param("user_id", entity.user_id.clone())
                    .param("visibility", visibility_as_str(entity.visibility))
                    .param(
                        "universe_id",
                        entity
                            .universe_id
                            .clone()
                            .unwrap_or_else(|| "9d7f0fa5-78c1-4805-9efb-3f8f16090d7f".to_string()),
                    ),
            )
            .await
            .context("failed to upsert entity")?;
        }

        for block in &delta.blocks {
            let labels = sanitize_labels(&block.resolved_labels)?;
            let cypher = format!(
                "MERGE (b:{} {{id: $id}}) SET b.type_id = $type_id, b.text = $text, b.user_id = $user_id, b.visibility = $visibility",
                labels.join(":"),
            );
            txn.run(
                query(&cypher)
                    .param("id", block.id.clone())
                    .param("type_id", block.type_id.clone())
                    .param(
                        "text",
                        prop_as_string(&block.properties, "text").unwrap_or_default(),
                    )
                    .param("user_id", block.user_id.clone())
                    .param("visibility", visibility_as_str(block.visibility)),
            )
            .await
            .context("failed to upsert block")?;
        }

        for edge in &delta.edges {
            validate_edge_type(&edge.edge_type)?;
            let allowed_node_visibilities = allowed_node_visibilities(edge.visibility);
            let cypher = format!("MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) WHERE a.visibility IN $allowed_node_visibilities AND b.visibility IN $allowed_node_visibilities MERGE (a)-[r:{}]->(b) SET r.confidence = $confidence, r.status = $status, r.context = $context, r.user_id = $user_id, r.visibility = $visibility RETURN COUNT(r) AS upserted_count", edge.edge_type);
            let mut result = txn
                .execute(
                    query(&cypher)
                        .param("from_id", edge.from_id.clone())
                        .param("to_id", edge.to_id.clone())
                        .param("user_id", edge.user_id.clone())
                        .param("visibility", visibility_as_str(edge.visibility))
                        .param("allowed_node_visibilities", allowed_node_visibilities)
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

            let upserted_count = result
                .next(&mut *txn)
                .await?
                .and_then(|row| row.get::<i64>("upserted_count").ok())
                .unwrap_or(0);
            if upserted_count == 0 {
                return Err(anyhow::anyhow!(
                    "failed to upsert edge {} from {} to {} with user_id={} visibility={}",
                    edge.edge_type,
                    edge.from_id,
                    edge.to_id,
                    edge.user_id,
                    visibility_as_str(edge.visibility),
                ));
            }
        }

        Ok(())
    }

    async fn common_root_graph_exists(&self) -> Result<bool> {
        let mut result = self
            .graph
            .execute(query("MATCH (e:Entity {id: '8c75cc89-6204-4fed-aec1-34d032ff95ee', user_id: 'exobrain', visibility: 'SHARED'})-[:IS_PART_OF]->(:Universe {id: '9d7f0fa5-78c1-4805-9efb-3f8f16090d7f'}) MATCH (e)-[:DESCRIBED_BY]->(:Block {id: 'ea5ca80f-346b-4f66-bff2-d307ce5d7da9', user_id: 'exobrain', visibility: 'SHARED'}) RETURN 1 AS present LIMIT 1"))
            .await
            .context("failed to query common root graph")?;

        Ok(result.next().await?.is_some())
    }

    async fn user_graph_needs_initialization(&self, user_id: &str) -> Result<bool> {
        Ok(!self.is_user_graph_initialized(user_id).await?)
    }

    async fn is_user_graph_initialized(&self, user_id: &str) -> Result<bool> {
        let mut result = self
            .graph
            .execute(
                query(
                    "MATCH (:GraphInitialization {user_id: $user_id, visibility: 'SHARED'}) RETURN 1 AS present LIMIT 1",
                )
                .param("user_id", user_id.to_string()),
            )
            .await
            .context("failed to query user graph initialization marker")?;

        Ok(result.next().await?.is_some())
    }

    async fn mark_user_graph_initialized(&self, user_id: &str) -> Result<()> {
        self.graph
            .run(
                query(
                    "MERGE (m:GraphInitialization {user_id: $user_id}) SET m.visibility = 'SHARED'",
                )
                .param("user_id", user_id.to_string()),
            )
            .await
            .context("failed to mark user graph initialized")?;

        Ok(())
    }

    async fn get_existing_block_context(
        &self,
        block_id: &str,
        user_id: &str,
        visibility: Visibility,
    ) -> Result<Option<ExistingBlockContext>> {
        let allowed_node_visibilities = allowed_node_visibilities(visibility);
        let mut result = self
            .graph
            .execute(
                query(
                    "MATCH (e:Entity)-[:DESCRIBED_BY]->(root:Block)                      MATCH p=(root)-[:SUMMARIZES*0..]->(b:Block {id: $block_id})                      WHERE e.user_id = $user_id AND root.user_id = $user_id AND b.user_id = $user_id                      AND e.visibility IN $allowed_node_visibilities                      AND root.visibility IN $allowed_node_visibilities                      AND b.visibility IN $allowed_node_visibilities                      OPTIONAL MATCH (e)-[:IS_PART_OF]->(u:Universe)                      RETURN e.id AS root_entity_id, COALESCE(u.id, $default_universe_id) AS universe_id, length(p) AS block_level                      ORDER BY block_level ASC LIMIT 1",
                )
                .param("block_id", block_id.to_string())
                .param("user_id", user_id.to_string())
                .param("allowed_node_visibilities", allowed_node_visibilities)
                .param("default_universe_id", "9d7f0fa5-78c1-4805-9efb-3f8f16090d7f".to_string()),
            )
            .await
            .context("failed to query existing block context")?;

        let Some(row) = result.next().await? else {
            return Ok(None);
        };

        Ok(Some(ExistingBlockContext {
            root_entity_id: row.get("root_entity_id")?,
            universe_id: row.get("universe_id")?,
            block_level: row.get("block_level")?,
        }))
    }

    async fn get_node_relationship_counts(&self, node_id: &str) -> Result<NodeRelationshipCounts> {
        let mut result = self
            .graph
            .execute(query(
                "MATCH (n {id: $node_id}) OPTIONAL MATCH (n)-[out]->() WITH n, COUNT(out) AS outgoing OPTIONAL MATCH ()-[incoming]->(n) WITH n, outgoing, COUNT(incoming) AS incoming OPTIONAL MATCH (n)-[is_part_of:IS_PART_OF]->(:Universe) WITH n, outgoing, incoming, COUNT(is_part_of) AS entity_is_part_of OPTIONAL MATCH ()-[parent:DESCRIBED_BY|SUMMARIZES]->(n) RETURN incoming + outgoing AS total, entity_is_part_of, COUNT(parent) AS block_parent_edges",
            ).param("node_id", node_id.to_string()))
            .await
            .context("failed to query node relationship counts")?;

        let Some(row) = result.next().await? else {
            return Ok(NodeRelationshipCounts::default());
        };

        Ok(NodeRelationshipCounts {
            total: row.get::<i64>("total")? as usize,
            entity_is_part_of: row.get::<i64>("entity_is_part_of")? as usize,
            block_parent_edges: row.get::<i64>("block_parent_edges")? as usize,
        })
    }
}

fn allowed_node_visibilities(edge_visibility: Visibility) -> Vec<String> {
    match edge_visibility {
        Visibility::Private => vec!["PRIVATE".to_string(), "SHARED".to_string()],
        Visibility::Shared => vec!["SHARED".to_string()],
    }
}

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

    async fn upsert_blocks(&self, blocks: &[EmbeddedBlock]) -> Result<()> {
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

    async fn rollback_points(&self, blocks: &[EmbeddedBlock]) -> Result<()> {
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
}

pub struct MemgraphQdrantGraphRepository {
    graph_store: Neo4jGraphStore,
    vector_store: QdrantVectorStore,
}

impl MemgraphQdrantGraphRepository {
    pub fn new(graph_store: Neo4jGraphStore, vector_store: QdrantVectorStore) -> Self {
        Self {
            graph_store,
            vector_store,
        }
    }
}

#[async_trait]
impl GraphRepository for MemgraphQdrantGraphRepository {
    async fn apply_delta_with_blocks(
        &self,
        delta: &GraphDelta,
        blocks: &[EmbeddedBlock],
    ) -> Result<()> {
        let mut txn = self
            .graph_store
            .graph
            .start_txn()
            .await
            .context("failed to start memgraph transaction")?;
        if let Err(err) = self.graph_store.apply_delta_in_tx(&mut txn, delta).await {
            let _ = txn.rollback().await;
            return Err(err);
        }

        if let Err(err) = self.vector_store.upsert_blocks(blocks).await {
            let _ = txn.rollback().await;
            return Err(err.context("qdrant upsert failed; memgraph transaction rolled back"));
        }

        if let Err(err) = txn.commit().await {
            warn!(error = ?err, "memgraph commit failed after qdrant upsert; reverting qdrant points");
            let _ = self.vector_store.rollback_points(blocks).await;
            return Err(err.into());
        }

        Ok(())
    }

    async fn common_root_graph_exists(&self) -> Result<bool> {
        self.graph_store.common_root_graph_exists().await
    }

    async fn user_graph_needs_initialization(&self, user_id: &str) -> Result<bool> {
        self.graph_store
            .user_graph_needs_initialization(user_id)
            .await
    }

    async fn is_user_graph_initialized(&self, user_id: &str) -> Result<bool> {
        self.graph_store.is_user_graph_initialized(user_id).await
    }

    async fn mark_user_graph_initialized(&self, user_id: &str) -> Result<()> {
        self.graph_store.mark_user_graph_initialized(user_id).await
    }

    async fn get_existing_block_context(
        &self,
        block_id: &str,
        user_id: &str,
        visibility: Visibility,
    ) -> Result<Option<ExistingBlockContext>> {
        self.graph_store
            .get_existing_block_context(block_id, user_id, visibility)
            .await
    }

    async fn get_node_relationship_counts(&self, node_id: &str) -> Result<NodeRelationshipCounts> {
        self.graph_store.get_node_relationship_counts(node_id).await
    }

    async fn find_entity_candidates(
        &self,
        find_query: &FindEntityCandidatesQuery,
        query_vector: Option<&[f32]>,
    ) -> Result<Vec<EntityCandidate>> {
        let names = find_query.names.clone();
        let has_names = !names.is_empty();
        let potential_type_ids = find_query.potential_type_ids.clone();
        let has_type_filter = !potential_type_ids.is_empty();

        let mut cypher = format!(
            "MATCH (e:Entity) WHERE {}",
            memgraph_user_or_shared_access_clause("e")
        );
        if has_names {
            cypher.push_str(" AND (");
            cypher.push_str("ANY(name IN $names WHERE toLower(e.name) CONTAINS name)");
            cypher.push_str(" OR ");
            cypher.push_str(
                "ANY(alias IN COALESCE(e.aliases, []) WHERE ANY(name IN $names WHERE toLower(alias) CONTAINS name))",
            );
            cypher.push(')');
        }
        if has_type_filter {
            cypher.push_str(" AND e.type_id IN $potential_type_ids");
        }
        cypher.push_str(
            " RETURN e.id AS id, e.name AS name, e.type_id AS type_id, e.aliases AS aliases",
        );

        let mut name_matches = self
            .graph_store
            .graph
            .execute(
                query(&cypher)
                    .param("user_id", find_query.user_id.clone())
                    .param("names", names.clone())
                    .param("potential_type_ids", potential_type_ids.clone()),
            )
            .await
            .context("failed to fetch name candidates from memgraph")?;

        let mut aggregated: HashMap<String, AggregatedCandidate> = HashMap::new();
        while let Some(row) = name_matches.next().await? {
            let id: String = row.get("id")?;
            let entity_name: String = row.get("name")?;
            let type_id: String = row.get("type_id")?;
            let aliases: Option<Vec<String>> = row.get("aliases")?;

            let (name_score, matched_tokens) =
                compute_name_score(&names, &entity_name, aliases.as_deref());

            let entry = aggregated
                .entry(id.clone())
                .or_insert_with(|| AggregatedCandidate {
                    id: id.clone(),
                    name: entity_name.clone(),
                    type_id: type_id.clone(),
                    name_score,
                    semantic_score_weighted: 0.0,
                    described_by_text: None,
                    described_by_block_level: i64::MAX,
                    matched_tokens: matched_tokens.clone(),
                });

            if name_score > entry.name_score {
                entry.name_score = name_score;
            }
            if matched_tokens.len() > entry.matched_tokens.len() {
                entry.matched_tokens = matched_tokens;
            }
        }

        if let Some(vector) = query_vector {
            let search_limit = (find_query.limit.unwrap_or(10) as u64).saturating_mul(8);
            let search = SearchPointsBuilder::new(
                &self.vector_store.collection,
                vector.to_vec(),
                search_limit,
            )
            .with_payload(true)
            .filter(qdrant_user_or_shared_access_filter(&find_query.user_id));

            let response = self
                .vector_store
                .client
                .search_points(search)
                .await
                .context("failed to query qdrant semantic candidates")?;

            for point in response.result {
                let Some(root_entity_id) = payload_string(&point.payload, "root_entity_id") else {
                    continue;
                };
                let block_level = payload_i64(&point.payload, "block_level").unwrap_or(99);
                let text = payload_string(&point.payload, "text");
                let level_weight = 1.0 / (1.0 + block_level as f64);
                let weighted_semantic = (point.score as f64) * level_weight;

                let entry = aggregated.entry(root_entity_id.clone()).or_insert_with(|| {
                    AggregatedCandidate {
                        id: root_entity_id,
                        name: String::new(),
                        type_id: String::new(),
                        name_score: 0.0,
                        semantic_score_weighted: weighted_semantic,
                        described_by_text: text.clone(),
                        described_by_block_level: block_level,
                        matched_tokens: Vec::new(),
                    }
                });

                if weighted_semantic > entry.semantic_score_weighted {
                    entry.semantic_score_weighted = weighted_semantic;
                }
                if block_level < entry.described_by_block_level {
                    entry.described_by_text = text;
                    entry.described_by_block_level = block_level;
                }
            }
        }

        let ids: Vec<String> = aggregated.keys().cloned().collect();
        if ids.is_empty() {
            return Ok(Vec::new());
        }

        let mut entity_rows = self
            .graph_store
            .graph
            .execute(query(&format!("MATCH (e:Entity) WHERE e.id IN $ids AND {} RETURN e.id AS id, e.name AS name, e.type_id AS type_id", memgraph_user_or_shared_access_clause("e")))
                .param("ids", ids)
                .param("user_id", find_query.user_id.clone()))
            .await
            .context("failed to hydrate candidate display fields")?;

        while let Some(row) = entity_rows.next().await? {
            let id: String = row.get("id")?;
            if let Some(entry) = aggregated.get_mut(&id) {
                entry.name = row.get("name")?;
                entry.type_id = row.get("type_id")?;
            }
        }

        let mut candidates: Vec<EntityCandidate> = aggregated
            .into_values()
            .filter(|entry| !entry.name.is_empty() && !entry.type_id.is_empty())
            .map(|entry| EntityCandidate {
                id: entry.id,
                name: entry.name,
                described_by_text: entry.described_by_text,
                score: (0.55 * entry.name_score) + (0.45 * entry.semantic_score_weighted),
                type_id: entry.type_id,
                matched_tokens: entry.matched_tokens,
            })
            .collect();

        candidates.sort_by(|a, b| b.score.total_cmp(&a.score));
        if let Some(limit) = find_query.limit {
            candidates.truncate(limit);
        }

        Ok(candidates)
    }
}

#[derive(Debug, Clone)]
struct AggregatedCandidate {
    id: String,
    name: String,
    type_id: String,
    name_score: f64,
    semantic_score_weighted: f64,
    described_by_text: Option<String>,
    described_by_block_level: i64,
    matched_tokens: Vec<String>,
}

fn compute_name_score(
    names: &[String],
    entity_name: &str,
    aliases: Option<&[String]>,
) -> (f64, Vec<String>) {
    let normalized_name = entity_name.to_lowercase();
    let alias_values: Vec<String> = aliases
        .unwrap_or_default()
        .iter()
        .map(|alias| alias.to_lowercase())
        .collect();

    let mut total_score = 0.0;
    let mut matched_tokens = Vec::new();
    for token in names {
        let mut token_score = 0.0;
        if normalized_name == *token {
            token_score = 1.0;
        } else if normalized_name.contains(token) {
            token_score = 0.85;
        }

        for alias in &alias_values {
            let alias_score = if alias == token {
                0.95
            } else if alias.contains(token) {
                0.75
            } else {
                0.0
            };
            if alias_score > token_score {
                token_score = alias_score;
            }
        }

        if token_score > 0.0 {
            matched_tokens.push(token.clone());
            total_score += token_score;
        }
    }

    if names.is_empty() {
        (0.0, matched_tokens)
    } else {
        (total_score / names.len() as f64, matched_tokens)
    }
}

fn payload_string(payload: &HashMap<String, Value>, key: &str) -> Option<String> {
    payload
        .get(key)
        .and_then(|value| value.kind.as_ref())
        .and_then(|kind| match kind {
            Kind::StringValue(value) => Some(value.clone()),
            _ => None,
        })
}

fn payload_i64(payload: &HashMap<String, Value>, key: &str) -> Option<i64> {
    payload
        .get(key)
        .and_then(|value| value.kind.as_ref())
        .and_then(|kind| match kind {
            Kind::IntegerValue(value) => Some(*value),
            Kind::DoubleValue(value) => Some(*value as i64),
            _ => None,
        })
}

fn memgraph_user_or_shared_access_clause(alias: &str) -> String {
    format!("({alias}.user_id = $user_id OR {alias}.visibility = 'SHARED')")
}

fn qdrant_user_or_shared_access_filter(user_id: &str) -> Filter {
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
        Value::from(visibility_as_str(embedded.visibility).to_string()),
    );
    payload.insert("text".to_string(), Value::from(embedded.text.clone()));
    payload.insert(
        "root_entity_id".to_string(),
        Value::from(embedded.root_entity_id.clone()),
    );
    payload.insert("block_level".to_string(), Value::from(embedded.block_level));
    PointStruct::new(embedded.block.id.clone(), embedded.vector.clone(), payload)
}

fn sanitize_labels(labels: &[String]) -> Result<Vec<String>> {
    let cleaned: Vec<String> = labels
        .iter()
        .map(|label| label.trim().to_string())
        .filter(|label| !label.is_empty())
        .collect();
    if cleaned.is_empty() {
        anyhow::bail!("resolved labels cannot be empty");
    }
    for label in &cleaned {
        if !label
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '_')
        {
            anyhow::bail!("invalid label '{}'", label);
        }
    }
    Ok(cleaned)
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

pub struct OpenAiCompatibleEmbedder {
    client: reqwest::Client,
    base_url: String,
    model_alias: String,
}

impl OpenAiCompatibleEmbedder {
    pub fn new(base_url: String, model_alias: String) -> Self {
        Self {
            client: reqwest::Client::new(),
            base_url,
            model_alias,
        }
    }
}

#[async_trait]
impl Embedder for OpenAiCompatibleEmbedder {
    async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(vec![]);
        }

        let url = format!("{}/embeddings", self.base_url.trim_end_matches('/'));
        let response: EmbeddingResponse = self
            .client
            .post(url)
            .header(CONTENT_TYPE, "application/json")
            .json(&EmbeddingRequest {
                input: texts,
                model: &self.model_alias,
            })
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;

        Ok(response.data.into_iter().map(|d| d.embedding).collect())
    }
}

pub struct MockEmbedder;

#[async_trait]
impl Embedder for MockEmbedder {
    async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        Ok(texts
            .iter()
            .map(|text| {
                let mut v = vec![0.0_f32; 3072];
                for (idx, byte) in text.as_bytes().iter().enumerate() {
                    v[idx % 3072] += (*byte as f32) / 255.0;
                }
                v
            })
            .collect())
    }
}

fn normalize_qdrant_grpc_url(url: &str) -> String {
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
    use super::{
        allowed_node_visibilities, compute_name_score, memgraph_user_or_shared_access_clause,
        normalize_qdrant_grpc_url, payload_i64, payload_string,
        qdrant_user_or_shared_access_filter, validate_edge_type, MockEmbedder,
    };
    use crate::domain::Visibility;
    use crate::ports::Embedder;

    #[test]
    fn normalizes_qdrant_rest_port_to_grpc_port() {
        assert_eq!(
            normalize_qdrant_grpc_url("http://localhost:6333"),
            "http://localhost:6334"
        );
        assert_eq!(
            normalize_qdrant_grpc_url("http://localhost:16333"),
            "http://localhost:16334"
        );
        assert_eq!(
            normalize_qdrant_grpc_url("localhost:6333"),
            "http://localhost:6334"
        );
    }

    #[test]
    fn allows_private_edges_to_connect_shared_or_private_nodes() {
        assert_eq!(
            allowed_node_visibilities(Visibility::Private),
            vec!["PRIVATE".to_string(), "SHARED".to_string()]
        );
        assert_eq!(
            allowed_node_visibilities(Visibility::Shared),
            vec!["SHARED".to_string()]
        );
    }

    #[tokio::test]
    async fn mock_embedder_matches_qdrant_dimension() {
        let embedder = MockEmbedder;
        let vectors = embedder
            .embed_texts(&["hello".to_string()])
            .await
            .expect("mock embedding should succeed");
        assert_eq!(vectors.len(), 1);
        assert_eq!(vectors[0].len(), 3072);
    }

    #[test]
    fn compute_name_score_prefers_exact_name_and_alias_matches() {
        let names = vec!["ada".to_string(), "lovelace".to_string()];
        let aliases = vec!["A. Lovelace".to_string(), "Augusta Ada".to_string()];

        let (score, matched_tokens) = compute_name_score(&names, "Ada Lovelace", Some(&aliases));

        assert!(score > 0.8);
        assert_eq!(matched_tokens, names);
    }

    #[test]
    fn payload_helpers_extract_expected_types() {
        use qdrant_client::qdrant::value::Kind;
        use qdrant_client::qdrant::Value;
        use std::collections::HashMap;

        let mut payload = HashMap::new();
        payload.insert(
            "text".to_string(),
            Value {
                kind: Some(Kind::StringValue("root block".to_string())),
            },
        );
        payload.insert(
            "block_level".to_string(),
            Value {
                kind: Some(Kind::IntegerValue(0)),
            },
        );

        assert_eq!(
            payload_string(&payload, "text").as_deref(),
            Some("root block")
        );
        assert_eq!(payload_i64(&payload, "block_level"), Some(0));
    }

    #[test]
    fn builds_memgraph_user_or_shared_access_clause() {
        assert_eq!(
            memgraph_user_or_shared_access_clause("e"),
            "(e.user_id = $user_id OR e.visibility = 'SHARED')"
        );
    }

    #[test]
    fn builds_qdrant_user_or_shared_access_filter() {
        let filter = qdrant_user_or_shared_access_filter("alice");
        assert!(filter.must.is_empty());
        assert_eq!(filter.should.len(), 2);
    }

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
