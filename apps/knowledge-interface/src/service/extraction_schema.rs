use std::cmp::Ordering;
use std::collections::{BTreeMap, HashMap};

use crate::domain::{FullSchema, SchemaKind};

#[derive(Debug, Clone)]
pub(crate) struct ExtractionSchemaOptions {
    pub include_edge_properties: bool,
    pub include_inactive: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ExtractionAllowedEdge {
    pub edge_type_id: String,
    pub edge_name: String,
    pub edge_description: String,
    pub other_entity_type_id: String,
    pub other_entity_type_name: String,
    pub min_cardinality: Option<u32>,
    pub max_cardinality: Option<u32>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ExtractionUniverseContext {
    pub id: String,
    pub name: String,
    pub described_by_text: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ExtractionEntityType {
    pub type_id: String,
    pub name: String,
    pub description: String,
    pub inheritance_chain: Vec<String>,
    pub outgoing_edges: Vec<ExtractionAllowedEdge>,
    pub incoming_edges: Vec<ExtractionAllowedEdge>,
}

pub(crate) fn build_extraction_entity_types(
    schema: FullSchema,
    options: ExtractionSchemaOptions,
) -> Vec<ExtractionEntityType> {
    let _include_edge_properties = options.include_edge_properties;
    let node_types = schema.node_types;
    let edge_types = schema.edge_types;

    let type_name_by_id: HashMap<String, String> = node_types
        .iter()
        .map(|node| (node.schema_type.id.clone(), node.schema_type.name.clone()))
        .collect();

    let parent_by_child: BTreeMap<String, String> = node_types
        .iter()
        .flat_map(|node| {
            node.parents
                .iter()
                .filter(move |parent| options.include_inactive || parent.active)
                .map(|parent| (node.schema_type.id.clone(), parent.parent_type_id.clone()))
        })
        .fold(BTreeMap::new(), |mut acc, (child, parent)| {
            acc.entry(child)
                .and_modify(|existing| {
                    if parent < *existing {
                        *existing = parent.clone();
                    }
                })
                .or_insert(parent);
            acc
        });

    let edge_meta_by_id: HashMap<String, (String, String)> = edge_types
        .iter()
        .filter(|edge| options.include_inactive || edge.schema_type.active)
        .map(|edge| {
            (
                edge.schema_type.id.clone(),
                (
                    edge.schema_type.name.clone(),
                    edge.schema_type.description.clone(),
                ),
            )
        })
        .collect();

    let mut entity_types = node_types
        .into_iter()
        .filter(|node| matches!(node.schema_type.schema_kind(), Some(SchemaKind::Node)))
        .filter(|node| node.schema_type.id != "node")
        .filter(|node| options.include_inactive || node.schema_type.active)
        .map(|node| {
            let mut inheritance_chain = vec![node.schema_type.id.clone()];
            let mut current = node.schema_type.id.clone();
            while let Some(parent_id) = parent_by_child.get(&current) {
                inheritance_chain.push(parent_id.clone());
                current = parent_id.clone();
            }
            inheritance_chain.reverse();

            let mut outgoing_edges: Vec<ExtractionAllowedEdge> = edge_types
                .iter()
                .flat_map(|edge| edge.rules.iter())
                .filter(|rule| options.include_inactive || rule.active)
                .filter(|rule| {
                    extraction_type_is_assignable(
                        &node.schema_type.id,
                        &rule.from_node_type_id,
                        &parent_by_child,
                    )
                })
                .filter_map(|rule| {
                    let (edge_name, edge_description) = edge_meta_by_id.get(&rule.edge_type_id)?;
                    Some(ExtractionAllowedEdge {
                        edge_type_id: rule.edge_type_id.clone(),
                        edge_name: edge_name.clone(),
                        edge_description: edge_description.clone(),
                        other_entity_type_id: rule.to_node_type_id.clone(),
                        other_entity_type_name: type_name_by_id
                            .get(&rule.to_node_type_id)
                            .cloned()
                            .unwrap_or_default(),
                        min_cardinality: None,
                        max_cardinality: None,
                    })
                })
                .collect();
            outgoing_edges.sort_by(extraction_allowed_edge_sort_key);

            let mut incoming_edges: Vec<ExtractionAllowedEdge> = edge_types
                .iter()
                .flat_map(|edge| edge.rules.iter())
                .filter(|rule| options.include_inactive || rule.active)
                .filter(|rule| {
                    extraction_type_is_assignable(
                        &node.schema_type.id,
                        &rule.to_node_type_id,
                        &parent_by_child,
                    )
                })
                .filter_map(|rule| {
                    let (edge_name, edge_description) = edge_meta_by_id.get(&rule.edge_type_id)?;
                    Some(ExtractionAllowedEdge {
                        edge_type_id: rule.edge_type_id.clone(),
                        edge_name: edge_name.clone(),
                        edge_description: edge_description.clone(),
                        other_entity_type_id: rule.from_node_type_id.clone(),
                        other_entity_type_name: type_name_by_id
                            .get(&rule.from_node_type_id)
                            .cloned()
                            .unwrap_or_default(),
                        min_cardinality: None,
                        max_cardinality: None,
                    })
                })
                .collect();
            incoming_edges.sort_by(extraction_allowed_edge_sort_key);

            ExtractionEntityType {
                type_id: node.schema_type.id,
                name: node.schema_type.name,
                description: node.schema_type.description,
                inheritance_chain,
                outgoing_edges,
                incoming_edges,
            }
        })
        .collect::<Vec<_>>();

    entity_types.sort_by(|a, b| a.type_id.cmp(&b.type_id));
    entity_types
}

fn extraction_type_is_assignable(
    node_type_id: &str,
    target_type_id: &str,
    inheritance: &BTreeMap<String, String>,
) -> bool {
    if node_type_id == target_type_id {
        return true;
    }

    let mut current = node_type_id;
    while let Some(parent) = inheritance.get(current) {
        if parent == target_type_id {
            return true;
        }
        current = parent;
    }

    false
}

fn extraction_allowed_edge_sort_key(
    a: &ExtractionAllowedEdge,
    b: &ExtractionAllowedEdge,
) -> Ordering {
    a.edge_type_id
        .cmp(&b.edge_type_id)
        .then_with(|| a.other_entity_type_id.cmp(&b.other_entity_type_id))
        .then_with(|| a.edge_name.cmp(&b.edge_name))
        .then_with(|| a.other_entity_type_name.cmp(&b.other_entity_type_name))
}
