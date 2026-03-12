use std::collections::HashMap;

use anyhow::{Context, Result};
use neo4rs::{query, BoltMap, BoltType, ConfigBuilder, Graph, Txn};

use super::conversion::{
    bolt_map_remove_aliases, bolt_map_to_property_values, parse_alias_payload,
};

use crate::domain::{
    EntityContextBlockItem, EntityContextEntitySnapshot, EntityContextNeighborItem,
    EntityContextOtherEntity, ExistingBlockContext, GetEntityContextQuery, GetEntityContextResult,
    GraphDelta, NeighborDirection, NodeRelationshipCounts, PropertyScalar, PropertyValue,
    TypedEntityListItem, UserInitGraphNodeIds, Visibility,
};

const ENTITY_BLOCK_VOLUME_WEIGHT: f64 = 0.30;
const ENTITY_OWNERSHIP_WEIGHT: f64 = 0.15;
const ENTITY_NEIGHBOR_COUNT_WEIGHT: f64 = 0.10;
const ENTITY_LIST_DEFAULT_UPDATED_AT_EPOCH: &str = "1970-01-01T00:00:00Z";

pub struct Neo4jGraphStore {
    pub(crate) graph: Graph,
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
        let store = Self { graph };
        store.ensure_internal_timestamps_triggers().await?;
        Ok(store)
    }

    async fn ensure_internal_timestamps_triggers(&self) -> Result<()> {
        // `created_at` and `updated_at` are knowledge-interface-internal metadata
        // and are maintained only by Memgraph triggers.
        let mut existing_trigger_names = std::collections::HashSet::new();
        if let Ok(mut rows) = self.graph.execute(query("SHOW TRIGGERS")).await {
            while let Some(row) = rows.next().await? {
                for key in trigger_name_column_candidates() {
                    if let Ok(value) = row.get::<String>(key) {
                        existing_trigger_names.insert(value);
                    }
                }
            }
        }

        for (name, cypher) in internal_timestamp_trigger_specs() {
            if existing_trigger_names.contains(name) {
                continue;
            }
            self.graph
                .run(query(cypher))
                .await
                .context("failed to ensure internal timestamp triggers")?;
        }

        Ok(())
    }

    pub(crate) async fn apply_delta_in_tx(&self, txn: &mut Txn, delta: &GraphDelta) -> Result<()> {
        let universe_aliases: Vec<String> = Vec::new();
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
            let entity_properties = property_values_to_bolt_map(&entity.properties);
            let cypher = format!(
                "MERGE (e:{} {{id: $id}}) SET e += $properties, e.type_id = $type_id, e.name = $name, e.aliases = $aliases, e.user_id = $user_id, e.visibility = $visibility WITH e MATCH (u:Universe {{id: $universe_id}}) MERGE (e)-[:IS_PART_OF]->(u)",
                labels.join(":"),
            );
            txn.run(
                query(&cypher)
                    .param("id", entity.id.clone())
                    .param("properties", entity_properties)
                    .param("type_id", entity.type_id.clone())
                    .param(
                        "name",
                        prop_as_string(&entity.properties, "name").unwrap_or_default(),
                    )
                    .param("aliases", prop_as_aliases(&entity.properties))
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
            let block_properties = property_values_to_bolt_map(&block.properties);
            let cypher = format!(
                "MERGE (b:{} {{id: $id}}) SET b += $properties, b.type_id = $type_id, b.text = $text, b.user_id = $user_id, b.visibility = $visibility",
                labels.join(":"),
            );
            txn.run(
                query(&cypher)
                    .param("id", block.id.clone())
                    .param("properties", block_properties)
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
            let edge_properties = property_values_to_bolt_map(&edge.properties);
            let allowed_node_visibilities = allowed_node_visibilities(edge.visibility);
            let cypher = format!("MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) WHERE a.visibility IN $allowed_node_visibilities AND b.visibility IN $allowed_node_visibilities MERGE (a)-[r:{}]->(b) SET r += $properties, r.confidence = $confidence, r.status = $status, r.provenance_hint = $provenance_hint, r.user_id = $user_id, r.visibility = $visibility RETURN COUNT(r) AS upserted_count", edge.edge_type);
            let mut result = txn
                .execute(
                    query(&cypher)
                        .param("from_id", edge.from_id.clone())
                        .param("to_id", edge.to_id.clone())
                        .param("user_id", edge.user_id.clone())
                        .param("visibility", visibility_as_str(edge.visibility))
                        .param("properties", edge_properties)
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
                            "provenance_hint",
                            prop_as_string(&edge.properties, "provenance_hint").unwrap_or_default(),
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

    pub(crate) async fn common_root_graph_exists(&self) -> Result<bool> {
        let mut result = self
            .graph
            .execute(query("MATCH (e:Entity {id: '8c75cc89-6204-4fed-aec1-34d032ff95ee', user_id: 'exobrain', visibility: 'SHARED'})-[:IS_PART_OF]->(:Universe {id: '9d7f0fa5-78c1-4805-9efb-3f8f16090d7f'}) MATCH (e)-[:DESCRIBED_BY]->(:Block {id: 'ea5ca80f-346b-4f66-bff2-d307ce5d7da9', user_id: 'exobrain', visibility: 'SHARED'}) RETURN 1 AS present LIMIT 1"))
            .await
            .context("failed to query common root graph")?;

        Ok(result.next().await?.is_some())
    }

    pub(crate) async fn user_graph_needs_initialization(&self, user_id: &str) -> Result<bool> {
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

        Ok(result.next().await?.is_none())
    }

    pub(crate) async fn mark_user_graph_initialized(
        &self,
        user_id: &str,
        node_ids: &UserInitGraphNodeIds,
    ) -> Result<()> {
        self.graph
            .run(
                query(
                    "MERGE (m:GraphInitialization {user_id: $user_id}) SET m.visibility = 'SHARED', m.person_entity_id = $person_entity_id, m.assistant_entity_id = $assistant_entity_id",
                )
                .param("user_id", user_id.to_string())
                .param("person_entity_id", node_ids.person_entity_id.clone())
                .param("assistant_entity_id", node_ids.assistant_entity_id.clone()),
            )
            .await
            .context("failed to mark user graph initialized")?;

        Ok(())
    }

    pub(crate) async fn get_user_init_graph_node_ids(
        &self,
        user_id: &str,
    ) -> Result<Option<UserInitGraphNodeIds>> {
        let mut result = self
            .graph
            .execute(
                query(
                    "MATCH (m:GraphInitialization {user_id: $user_id, visibility: 'SHARED'}) RETURN m.person_entity_id AS person_entity_id, m.assistant_entity_id AS assistant_entity_id LIMIT 1",
                )
                .param("user_id", user_id.to_string()),
            )
            .await
            .context("failed to query user graph node ids")?;

        let Some(row) = result.next().await? else {
            return Ok(None);
        };

        let person_entity_id = row.get::<String>("person_entity_id").unwrap_or_default();
        let assistant_entity_id = row.get::<String>("assistant_entity_id").unwrap_or_default();
        if person_entity_id.is_empty() || assistant_entity_id.is_empty() {
            return Ok(None);
        }

        Ok(Some(UserInitGraphNodeIds {
            person_entity_id,
            assistant_entity_id,
        }))
    }

    pub(crate) async fn update_person_name(
        &self,
        person_entity_id: &str,
        user_name: &str,
    ) -> Result<()> {
        self.graph
            .run(
                query("MATCH (p:Entity {id: $person_entity_id}) SET p.name = $user_name")
                    .param("person_entity_id", person_entity_id.to_string())
                    .param("user_name", user_name.to_string()),
            )
            .await
            .context("failed to update person name")?;

        Ok(())
    }

    pub(crate) async fn get_existing_block_context(
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
                    "MATCH (e:Entity)-[:DESCRIBED_BY]->(root:Block)                      MATCH p=(root)-[:SUMMARIZES*0..]->(b:Block {id: $block_id})                      WHERE e.user_id = $user_id AND root.user_id = $user_id AND b.user_id = $user_id                      AND e.visibility IN $allowed_node_visibilities                      AND root.visibility IN $allowed_node_visibilities                      AND b.visibility IN $allowed_node_visibilities                      RETURN e.id AS root_entity_id, length(p) AS block_level                      ORDER BY block_level ASC LIMIT 1",
                )
                .param("block_id", block_id.to_string())
                .param("user_id", user_id.to_string())
                .param("allowed_node_visibilities", allowed_node_visibilities)
            )
            .await
            .context("failed to query existing block context")?;

        let Some(row) = result.next().await? else {
            return Ok(None);
        };

        Ok(Some(ExistingBlockContext {
            root_entity_id: row.get("root_entity_id")?,
            block_level: row.get("block_level")?,
        }))
    }

    pub(crate) async fn get_node_relationship_counts(
        &self,
        node_id: &str,
    ) -> Result<NodeRelationshipCounts> {
        let mut result = self
            .graph
            .execute(query(
                "MATCH (n {id: $node_id}) OPTIONAL MATCH (n)-[out]->() WITH n, COUNT(out) AS outgoing OPTIONAL MATCH ()-[incoming]->(n) WITH n, outgoing, COUNT(incoming) AS incoming OPTIONAL MATCH (n)-[is_part_of:IS_PART_OF]->(:Universe) WITH n, outgoing, incoming, COUNT(is_part_of) AS entity_is_part_of OPTIONAL MATCH (n)-[described_by_entity:DESCRIBED_BY]->(:Block) WHERE n:Entity WITH n, outgoing, incoming, entity_is_part_of, COUNT(described_by_entity) AS entity_described_by_edges OPTIONAL MATCH (n)-[described_by_universe:DESCRIBED_BY]->(:Block) WHERE n:Universe WITH n, outgoing, incoming, entity_is_part_of, entity_described_by_edges, COUNT(described_by_universe) AS universe_described_by_edges OPTIONAL MATCH ()-[parent:DESCRIBED_BY|SUMMARIZES]->(n) RETURN incoming + outgoing AS total, entity_is_part_of, COUNT(parent) AS block_parent_edges, entity_described_by_edges, universe_described_by_edges",
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
            entity_described_by_edges: row.get::<i64>("entity_described_by_edges")? as usize,
            universe_described_by_edges: row.get::<i64>("universe_described_by_edges")? as usize,
        })
    }

    pub(crate) async fn get_entity_context(
        &self,
        query_input: &GetEntityContextQuery,
    ) -> Result<GetEntityContextResult> {
        let entity_query = build_get_entity_context_entity_query();
        let mut entity_rows = self
            .graph
            .execute(
                query(&entity_query)
                    .param("entity_id", query_input.entity_id.clone())
                    .param("user_id", query_input.user_id.clone()),
            )
            .await
            .context("failed to query target entity context")?;

        let Some(entity_row) = entity_rows.next().await? else {
            return Err(entity_not_found_or_inaccessible_error());
        };

        let mut entity_properties: BoltMap = entity_row
            .get("entity_props")
            .context("missing entity.entity_props")?;

        let entity_name = bolt_map_remove_string(&mut entity_properties, "name");
        let entity_aliases = bolt_map_remove_aliases(&mut entity_properties, "aliases");
        let entity_created_at = entity_row.get("created_at").ok();
        let entity_updated_at = entity_row.get("updated_at").ok();

        let entity = EntityContextEntitySnapshot {
            id: entity_row.get("id").context("missing entity.id")?,
            type_id: entity_row
                .get("type_id")
                .context("missing entity.type_id")?,
            user_id: entity_row
                .get("user_id")
                .context("missing entity.user_id")?,
            visibility: visibility_from_str(
                &entity_row
                    .get::<String>("visibility")
                    .context("missing entity.visibility")?,
            )?,
            name: entity_name,
            aliases: entity_aliases,
            created_at: entity_created_at,
            updated_at: entity_updated_at,
            properties: bolt_map_to_property_values(entity_properties),
        };

        let block_query = build_get_entity_context_blocks_query();
        let mut block_rows = self
            .graph
            .execute(
                query(&block_query)
                    .param("entity_id", query_input.entity_id.clone())
                    .param("user_id", query_input.user_id.clone())
                    .param("max_block_level", query_input.max_block_level as i64),
            )
            .await
            .context("failed to query entity context blocks")?;

        let mut blocks = Vec::new();
        while let Some(row) = block_rows.next().await? {
            let block_level: i64 = row
                .get("block_level")
                .context("missing block.block_level")?;
            let mut block_props: BoltMap = row
                .get("block_props")
                .context("missing block.block_props")?;
            let block_text = bolt_map_remove_string(&mut block_props, "text");
            let block_created_at = row.get("created_at").ok();
            let block_updated_at = row.get("updated_at").ok();

            blocks.push(EntityContextBlockItem {
                id: row.get("block_id").context("missing block.id")?,
                type_id: row.get("type_id").context("missing block.type_id")?,
                block_level: parse_block_level(block_level)?,
                text: block_text,
                created_at: block_created_at,
                updated_at: block_updated_at,
                properties: bolt_map_to_property_values(block_props),
                parent_block_id: row.get("parent_block_id").ok(),
                neighbors: Vec::new(),
            });
        }

        let block_neighbor_query = build_get_entity_context_block_neighbors_query();

        let mut block_neighbor_rows = self
            .graph
            .execute(
                query(&block_neighbor_query)
                    .param("entity_id", query_input.entity_id.clone())
                    .param("user_id", query_input.user_id.clone())
                    .param("max_block_level", query_input.max_block_level as i64),
            )
            .await
            .context("failed to query entity context block neighbors")?;

        let mut block_neighbors_by_id: HashMap<String, Vec<EntityContextNeighborItem>> =
            HashMap::new();
        while let Some(row) = block_neighbor_rows.next().await? {
            let direction_raw: String = row
                .get("direction")
                .context("missing block_neighbor.direction")?;
            let direction = parse_neighbor_direction(&direction_raw)?;
            let edge_props: BoltMap = row
                .get("edge_props")
                .context("missing block_neighbor.edge_props")?;
            let other_entity = EntityContextOtherEntity {
                id: row
                    .get("other_entity_id")
                    .context("missing block_neighbor.other_entity_id")?,
                description: row.get("other_entity_description").ok(),
                name: row.get("other_entity_name").ok(),
                type_id: row
                    .get("other_entity_type_id")
                    .context("missing block_neighbor.other_entity_type_id")?,
                aliases: parse_alias_payload(
                    &row.get::<String>("other_entity_aliases")
                        .unwrap_or_default(),
                ),
            };

            let item = EntityContextNeighborItem {
                direction,
                edge_type: row
                    .get("edge_type")
                    .context("missing block_neighbor.edge_type")?,
                properties: bolt_map_to_property_values(edge_props),
                other_entity,
            };

            let block_id: String = row
                .get("block_id")
                .context("missing block_neighbor.block_id")?;
            block_neighbors_by_id
                .entry(block_id)
                .or_default()
                .push(item);
        }

        for block in &mut blocks {
            if let Some(neighbors) = block_neighbors_by_id.remove(&block.id) {
                block.neighbors = neighbors;
            }
        }

        let neighbor_query = build_get_entity_context_neighbors_query();

        let mut neighbor_rows = self
            .graph
            .execute(
                query(&neighbor_query)
                    .param("entity_id", query_input.entity_id.clone())
                    .param("user_id", query_input.user_id.clone()),
            )
            .await
            .context("failed to query entity context neighbors")?;

        let mut neighbors = Vec::new();
        while let Some(row) = neighbor_rows.next().await? {
            let direction_raw: String =
                row.get("direction").context("missing neighbor.direction")?;
            let direction = parse_neighbor_direction(&direction_raw)?;
            let edge_props: BoltMap = row
                .get("edge_props")
                .context("missing neighbor.edge_props")?;

            neighbors.push(EntityContextNeighborItem {
                direction,
                edge_type: row.get("edge_type").context("missing neighbor.edge_type")?,
                properties: bolt_map_to_property_values(edge_props),
                other_entity: EntityContextOtherEntity {
                    id: row
                        .get("other_entity_id")
                        .context("missing neighbor.other_entity_id")?,
                    description: row.get("other_entity_description").ok(),
                    name: row.get("other_entity_name").ok(),
                    type_id: row
                        .get("other_entity_type_id")
                        .context("missing neighbor.other_entity_type_id")?,
                    aliases: parse_alias_payload(
                        &row.get::<String>("other_entity_aliases")
                            .unwrap_or_default(),
                    ),
                },
            });
        }

        Ok(GetEntityContextResult {
            entity,
            blocks,
            neighbors,
        })
    }
}

fn entity_not_found_or_inaccessible_error() -> anyhow::Error {
    anyhow::anyhow!("entity not found or inaccessible")
}

fn bolt_map_remove_string(map: &mut BoltMap, key: &str) -> Option<String> {
    let value = map.value.remove(key)?;
    match value {
        BoltType::String(v) => Some(v.value),
        BoltType::Null(_) => None,
        other => Some(format!("{other:?}")),
    }
}

fn allowed_node_visibilities(edge_visibility: Visibility) -> Vec<String> {
    match edge_visibility {
        Visibility::Private => vec!["PRIVATE".to_string(), "SHARED".to_string()],
        Visibility::Shared => vec!["SHARED".to_string()],
    }
}

fn build_get_entity_context_entity_query() -> String {
    format!(
        "MATCH (e:Entity {{id: $entity_id}}) WHERE {} RETURN e.id AS id, e.type_id AS type_id, e.user_id AS user_id, e.visibility AS visibility, properties(e) AS entity_props, toString(e.created_at) AS created_at, toString(e.updated_at) AS updated_at",
        memgraph_user_or_shared_access_clause("e")
    )
}

fn build_get_entity_context_blocks_query() -> String {
    format!(
        "MATCH (e:Entity {{id: $entity_id}})-[:DESCRIBED_BY]->(root:Block)
         WHERE {entity_access} AND {root_access}
         MATCH p=(root)-[:SUMMARIZES*0..]->(b:Block)
         WHERE {block_access} AND length(p) <= $max_block_level
         OPTIONAL MATCH (parent:Block)-[:SUMMARIZES]->(b)
         WHERE {parent_access}
         RETURN b.id AS block_id,
                b.type_id AS type_id,
                length(p) AS block_level,
                parent.id AS parent_block_id,
                properties(b) AS block_props,
                toString(b.created_at) AS created_at,
                toString(b.updated_at) AS updated_at
         ORDER BY block_level ASC, block_id ASC",
        entity_access = memgraph_user_or_shared_access_clause("e"),
        root_access = memgraph_user_or_shared_access_clause("root"),
        block_access = memgraph_user_or_shared_access_clause("b"),
        parent_access = memgraph_user_or_shared_access_clause("parent"),
    )
}

fn build_get_entity_context_block_neighbors_query() -> String {
    format!(
        "MATCH (e:Entity {{id: $entity_id}})-[:DESCRIBED_BY]->(root:Block)
         WHERE {entity_access} AND {root_access}
         MATCH p=(root)-[:SUMMARIZES*0..]->(b:Block)
         WHERE {block_access} AND length(p) <= $max_block_level
         MATCH (b)-[r]->(other:Entity)
         WHERE {other_access} AND {edge_access} AND type(r) <> 'DESCRIBED_BY' AND type(r) <> 'SUMMARIZES'
         OPTIONAL MATCH (other)-[:DESCRIBED_BY]->(described_by:Block)
         WHERE {described_access}
         RETURN b.id AS block_id,
                'OUTGOING' AS direction,
                type(r) AS edge_type,
                properties(r) AS edge_props,
                other.id AS other_entity_id,
                described_by.text AS other_entity_description,
                other.name AS other_entity_name,
                other.type_id AS other_entity_type_id,
                toString(other.aliases) AS other_entity_aliases
         UNION ALL
         MATCH (e:Entity {{id: $entity_id}})-[:DESCRIBED_BY]->(root:Block)
         WHERE {entity_access} AND {root_access}
         MATCH p=(root)-[:SUMMARIZES*0..]->(b:Block)
         WHERE {block_access} AND length(p) <= $max_block_level
         MATCH (b)<-[r]-(other:Entity)
         WHERE {other_access} AND {edge_access} AND type(r) <> 'DESCRIBED_BY' AND type(r) <> 'SUMMARIZES'
         OPTIONAL MATCH (other)-[:DESCRIBED_BY]->(described_by:Block)
         WHERE {described_access}
         RETURN b.id AS block_id,
                'INCOMING' AS direction,
                type(r) AS edge_type,
                properties(r) AS edge_props,
                other.id AS other_entity_id,
                described_by.text AS other_entity_description,
                other.name AS other_entity_name,
                other.type_id AS other_entity_type_id,
                toString(other.aliases) AS other_entity_aliases
         ORDER BY block_id ASC, direction ASC, edge_type ASC, other_entity_id ASC",
        entity_access = memgraph_user_or_shared_access_clause("e"),
        root_access = memgraph_user_or_shared_access_clause("root"),
        block_access = memgraph_user_or_shared_access_clause("b"),
        other_access = memgraph_user_or_shared_access_clause("other"),
        edge_access = memgraph_user_or_shared_access_clause("r"),
        described_access = memgraph_user_or_shared_access_clause("described_by"),
    )
}

fn build_get_entity_context_neighbors_query() -> String {
    format!(
        "MATCH (e:Entity {{id: $entity_id}})
         WHERE {entity_access}
         MATCH (e)-[r]->(other:Entity)
         WHERE {other_access} AND {edge_access} AND type(r) <> 'DESCRIBED_BY' AND type(r) <> 'SUMMARIZES'
         OPTIONAL MATCH (other)-[:DESCRIBED_BY]->(described_by:Block)
         WHERE {described_access}
         RETURN 'OUTGOING' AS direction,
                type(r) AS edge_type,
                properties(r) AS edge_props,
                other.id AS other_entity_id,
                described_by.text AS other_entity_description,
                other.name AS other_entity_name,
                other.type_id AS other_entity_type_id,
                toString(other.aliases) AS other_entity_aliases
         UNION ALL
         MATCH (e:Entity {{id: $entity_id}})
         WHERE {entity_access}
         MATCH (e)<-[r]-(other:Entity)
         WHERE {other_access} AND {edge_access} AND type(r) <> 'DESCRIBED_BY' AND type(r) <> 'SUMMARIZES'
         OPTIONAL MATCH (other)-[:DESCRIBED_BY]->(described_by:Block)
         WHERE {described_access}
         RETURN 'INCOMING' AS direction,
                type(r) AS edge_type,
                properties(r) AS edge_props,
                other.id AS other_entity_id,
                described_by.text AS other_entity_description,
                other.name AS other_entity_name,
                other.type_id AS other_entity_type_id,
                toString(other.aliases) AS other_entity_aliases
         ORDER BY direction ASC, edge_type ASC, other_entity_id ASC",
        entity_access = memgraph_user_or_shared_access_clause("e"),
        other_access = memgraph_user_or_shared_access_clause("other"),
        edge_access = memgraph_user_or_shared_access_clause("r"),
        described_access = memgraph_user_or_shared_access_clause("described_by"),
    )
}

pub(crate) fn build_list_entities_by_type_query() -> String {
    format!(
        "MATCH (e:Entity)
         WHERE {entity_access} AND $type_label IN labels(e)
         OPTIONAL MATCH (e)-[:DESCRIBED_BY]->(root:Block)
         WHERE {root_access}
         WITH e, root
         ORDER BY root.updated_at DESC, root.id ASC
         WITH e,
              head(collect(root.text)) AS description,
              coalesce(e.updated_at, datetime('{default_updated_at_epoch}')) AS updated_at_value,
              toString(e.updated_at) AS updated_at
         OPTIONAL MATCH (e)-[:DESCRIBED_BY]->(described_root:Block)
         WHERE {described_root_access}
         OPTIONAL MATCH (described_root)-[:SUMMARIZES*0..]->(b:Block)
         WHERE {block_access}
         WITH e, description, updated_at_value, updated_at, COUNT(DISTINCT b) AS block_volume
         OPTIONAL MATCH (e)-[rel]-()
         WHERE type(rel) <> 'DESCRIBED_BY' AND type(rel) <> 'SUMMARIZES'
           AND {relationship_access}
         WITH e,
              description,
              updated_at,
              block_volume,
              COUNT(DISTINCT rel) AS neighbor_count,
              CASE WHEN e.user_id = $user_id THEN 1.0 ELSE 0.0 END AS ownership_boost
         WITH e,
              description,
              updated_at,
              ({block_volume_weight} * log10(toFloat(1 + block_volume))) +
              ({ownership_weight} * ownership_boost) +
              ({neighbor_count_weight} * log10(toFloat(1 + neighbor_count))) AS relevance
         RETURN e.id AS id,
                e.name AS name,
                updated_at,
                description,
                relevance
         ORDER BY relevance DESC, updated_at DESC, id ASC
         SKIP $offset
         LIMIT $limit",
        entity_access = memgraph_user_or_shared_access_clause("e"),
        root_access = memgraph_user_or_shared_access_clause("root"),
        described_root_access = memgraph_user_or_shared_access_clause("described_root"),
        block_access = memgraph_user_or_shared_access_clause("b"),
        relationship_access = memgraph_user_or_shared_access_clause("rel"),
        default_updated_at_epoch = ENTITY_LIST_DEFAULT_UPDATED_AT_EPOCH,
        block_volume_weight = ENTITY_BLOCK_VOLUME_WEIGHT,
        ownership_weight = ENTITY_OWNERSHIP_WEIGHT,
        neighbor_count_weight = ENTITY_NEIGHBOR_COUNT_WEIGHT,
    )
}

fn parse_neighbor_direction(direction: &str) -> Result<NeighborDirection> {
    match direction {
        "OUTGOING" => Ok(NeighborDirection::Outgoing),
        "INCOMING" => Ok(NeighborDirection::Incoming),
        _ => anyhow::bail!("invalid neighbor direction: {direction}"),
    }
}

fn parse_block_level(block_level: i64) -> Result<u32> {
    u32::try_from(block_level).map_err(|_| anyhow::anyhow!("invalid block level: {block_level}"))
}

pub(crate) fn to_typed_entity_list_item(
    id: String,
    name: Option<String>,
    updated_at: Option<String>,
    description: Option<String>,
) -> TypedEntityListItem {
    TypedEntityListItem {
        id,
        name,
        updated_at,
        description,
    }
}

pub(crate) fn memgraph_user_or_shared_access_clause(alias: &str) -> String {
    format!("({alias}.user_id = $user_id OR {alias}.visibility = 'SHARED')")
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

pub(crate) fn type_id_to_memgraph_label(type_id: &str) -> String {
    let label = type_id.trim().trim_start_matches("node.");
    let mut chars = label.chars();
    match chars.next() {
        Some(first) => format!(
            "{}{}",
            first.to_ascii_uppercase(),
            chars.collect::<String>()
        ),
        None => String::new(),
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

fn prop_as_aliases(props: &[PropertyValue]) -> Vec<String> {
    let Some(raw) = prop_as_string(props, "aliases") else {
        return Vec::new();
    };

    parse_alias_payload(&raw)
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

fn property_values_to_bolt_map(props: &[PropertyValue]) -> HashMap<String, BoltType> {
    props
        .iter()
        .map(|prop| (prop.key.clone(), property_scalar_to_bolt_type(&prop.value)))
        .collect()
}

fn property_scalar_to_bolt_type(value: &PropertyScalar) -> BoltType {
    match value {
        PropertyScalar::String(v) | PropertyScalar::Datetime(v) | PropertyScalar::Json(v) => {
            BoltType::from(v.clone())
        }
        PropertyScalar::Float(v) => BoltType::from(*v),
        PropertyScalar::Int(v) => BoltType::from(*v),
        PropertyScalar::Bool(v) => BoltType::from(*v),
    }
}

fn internal_timestamp_trigger_specs() -> [(&'static str, &'static str); 4] {
    [
        (
            "set_node_timestamps_on_create",
            "CREATE TRIGGER set_node_timestamps_on_create ON () CREATE BEFORE COMMIT EXECUTE UNWIND createdVertices AS n SET n.created_at = coalesce(n.created_at, datetime()), n.updated_at = datetime()",
        ),
        (
            "set_edge_timestamps_on_create",
            "CREATE TRIGGER set_edge_timestamps_on_create ON --> CREATE BEFORE COMMIT EXECUTE UNWIND createdEdges AS e SET e.created_at = coalesce(e.created_at, datetime()), e.updated_at = datetime()",
        ),
        (
            "set_node_updated_at_on_update",
            "CREATE TRIGGER set_node_updated_at_on_update ON () UPDATE BEFORE COMMIT EXECUTE UNWIND updatedVertices AS event SET event.vertex.updated_at = datetime()",
        ),
        (
            "set_edge_updated_at_on_update",
            "CREATE TRIGGER set_edge_updated_at_on_update ON --> UPDATE BEFORE COMMIT EXECUTE UNWIND updatedEdges AS event SET event.edge.updated_at = datetime()",
        ),
    ]
}

fn trigger_name_column_candidates() -> [&'static str; 7] {
    [
        "trigger_name",
        "trigger name",
        "Trigger name",
        "name",
        "Name",
        "trigger",
        "Trigger",
    ]
}

fn visibility_as_str(visibility: Visibility) -> &'static str {
    match visibility {
        Visibility::Private => "PRIVATE",
        Visibility::Shared => "SHARED",
    }
}

fn visibility_from_str(visibility: &str) -> Result<Visibility> {
    match visibility {
        "PRIVATE" => Ok(Visibility::Private),
        "SHARED" => Ok(Visibility::Shared),
        _ => anyhow::bail!("invalid visibility: {visibility}"),
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
