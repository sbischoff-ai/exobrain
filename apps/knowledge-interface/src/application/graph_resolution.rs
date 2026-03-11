use std::collections::{HashMap, HashSet};

use anyhow::{anyhow, Result};

use crate::{
    domain::{
        BlockNode, EntityNode, ExistingBlockContext, GraphEdge, PropertyScalar, PropertyValue,
        Visibility,
    },
    ports::GraphRepository,
};

use super::COMMON_UNIVERSE_ID;

pub(crate) fn extract_text(properties: &[PropertyValue]) -> String {
    properties
        .iter()
        .find_map(|prop| match (&prop.key[..], &prop.value) {
            ("text", PropertyScalar::String(value)) => Some(value.clone()),
            _ => None,
        })
        .unwrap_or_default()
}

pub(crate) async fn block_levels_for_blocks(
    blocks: &[BlockNode],
    edges: &[GraphEdge],
    graph_repository: &dyn GraphRepository,
) -> Result<HashMap<String, i64>> {
    let contexts =
        existing_block_context_for_referenced_summarize_parents(blocks, edges, graph_repository)
            .await?;

    let block_ids: HashSet<&str> = blocks.iter().map(|b| b.id.as_str()).collect();
    let mut levels: HashMap<String, i64> = HashMap::new();

    for edge in edges {
        if edge.edge_type.eq_ignore_ascii_case("DESCRIBED_BY")
            && block_ids.contains(edge.to_id.as_str())
        {
            levels.entry(edge.to_id.clone()).or_insert(0);
        }
    }

    for (block_id, context) in &contexts {
        levels
            .entry(block_id.clone())
            .or_insert(context.block_level);
    }

    for block in blocks {
        if levels.contains_key(&block.id) {
            continue;
        }
        if let Some(existing) = graph_repository
            .get_existing_block_context(&block.id, &block.user_id, block.visibility)
            .await?
        {
            levels.insert(block.id.clone(), existing.block_level);
        }
    }

    let summarize_edges: Vec<(&str, &str)> = edges
        .iter()
        .filter(|edge| {
            edge.edge_type.eq_ignore_ascii_case("SUMMARIZES")
                && (block_ids.contains(edge.from_id.as_str())
                    || contexts.contains_key(edge.from_id.as_str()))
                && block_ids.contains(edge.to_id.as_str())
        })
        .map(|edge| (edge.from_id.as_str(), edge.to_id.as_str()))
        .collect();

    let mut changed = true;
    while changed {
        changed = false;
        for (from_id, to_id) in &summarize_edges {
            if let Some(from_level) = levels.get(*from_id) {
                let candidate = from_level + 1;
                let existing = levels.get(*to_id).copied();
                if existing.is_none() || candidate < existing.unwrap_or(i64::MAX) {
                    levels.insert((*to_id).to_string(), candidate);
                    changed = true;
                }
            }
        }
    }

    levels.retain(|id, _| block_ids.contains(id.as_str()));

    Ok(levels)
}

pub(crate) async fn root_entity_ids_for_blocks(
    blocks: &[BlockNode],
    edges: &[GraphEdge],
    graph_repository: &dyn GraphRepository,
) -> Result<HashMap<String, String>> {
    let contexts =
        existing_block_context_for_referenced_summarize_parents(blocks, edges, graph_repository)
            .await?;

    let block_ids: HashSet<&str> = blocks.iter().map(|b| b.id.as_str()).collect();
    let described_by_parents: HashMap<&str, &str> = edges
        .iter()
        .filter(|e| {
            e.edge_type.eq_ignore_ascii_case("DESCRIBED_BY") && block_ids.contains(e.to_id.as_str())
        })
        .map(|e| (e.to_id.as_str(), e.from_id.as_str()))
        .collect();
    let summarize_parents: HashMap<&str, &str> = edges
        .iter()
        .filter(|e| {
            e.edge_type.eq_ignore_ascii_case("SUMMARIZES") && block_ids.contains(e.to_id.as_str())
        })
        .map(|e| (e.to_id.as_str(), e.from_id.as_str()))
        .collect();

    let mut out = HashMap::new();
    for block in blocks {
        let mut current = block.id.as_str();
        let mut seen = HashSet::new();
        loop {
            if !seen.insert(current) {
                return Err(anyhow!(
                    "cycle detected while resolving root_entity_id for block {}",
                    block.id
                ));
            }
            if let Some(root_entity) = described_by_parents.get(current) {
                out.insert(block.id.clone(), (*root_entity).to_string());
                break;
            }
            if let Some(parent_block) = summarize_parents.get(current) {
                if let Some(parent_context) = contexts.get(*parent_block) {
                    out.insert(block.id.clone(), parent_context.root_entity_id.clone());
                    break;
                }
                current = parent_block;
                continue;
            }
            if let Some(context) = contexts.get(current) {
                out.insert(block.id.clone(), context.root_entity_id.clone());
                break;
            }
            if let Some(existing) = graph_repository
                .get_existing_block_context(current, &block.user_id, block.visibility)
                .await?
            {
                out.insert(block.id.clone(), existing.root_entity_id);
                break;
            }
            return Err(anyhow!(
                "unable to resolve root_entity_id for block {} from DESCRIBED_BY/SUMMARIZES edges",
                block.id
            ));
        }
    }
    Ok(out)
}

async fn existing_block_context_for_referenced_summarize_parents(
    blocks: &[BlockNode],
    edges: &[GraphEdge],
    graph_repository: &dyn GraphRepository,
) -> Result<HashMap<String, ExistingBlockContext>> {
    let block_ids: HashSet<&str> = blocks.iter().map(|b| b.id.as_str()).collect();
    let parent_scopes: HashMap<&str, (&str, Visibility)> = edges
        .iter()
        .filter(|edge| {
            edge.edge_type.eq_ignore_ascii_case("SUMMARIZES")
                && block_ids.contains(edge.to_id.as_str())
                && !block_ids.contains(edge.from_id.as_str())
        })
        .map(|edge| {
            (
                edge.from_id.as_str(),
                (edge.user_id.as_str(), edge.visibility),
            )
        })
        .collect();

    let mut contexts = HashMap::new();
    for (parent_id, (user_id, visibility)) in parent_scopes {
        let context = graph_repository
            .get_existing_block_context(parent_id, user_id, visibility)
            .await?
            .ok_or_else(|| {
                anyhow!(
                    "unable to resolve root_entity_id for block {} from DESCRIBED_BY/SUMMARIZES edges",
                    parent_id
                )
            })?;
        contexts.insert(parent_id.to_string(), context);
    }

    Ok(contexts)
}

pub(crate) fn resolve_block_universe_id<'a>(
    root_entity_ids: &HashMap<String, String>,
    block: &BlockNode,
    entities: &'a [EntityNode],
) -> &'a str {
    if let Some(root_entity_id) = root_entity_ids.get(&block.id) {
        if let Some(entity) = entities.iter().find(|entity| &entity.id == root_entity_id) {
            return entity.universe_id.as_deref().unwrap_or(COMMON_UNIVERSE_ID);
        }
    }

    COMMON_UNIVERSE_ID
}
