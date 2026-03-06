use std::cmp::Ordering;
use std::collections::{BTreeMap, HashMap};

use anyhow::{anyhow, Result};

use crate::domain::{EdgeEndpointRule, FullSchema, SchemaKind, SchemaType, TypeInheritance};

#[derive(Debug, Clone)]
pub(crate) struct ExtractionSchemaBuildInput {
    pub node_types: Vec<SchemaType>,
    pub edge_types: Vec<SchemaType>,
    pub inheritance: Vec<TypeInheritance>,
    pub edge_rules: Vec<EdgeEndpointRule>,
}

#[derive(Debug, Clone)]
pub(crate) struct ExtractionSchemaOptions {
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
pub(crate) struct ExtractionEdgeType {
    pub edge_type_id: String,
    pub edge_name: String,
    pub edge_description: String,
    pub source_entity_type_id: String,
    pub target_entity_type_id: String,
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

#[derive(Debug, Clone)]
pub(crate) struct EntityTypePropertyContextOptions {
    pub include_inactive: bool,
    pub include_inherited: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ExtractionPropertyContext {
    pub prop_name: String,
    pub value_type: String,
    pub required: bool,
    pub readable: bool,
    pub writable: bool,
    pub description: String,
    pub declared_on_type_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct EntityTypePropertyContext {
    pub type_id: String,
    pub type_name: String,
    pub inheritance_chain: Vec<String>,
    pub properties: Vec<ExtractionPropertyContext>,
}

pub(crate) fn build_extraction_entity_types_from_input(
    input: ExtractionSchemaBuildInput,
    options: ExtractionSchemaOptions,
) -> Vec<ExtractionEntityType> {
    let type_name_by_id: HashMap<String, String> = input
        .node_types
        .iter()
        .map(|node| (node.id.clone(), node.name.clone()))
        .collect();

    let parent_by_child: BTreeMap<String, String> = input
        .inheritance
        .iter()
        .filter(|parent| options.include_inactive || parent.active)
        .map(|parent| (parent.child_type_id.clone(), parent.parent_type_id.clone()))
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

    let edge_meta_by_id: HashMap<String, (String, String)> = input
        .edge_types
        .iter()
        .filter(|edge| options.include_inactive || edge.active)
        .map(|edge| {
            (
                edge.id.clone(),
                (edge.name.clone(), edge.description.clone()),
            )
        })
        .collect();

    let mut entity_types = input
        .node_types
        .into_iter()
        .filter(|node| matches!(node.schema_kind(), Some(SchemaKind::Node)))
        .filter(|node| node.id != "node")
        .filter(|node| options.include_inactive || node.active)
        .map(|node| {
            let mut inheritance_chain = vec![node.id.clone()];
            let mut current = node.id.clone();
            while let Some(parent_id) = parent_by_child.get(&current) {
                inheritance_chain.push(parent_id.clone());
                current = parent_id.clone();
            }
            inheritance_chain.reverse();

            let mut outgoing_edges: Vec<ExtractionAllowedEdge> = input
                .edge_rules
                .iter()
                .filter(|rule| options.include_inactive || rule.active)
                .filter(|rule| {
                    extraction_type_is_assignable(
                        &node.id,
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

            let mut incoming_edges: Vec<ExtractionAllowedEdge> = input
                .edge_rules
                .iter()
                .filter(|rule| options.include_inactive || rule.active)
                .filter(|rule| {
                    extraction_type_is_assignable(&node.id, &rule.to_node_type_id, &parent_by_child)
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
                type_id: node.id,
                name: node.name,
                description: node.description,
                inheritance_chain,
                outgoing_edges,
                incoming_edges,
            }
        })
        .collect::<Vec<_>>();

    entity_types.sort_by(|a, b| a.type_id.cmp(&b.type_id));
    entity_types
}

pub(crate) fn build_extraction_edge_types_from_input(
    input: ExtractionSchemaBuildInput,
    first_entity_type: &str,
    second_entity_type: &str,
    options: ExtractionSchemaOptions,
) -> Vec<ExtractionEdgeType> {
    let first = first_entity_type.trim();
    let second = second_entity_type.trim();
    if first.is_empty() || second.is_empty() {
        return Vec::new();
    }

    let parent_by_child: BTreeMap<String, String> = input
        .inheritance
        .iter()
        .filter(|parent| options.include_inactive || parent.active)
        .map(|parent| (parent.child_type_id.clone(), parent.parent_type_id.clone()))
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

    let edge_meta_by_id: HashMap<String, (String, String)> = input
        .edge_types
        .iter()
        .filter(|edge| options.include_inactive || edge.active)
        .map(|edge| {
            (
                edge.id.clone(),
                (edge.name.clone(), edge.description.clone()),
            )
        })
        .collect();

    let mut edge_types = input
        .edge_rules
        .iter()
        .filter(|rule| options.include_inactive || rule.active)
        .filter(|rule| {
            let supports_forward =
                extraction_type_is_assignable(first, &rule.from_node_type_id, &parent_by_child)
                    && extraction_type_is_assignable(
                        second,
                        &rule.to_node_type_id,
                        &parent_by_child,
                    );
            let supports_reverse =
                extraction_type_is_assignable(second, &rule.from_node_type_id, &parent_by_child)
                    && extraction_type_is_assignable(
                        first,
                        &rule.to_node_type_id,
                        &parent_by_child,
                    );
            supports_forward || supports_reverse
        })
        .filter_map(|rule| {
            let (edge_name, edge_description) = edge_meta_by_id.get(&rule.edge_type_id)?;
            Some(ExtractionEdgeType {
                edge_type_id: rule.edge_type_id.clone(),
                edge_name: edge_name.clone(),
                edge_description: edge_description.clone(),
                source_entity_type_id: rule.from_node_type_id.clone(),
                target_entity_type_id: rule.to_node_type_id.clone(),
            })
        })
        .collect::<Vec<_>>();

    edge_types.sort_by(|a, b| {
        (
            a.edge_type_id.as_str(),
            a.source_entity_type_id.as_str(),
            a.target_entity_type_id.as_str(),
        )
            .cmp(&(
                b.edge_type_id.as_str(),
                b.source_entity_type_id.as_str(),
                b.target_entity_type_id.as_str(),
            ))
    });

    edge_types
}

/// Builds property context for a node type using root-to-leaf inheritance resolution.
///
/// Override precedence for duplicate property names is deterministic:
/// 1. A property declared on a more specific type (closer to the leaf) wins.
/// 2. If specificity ties, lexicographically smaller `owner_type_id` wins.
pub(crate) fn build_entity_type_property_context(
    schema: FullSchema,
    type_id: &str,
    options: EntityTypePropertyContextOptions,
) -> Result<EntityTypePropertyContext> {
    let trimmed_type_id = type_id.trim();
    if trimmed_type_id.is_empty() {
        return Err(anyhow!("type_id is required"));
    }

    let mut nodes_by_id = HashMap::new();
    for node in &schema.node_types {
        if options.include_inactive || node.schema_type.active {
            nodes_by_id.insert(node.schema_type.id.clone(), node);
        }
    }

    let Some(target) = nodes_by_id.get(trimmed_type_id) else {
        return Err(anyhow!("unknown type_id"));
    };

    let mut parent_by_child = HashMap::new();
    for node in nodes_by_id.values() {
        for inheritance in &node.parents {
            if (options.include_inactive || inheritance.active)
                && nodes_by_id.contains_key(&inheritance.parent_type_id)
            {
                parent_by_child.insert(
                    node.schema_type.id.clone(),
                    inheritance.parent_type_id.clone(),
                );
            }
        }
    }

    let inheritance_chain =
        extraction_entity_type_inheritance_chain(&target.schema_type.id, &parent_by_child);

    let mut owner_type_ids: std::collections::HashSet<String> = std::collections::HashSet::new();
    owner_type_ids.insert("node".to_string());
    if options.include_inherited {
        for owner in &inheritance_chain {
            owner_type_ids.insert(owner.clone());
        }
    } else {
        owner_type_ids.insert(target.schema_type.id.clone());
    }

    let specificity: HashMap<String, usize> = inheritance_chain
        .iter()
        .enumerate()
        .map(|(idx, id)| (id.clone(), idx))
        .collect();

    let mut selected_by_name: HashMap<String, crate::domain::TypeProperty> = HashMap::new();

    for node in nodes_by_id.values() {
        for prop in &node.properties {
            if !owner_type_ids.contains(&prop.owner_type_id) {
                continue;
            }
            if !options.include_inactive && !prop.active {
                continue;
            }

            let existing = selected_by_name.get(&prop.prop_name);
            let new_score = *specificity.get(&prop.owner_type_id).unwrap_or(&0);
            let replace = match existing {
                None => true,
                Some(existing_prop) => {
                    let old_score = *specificity.get(&existing_prop.owner_type_id).unwrap_or(&0);
                    new_score > old_score
                        || (new_score == old_score
                            && prop.owner_type_id < existing_prop.owner_type_id)
                }
            };

            if replace {
                selected_by_name.insert(prop.prop_name.clone(), prop.clone());
            }
        }
    }

    let mut properties: Vec<ExtractionPropertyContext> = selected_by_name
        .into_values()
        .map(|prop| ExtractionPropertyContext {
            prop_name: prop.prop_name,
            value_type: prop.value_type,
            required: prop.required,
            readable: prop.readable,
            writable: prop.writable,
            description: prop.description,
            declared_on_type_id: prop.owner_type_id,
        })
        .collect();
    properties.sort_by(|a, b| a.prop_name.cmp(&b.prop_name));

    Ok(EntityTypePropertyContext {
        type_id: target.schema_type.id.clone(),
        type_name: target.schema_type.name.clone(),
        inheritance_chain,
        properties,
    })
}

fn extraction_entity_type_inheritance_chain(
    type_id: &str,
    parent_by_child: &HashMap<String, String>,
) -> Vec<String> {
    let mut chain = Vec::new();
    let mut current = type_id.to_string();
    let mut seen = std::collections::HashSet::new();

    loop {
        if !seen.insert(current.clone()) {
            break;
        }
        chain.push(current.clone());
        let Some(parent) = parent_by_child.get(&current).cloned() else {
            break;
        };
        current = parent;
    }

    chain.reverse();
    chain
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

#[cfg(test)]
mod tests {
    use super::{
        build_entity_type_property_context, build_extraction_edge_types_from_input,
        EntityTypePropertyContextOptions, ExtractionSchemaBuildInput, ExtractionSchemaOptions,
    };
    use crate::domain::{
        EdgeEndpointRule, FullSchema, SchemaNodeTypeHydrated, SchemaType, TypeInheritance,
        TypeProperty,
    };

    #[test]
    fn entity_type_property_context_prefers_more_specific_override() {
        let schema = FullSchema {
            node_types: vec![
                SchemaNodeTypeHydrated {
                    schema_type: SchemaType {
                        id: "node.entity".to_string(),
                        kind: "node".to_string(),
                        name: "Entity".to_string(),
                        description: "Root".to_string(),
                        active: true,
                    },
                    properties: vec![TypeProperty {
                        owner_type_id: "node.entity".to_string(),
                        prop_name: "name".to_string(),
                        value_type: "string".to_string(),
                        required: false,
                        readable: true,
                        writable: false,
                        active: true,
                        description: "root".to_string(),
                    }],
                    parents: vec![],
                },
                SchemaNodeTypeHydrated {
                    schema_type: SchemaType {
                        id: "node.person".to_string(),
                        kind: "node".to_string(),
                        name: "Person".to_string(),
                        description: "Leaf".to_string(),
                        active: true,
                    },
                    properties: vec![TypeProperty {
                        owner_type_id: "node.person".to_string(),
                        prop_name: "name".to_string(),
                        value_type: "text".to_string(),
                        required: true,
                        readable: true,
                        writable: true,
                        active: true,
                        description: "leaf".to_string(),
                    }],
                    parents: vec![TypeInheritance {
                        child_type_id: "node.person".to_string(),
                        parent_type_id: "node.entity".to_string(),
                        description: "inherits".to_string(),
                        active: true,
                    }],
                },
            ],
            edge_types: vec![],
        };

        let context = build_entity_type_property_context(
            schema,
            "node.person",
            EntityTypePropertyContextOptions {
                include_inactive: false,
                include_inherited: true,
            },
        )
        .expect("context should build");

        assert_eq!(context.properties.len(), 1);
        assert_eq!(context.properties[0].declared_on_type_id, "node.person");
        assert_eq!(context.properties[0].value_type, "text");
    }

    #[test]
    fn entity_type_property_context_filters_inactive_when_disabled() {
        let schema = FullSchema {
            node_types: vec![SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.person".to_string(),
                    kind: "node".to_string(),
                    name: "Person".to_string(),
                    description: "Leaf".to_string(),
                    active: true,
                },
                properties: vec![TypeProperty {
                    owner_type_id: "node.person".to_string(),
                    prop_name: "legacy".to_string(),
                    value_type: "string".to_string(),
                    required: false,
                    readable: true,
                    writable: true,
                    active: false,
                    description: "legacy".to_string(),
                }],
                parents: vec![],
            }],
            edge_types: vec![],
        };

        let filtered = build_entity_type_property_context(
            schema.clone(),
            "node.person",
            EntityTypePropertyContextOptions {
                include_inactive: false,
                include_inherited: true,
            },
        )
        .expect("context should build");
        assert!(filtered.properties.is_empty());

        let included = build_entity_type_property_context(
            schema,
            "node.person",
            EntityTypePropertyContextOptions {
                include_inactive: true,
                include_inherited: true,
            },
        )
        .expect("context should build");
        assert_eq!(included.properties.len(), 1);
    }

    #[test]
    fn entity_type_property_context_includes_inherited_when_enabled() {
        let schema = FullSchema {
            node_types: vec![
                SchemaNodeTypeHydrated {
                    schema_type: SchemaType {
                        id: "node.entity".to_string(),
                        kind: "node".to_string(),
                        name: "Entity".to_string(),
                        description: "Root".to_string(),
                        active: true,
                    },
                    properties: vec![TypeProperty {
                        owner_type_id: "node.entity".to_string(),
                        prop_name: "name".to_string(),
                        value_type: "string".to_string(),
                        required: true,
                        readable: true,
                        writable: true,
                        active: true,
                        description: "entity name".to_string(),
                    }],
                    parents: vec![],
                },
                SchemaNodeTypeHydrated {
                    schema_type: SchemaType {
                        id: "node.person".to_string(),
                        kind: "node".to_string(),
                        name: "Person".to_string(),
                        description: "Leaf".to_string(),
                        active: true,
                    },
                    properties: vec![TypeProperty {
                        owner_type_id: "node.person".to_string(),
                        prop_name: "birthdate".to_string(),
                        value_type: "datetime".to_string(),
                        required: false,
                        readable: true,
                        writable: true,
                        active: true,
                        description: "date of birth".to_string(),
                    }],
                    parents: vec![TypeInheritance {
                        child_type_id: "node.person".to_string(),
                        parent_type_id: "node.entity".to_string(),
                        description: "inherits".to_string(),
                        active: true,
                    }],
                },
            ],
            edge_types: vec![],
        };

        let context = build_entity_type_property_context(
            schema,
            "node.person",
            EntityTypePropertyContextOptions {
                include_inactive: false,
                include_inherited: true,
            },
        )
        .expect("context should build");

        assert_eq!(
            context.inheritance_chain,
            vec!["node.entity", "node.person"]
        );
        assert_eq!(context.properties.len(), 2);
        assert_eq!(
            context
                .properties
                .iter()
                .map(|p| p.prop_name.as_str())
                .collect::<Vec<_>>(),
            vec!["birthdate", "name"]
        );
    }

    #[test]
    fn entity_type_property_context_excludes_inactive_types_by_default() {
        let schema = FullSchema {
            node_types: vec![SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.person".to_string(),
                    kind: "node".to_string(),
                    name: "Person".to_string(),
                    description: "Leaf".to_string(),
                    active: false,
                },
                properties: vec![],
                parents: vec![],
            }],
            edge_types: vec![],
        };

        let err = build_entity_type_property_context(
            schema,
            "node.person",
            EntityTypePropertyContextOptions {
                include_inactive: false,
                include_inherited: true,
            },
        )
        .expect_err("inactive type should be excluded");

        assert!(err.to_string().contains("unknown type_id"));
    }

    #[test]
    fn entity_type_property_context_properties_are_stably_sorted() {
        let schema = FullSchema {
            node_types: vec![SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.person".to_string(),
                    kind: "node".to_string(),
                    name: "Person".to_string(),
                    description: "Leaf".to_string(),
                    active: true,
                },
                properties: vec![
                    TypeProperty {
                        owner_type_id: "node.person".to_string(),
                        prop_name: "zeta".to_string(),
                        value_type: "string".to_string(),
                        required: false,
                        readable: true,
                        writable: true,
                        active: true,
                        description: "z".to_string(),
                    },
                    TypeProperty {
                        owner_type_id: "node.person".to_string(),
                        prop_name: "alpha".to_string(),
                        value_type: "string".to_string(),
                        required: false,
                        readable: true,
                        writable: true,
                        active: true,
                        description: "a".to_string(),
                    },
                ],
                parents: vec![],
            }],
            edge_types: vec![],
        };

        let context = build_entity_type_property_context(
            schema,
            "node.person",
            EntityTypePropertyContextOptions {
                include_inactive: false,
                include_inherited: true,
            },
        )
        .expect("context should build");

        assert_eq!(
            context
                .properties
                .iter()
                .map(|p| p.prop_name.as_str())
                .collect::<Vec<_>>(),
            vec!["alpha", "zeta"]
        );
    }

    #[test]
    fn entity_type_property_context_rejects_unknown_type_id() {
        let schema = FullSchema {
            node_types: vec![],
            edge_types: vec![],
        };

        let err = build_entity_type_property_context(
            schema,
            "node.unknown",
            EntityTypePropertyContextOptions {
                include_inactive: false,
                include_inherited: true,
            },
        )
        .expect_err("unknown type should fail");

        assert!(err.to_string().contains("unknown type_id"));
    }

    #[test]
    fn extraction_edge_types_match_pair_regardless_of_order() {
        let input = ExtractionSchemaBuildInput {
            node_types: vec![],
            edge_types: vec![
                SchemaType {
                    id: "edge.assigned_to".to_string(),
                    kind: "edge".to_string(),
                    name: "ASSIGNED_TO".to_string(),
                    description: "assignment".to_string(),
                    active: true,
                },
                SchemaType {
                    id: "edge.located_at".to_string(),
                    kind: "edge".to_string(),
                    name: "LOCATED_AT".to_string(),
                    description: "location".to_string(),
                    active: true,
                },
            ],
            inheritance: vec![TypeInheritance {
                child_type_id: "node.person".to_string(),
                parent_type_id: "node.entity".to_string(),
                description: "inherits".to_string(),
                active: true,
            }],
            edge_rules: vec![
                EdgeEndpointRule {
                    edge_type_id: "edge.assigned_to".to_string(),
                    from_node_type_id: "node.person".to_string(),
                    to_node_type_id: "node.task".to_string(),
                    active: true,
                    description: String::new(),
                },
                EdgeEndpointRule {
                    edge_type_id: "edge.located_at".to_string(),
                    from_node_type_id: "node.person".to_string(),
                    to_node_type_id: "node.location".to_string(),
                    active: true,
                    description: String::new(),
                },
            ],
        };

        let forward = build_extraction_edge_types_from_input(
            input.clone(),
            "node.person",
            "node.task",
            ExtractionSchemaOptions {
                include_inactive: false,
            },
        );
        let reverse = build_extraction_edge_types_from_input(
            input,
            "node.task",
            "node.person",
            ExtractionSchemaOptions {
                include_inactive: false,
            },
        );

        assert_eq!(forward.len(), 1);
        assert_eq!(forward[0].edge_type_id, "edge.assigned_to");
        assert_eq!(forward[0].source_entity_type_id, "node.person");
        assert_eq!(forward[0].target_entity_type_id, "node.task");
        assert_eq!(reverse, forward);
    }
}
