use std::collections::HashMap;

use anyhow::{Context, Result};
use async_trait::async_trait;
use neo4rs::query;
use tracing::warn;

use crate::infrastructure::qdrant::{payload_i64, payload_string, QdrantVectorStore};

use crate::{
    domain::{
        EmbeddedBlock, EntityCandidate, ExistingBlockContext, ExtractionUniverse,
        FindEntityCandidatesQuery, GetEntityContextQuery, GetEntityContextResult, GraphDelta,
        ListEntitiesByTypeQuery, ListEntitiesByTypeResult, NodeRelationshipCounts,
        UserInitGraphNodeIds, Visibility,
    },
    ports::GraphRepository,
};

use crate::infrastructure::memgraph::store::{
    build_list_entities_by_type_query, memgraph_user_or_shared_access_clause,
    to_typed_entity_list_item, type_id_to_memgraph_label, Neo4jGraphStore,
};

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

    async fn mark_user_graph_initialized(
        &self,
        user_id: &str,
        node_ids: &UserInitGraphNodeIds,
    ) -> Result<()> {
        self.graph_store
            .mark_user_graph_initialized(user_id, node_ids)
            .await
    }

    async fn get_user_init_graph_node_ids(
        &self,
        user_id: &str,
    ) -> Result<Option<UserInitGraphNodeIds>> {
        self.graph_store.get_user_init_graph_node_ids(user_id).await
    }

    async fn update_person_name(&self, person_entity_id: &str, user_name: &str) -> Result<()> {
        self.graph_store
            .update_person_name(person_entity_id, user_name)
            .await
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

    async fn get_extraction_universes(&self, user_id: &str) -> Result<Vec<ExtractionUniverse>> {
        let mut rows = self
            .graph_store
            .graph
            .execute(query(
                "MATCH (u:Universe)                  WHERE u.user_id = $user_id OR u.visibility = 'SHARED'                  OPTIONAL MATCH (u)-[:DESCRIBED_BY]->(b:Block)                  RETURN u.id AS id, u.name AS name, b.text AS described_by_text                  ORDER BY u.id"
            )
            .param("user_id", user_id.to_string()))
            .await
            .context("failed to fetch extraction universes from memgraph")?;

        let mut universes = Vec::new();
        while let Some(row) = rows.next().await? {
            let id: String = row.get("id")?;
            let name: String = row.get("name")?;
            let described_by_text: Option<String> = row.get("described_by_text")?;
            universes.push(ExtractionUniverse {
                id,
                name,
                described_by_text,
            });
        }

        Ok(universes)
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
            let points = self
                .vector_store
                .search(vector, search_limit, &find_query.user_id)
                .await
                .context("failed to query qdrant semantic candidates")?;

            for point in points {
                let Some(root_entity_id) = payload_string(&point.payload, "root_entity_id") else {
                    continue;
                };
                let block_level = payload_i64(&point.payload, "block_level").unwrap_or(99);
                let text = payload_string(&point.payload, "text");
                let weighted_semantic =
                    semantic_score_with_block_level(point.score as f64, block_level);

                upsert_semantic_candidate(
                    &mut aggregated,
                    root_entity_id,
                    weighted_semantic,
                    block_level,
                    text,
                );
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

    async fn list_entities_by_type(
        &self,
        query_input: &ListEntitiesByTypeQuery,
    ) -> Result<ListEntitiesByTypeResult> {
        let page_size = query_input.page_size.unwrap_or(20);
        let offset = query_input.offset.unwrap_or_default();
        let type_label = type_id_to_memgraph_label(&query_input.type_id);

        let cypher = build_list_entities_by_type_query();
        let limit = i64::from(page_size) + 1;
        let offset_i64 = offset as i64;

        let mut rows = self
            .graph_store
            .graph
            .execute(
                query(&cypher)
                    .param("user_id", query_input.user_id.clone())
                    .param("type_label", type_label)
                    .param("limit", limit)
                    .param("offset", offset_i64),
            )
            .await
            .map_err(|err| {
                warn!(
                    error = ?err,
                    user_id = %query_input.user_id,
                    type_id = %query_input.type_id,
                    page_size,
                    limit,
                    offset = offset_i64,
                    "failed to execute list_entities_by_type query"
                );
                err
            })
            .context("failed to list entities by type from memgraph")?;

        let mut entities = Vec::new();
        while let Some(row) = rows.next().await? {
            entities.push(to_typed_entity_list_item(
                row.get("id").context("missing list_entities.id")?,
                row.get("name").ok(),
                row.get("updated_at").ok(),
                row.get("description").ok(),
            ));
        }

        let has_next_page = entities.len() > page_size as usize;
        if has_next_page {
            entities.truncate(page_size as usize);
        }

        Ok(ListEntitiesByTypeResult {
            entities,
            offset,
            next_page_token: has_next_page.then(|| (offset + u64::from(page_size)).to_string()),
        })
    }

    async fn get_entity_context(
        &self,
        query: &GetEntityContextQuery,
    ) -> Result<GetEntityContextResult> {
        self.graph_store.get_entity_context(query).await
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

fn semantic_score_with_block_level(raw_score: f64, block_level: i64) -> f64 {
    raw_score * (1.0 / (1.0 + block_level as f64))
}

fn upsert_semantic_candidate(
    aggregated: &mut HashMap<String, AggregatedCandidate>,
    root_entity_id: String,
    weighted_semantic: f64,
    block_level: i64,
    text: Option<String>,
) {
    let entry = aggregated
        .entry(root_entity_id.clone())
        .or_insert_with(|| AggregatedCandidate {
            id: root_entity_id,
            name: String::new(),
            type_id: String::new(),
            name_score: 0.0,
            semantic_score_weighted: weighted_semantic,
            described_by_text: text.clone(),
            described_by_block_level: block_level,
            matched_tokens: Vec::new(),
        });

    if weighted_semantic > entry.semantic_score_weighted {
        entry.semantic_score_weighted = weighted_semantic;
    }
    if block_level < entry.described_by_block_level {
        entry.described_by_text = text;
        entry.described_by_block_level = block_level;
    }
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
