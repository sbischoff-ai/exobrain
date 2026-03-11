use std::collections::{HashMap, HashSet};

use anyhow::{anyhow, Result};

use crate::domain::{EmbeddedBlock, GraphDelta, SchemaKind};

use crate::application::{
    block_levels_for_blocks, extract_text, is_assignable, resolve_block_universe_id,
    resolve_labels_for_type, root_entity_ids_for_blocks, validate_graph_id,
    validate_internal_timestamps_not_provided, validate_properties, KnowledgeApplication,
    COMMON_UNIVERSE_ID,
};

pub(crate) async fn upsert_graph_delta_internal(
    app: &KnowledgeApplication,
    mut delta: GraphDelta,
) -> Result<()> {
    let inheritance = validate_delta_against_schema(app, &delta).await?;

    for entity in &mut delta.entities {
        entity.resolved_labels = resolve_labels_for_type(&entity.type_id, &inheritance);
    }
    for block in &mut delta.blocks {
        block.resolved_labels = resolve_labels_for_type(&block.type_id, &inheritance);
    }

    let texts: Vec<String> = delta
        .blocks
        .iter()
        .map(|block| extract_text(&block.properties))
        .collect();
    let vectors = app.embedder.embed_texts(&texts).await?;

    let block_levels =
        block_levels_for_blocks(&delta.blocks, &delta.edges, app.graph_repository.as_ref()).await?;
    let root_entity_ids =
        root_entity_ids_for_blocks(&delta.blocks, &delta.edges, app.graph_repository.as_ref())
            .await?;

    let blocks: Vec<EmbeddedBlock> = delta
        .blocks
        .iter()
        .zip(vectors.into_iter())
        .zip(texts.into_iter())
        .map(|((block, vector), text)| EmbeddedBlock {
            block: block.clone(),
            root_entity_id: root_entity_ids.get(&block.id).cloned().unwrap_or_default(),
            universe_id: resolve_block_universe_id(&root_entity_ids, block, &delta.entities)
                .to_string(),
            user_id: block.user_id.clone(),
            visibility: block.visibility,
            vector,
            block_level: block_levels.get(&block.id).copied().unwrap_or(0),
            text,
        })
        .collect();

    app.graph_repository
        .apply_delta_with_blocks(&delta, &blocks)
        .await
}

async fn validate_delta_against_schema(
    app: &KnowledgeApplication,
    delta: &GraphDelta,
) -> Result<Vec<crate::domain::TypeInheritance>> {
    let schema_types = app
        .schema_repository
        .get_by_kind(SchemaKind::Node)
        .await?
        .into_iter()
        .map(|t| (t.id.clone(), t))
        .collect::<HashMap<_, _>>();
    let edge_types = app
        .schema_repository
        .get_by_kind(SchemaKind::Edge)
        .await?
        .into_iter()
        .map(|t| (t.id.clone(), t))
        .collect::<HashMap<_, _>>();
    let inheritance = app.schema_repository.get_type_inheritance().await?;
    let properties = app.schema_repository.get_all_properties().await?;
    let edge_rules = app.schema_repository.get_edge_endpoint_rules().await?;

    let mut node_type_by_id = HashMap::new();
    let mut errors = vec![];

    for universe in &delta.universes {
        if let Err(err) = validate_graph_id(&universe.id, "universe") {
            errors.push(err);
            continue;
        }
        if universe.name.trim().is_empty() {
            errors.push(format!("universe {} name is required", universe.id));
        }
        node_type_by_id.insert(universe.id.clone(), "node.universe".to_string());
    }

    for entity in &delta.entities {
        if let Err(err) = validate_graph_id(&entity.id, "entity") {
            errors.push(err);
            continue;
        }
        let node_type = entity.type_id.clone();
        node_type_by_id.insert(entity.id.clone(), node_type.clone());
        if let Some(universe_id) = &entity.universe_id {
            if !node_type_by_id.contains_key(universe_id)
                && !delta.universes.iter().any(|u| &u.id == universe_id)
                && universe_id != COMMON_UNIVERSE_ID
            {
                errors.push(format!(
                    "entity {} references unknown universe {}",
                    entity.id, universe_id
                ));
            }
        }
        if !schema_types.contains_key(&node_type) {
            errors.push(format!(
                "entity {} uses unknown schema type {}",
                entity.id, node_type
            ));
        } else if !is_assignable(&node_type, "node.entity", &inheritance) {
            errors.push(format!(
                "entity {} type {} must descend from node.entity",
                entity.id, node_type
            ));
        }
        validate_properties(
            &entity.id,
            &node_type,
            &entity.properties,
            &properties,
            &inheritance,
            &mut errors,
        );
        validate_internal_timestamps_not_provided(&entity.id, &entity.properties, &mut errors);
    }

    for block in &delta.blocks {
        if let Err(err) = validate_graph_id(&block.id, "block") {
            errors.push(err);
            continue;
        }
        let node_type = block.type_id.clone();
        node_type_by_id.insert(block.id.clone(), node_type.clone());
        if !schema_types.contains_key(&node_type) {
            errors.push(format!(
                "block {} uses unknown schema type {}",
                block.id, node_type
            ));
        } else if !is_assignable(&node_type, "node.block", &inheritance) {
            errors.push(format!(
                "block {} type {} must descend from node.block",
                block.id, node_type
            ));
        }
        validate_properties(
            &block.id,
            &node_type,
            &block.properties,
            &properties,
            &inheritance,
            &mut errors,
        );
        validate_internal_timestamps_not_provided(&block.id, &block.properties, &mut errors);
    }

    for edge in &delta.edges {
        if let Err(err) = validate_graph_id(&edge.from_id, "edge.from_id") {
            errors.push(err);
        }
        if let Err(err) = validate_graph_id(&edge.to_id, "edge.to_id") {
            errors.push(err);
        }
        let edge_type_id = format!("edge.{}", edge.edge_type.to_lowercase());
        if !edge_types.contains_key(&edge_type_id) {
            errors.push(format!(
                "edge {}->{} references unknown edge type {}",
                edge.from_id, edge.to_id, edge.edge_type
            ));
            continue;
        }
        validate_properties(
            &format!("{}:{}->{}", edge.edge_type, edge.from_id, edge.to_id),
            &edge_type_id,
            &edge.properties,
            &properties,
            &inheritance,
            &mut errors,
        );
        validate_internal_timestamps_not_provided(
            &format!("{}:{}->{}", edge.edge_type, edge.from_id, edge.to_id),
            &edge.properties,
            &mut errors,
        );
        if let (Some(from_type), Some(to_type)) = (
            node_type_by_id.get(&edge.from_id),
            node_type_by_id.get(&edge.to_id),
        ) {
            let involves_universe = from_type == "node.universe" || to_type == "node.universe";
            let valid_rule = involves_universe
                || edge_rules.iter().any(|rule| {
                    rule.edge_type_id == edge_type_id
                        && is_assignable(from_type, &rule.from_node_type_id, &inheritance)
                        && is_assignable(to_type, &rule.to_node_type_id, &inheritance)
                });
            if !valid_rule {
                errors.push(format!(
                    "edge {} ({}) violates schema endpoint rules for {} -> {}",
                    edge.edge_type, edge_type_id, from_type, to_type
                ));
            }
        }
    }

    enforce_graph_state_rules(app, delta, &mut errors).await?;

    if errors.is_empty() {
        return Ok(inheritance);
    }

    Err(anyhow!(
        "graph delta validation failed:\n- {}",
        errors.join("\n- ")
    ))
}

async fn enforce_graph_state_rules(
    app: &KnowledgeApplication,
    delta: &GraphDelta,
    errors: &mut Vec<String>,
) -> Result<()> {
    let universe_ids: HashSet<&str> = delta.universes.iter().map(|u| u.id.as_str()).collect();
    let mut incoming_by_node: HashMap<&str, usize> = HashMap::new();
    let mut outgoing_by_node: HashMap<&str, usize> = HashMap::new();
    let mut entity_is_part_of: HashMap<&str, usize> = HashMap::new();
    let mut block_parent_edges: HashMap<&str, usize> = HashMap::new();
    let mut entity_described_by_edges: HashMap<&str, usize> = HashMap::new();
    let mut universe_described_by_edges: HashMap<&str, usize> = HashMap::new();

    for edge in &delta.edges {
        *incoming_by_node.entry(edge.to_id.as_str()).or_insert(0) += 1;
        *outgoing_by_node.entry(edge.from_id.as_str()).or_insert(0) += 1;

        if edge.edge_type.eq_ignore_ascii_case("IS_PART_OF") {
            *entity_is_part_of.entry(edge.from_id.as_str()).or_insert(0) += 1;
        }
        if edge.edge_type.eq_ignore_ascii_case("DESCRIBED_BY") {
            *block_parent_edges.entry(edge.to_id.as_str()).or_insert(0) += 1;
            if universe_ids.contains(edge.from_id.as_str()) {
                *universe_described_by_edges
                    .entry(edge.from_id.as_str())
                    .or_insert(0) += 1;
            } else {
                *entity_described_by_edges
                    .entry(edge.from_id.as_str())
                    .or_insert(0) += 1;
            }
        }
        if edge.edge_type.eq_ignore_ascii_case("SUMMARIZES") {
            *block_parent_edges.entry(edge.to_id.as_str()).or_insert(0) += 1;
        }
    }

    for entity in &delta.entities {
        let target_universe_id = entity.universe_id.as_deref().unwrap_or(COMMON_UNIVERSE_ID);
        *outgoing_by_node.entry(entity.id.as_str()).or_insert(0) += 1;
        *incoming_by_node.entry(target_universe_id).or_insert(0) += 1;
        *entity_is_part_of.entry(entity.id.as_str()).or_insert(0) += 1;
    }

    for universe in &delta.universes {
        let existing = app
            .graph_repository
            .get_node_relationship_counts(&universe.id)
            .await?;
        let payload_total = incoming_by_node
            .get(universe.id.as_str())
            .copied()
            .unwrap_or(0)
            + outgoing_by_node
                .get(universe.id.as_str())
                .copied()
                .unwrap_or(0);
        if existing.total + payload_total == 0 {
            errors.push(format!(
                "universe {} must have at least one relationship",
                universe.id
            ));
        }
        let payload_described_by = universe_described_by_edges
            .get(universe.id.as_str())
            .copied()
            .unwrap_or(0);
        if existing.universe_described_by_edges + payload_described_by > 1 {
            errors.push(format!(
                "universe {} must have exactly one outgoing DESCRIBED_BY edge",
                universe.id
            ));
        }
    }

    for entity in &delta.entities {
        let existing = app
            .graph_repository
            .get_node_relationship_counts(&entity.id)
            .await?;
        let payload_total = incoming_by_node
            .get(entity.id.as_str())
            .copied()
            .unwrap_or(0)
            + outgoing_by_node
                .get(entity.id.as_str())
                .copied()
                .unwrap_or(0);
        if existing.total + payload_total == 0 {
            errors.push(format!(
                "entity {} must have at least one relationship",
                entity.id
            ));
        }
        let payload_is_part_of = entity_is_part_of
            .get(entity.id.as_str())
            .copied()
            .unwrap_or(0);
        if existing.entity_is_part_of + payload_is_part_of == 0 {
            errors.push(format!(
                "entity {} must have IS_PART_OF edge to a universe",
                entity.id
            ));
        }
        let payload_described_by = entity_described_by_edges
            .get(entity.id.as_str())
            .copied()
            .unwrap_or(0);
        if existing.entity_described_by_edges + payload_described_by > 1 {
            errors.push(format!(
                "entity {} must have exactly one outgoing DESCRIBED_BY edge",
                entity.id
            ));
        }
    }

    for block in &delta.blocks {
        let existing = app
            .graph_repository
            .get_node_relationship_counts(&block.id)
            .await?;
        let payload_total = incoming_by_node
            .get(block.id.as_str())
            .copied()
            .unwrap_or(0)
            + outgoing_by_node
                .get(block.id.as_str())
                .copied()
                .unwrap_or(0);
        if existing.total + payload_total == 0 {
            errors.push(format!(
                "block {} must have at least one relationship",
                block.id
            ));
        }
        let payload_parent_count = block_parent_edges
            .get(block.id.as_str())
            .copied()
            .unwrap_or(0);
        let total_parent_count = existing.block_parent_edges + payload_parent_count;
        if total_parent_count != 1 {
            errors.push(format!(
                "block {} must have exactly one incoming DESCRIBED_BY or SUMMARIZES edge",
                block.id
            ));
        }
    }

    Ok(())
}
