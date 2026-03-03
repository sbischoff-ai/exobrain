use std::collections::{BTreeMap, BTreeSet, HashMap};

use crate::domain::{
    EntityContextBlockItem, EntityContextNeighborItem, GetEntityContextResult, NeighborDirection,
    PropertyScalar, PropertyValue,
};

pub(crate) fn render_entity_context_markdown(result: &GetEntityContextResult) -> String {
    let mut markdown = String::from("# Entity context\n\n");

    markdown.push_str("## Entity core summary\n\n");
    markdown.push_str(&format!("- id: `{}`\n", result.entity.id));
    markdown.push_str(&format!("- type_id: `{}`\n", result.entity.type_id));
    markdown.push_str(&format!("- user_id: `{}`\n", result.entity.user_id));
    markdown.push_str(&format!(
        "- visibility: `{}`\n",
        render_visibility(result.entity.visibility)
    ));
    markdown.push_str(&format!(
        "- name: {}\n",
        result.entity.name.as_deref().unwrap_or("(none)")
    ));
    markdown.push_str(&format!(
        "- aliases: {}\n",
        if result.entity.aliases.is_empty() {
            "(none)".to_string()
        } else {
            result.entity.aliases.join(", ")
        }
    ));
    markdown.push_str(&format!(
        "- created_at: {}\n",
        result.entity.created_at.as_deref().unwrap_or("(none)")
    ));
    markdown.push_str(&format!(
        "- updated_at: {}\n\n",
        result.entity.updated_at.as_deref().unwrap_or("(none)")
    ));

    markdown.push_str("## entity_properties\n\n");
    render_properties_table(&mut markdown, &result.entity.properties);

    markdown.push_str("\n## Neighbors\n\n");
    if result.neighbors.is_empty() {
        markdown.push_str("(none)\n");
    } else {
        let mut neighbors = result.neighbors.iter().collect::<Vec<_>>();
        neighbors.sort_by(|a, b| {
            a.edge_type
                .cmp(&b.edge_type)
                .then_with(|| render_direction(a.direction).cmp(render_direction(b.direction)))
                .then_with(|| a.other_entity.id.cmp(&b.other_entity.id))
        });

        for (index, neighbor) in neighbors.into_iter().enumerate() {
            markdown.push_str(&format!("### Neighbor {}\n\n", index + 1));
            render_neighbor_section(&mut markdown, neighbor);
        }
    }

    markdown.push_str("\n## Blocks\n\n");
    render_block_tree(&mut markdown, &result.blocks);

    markdown
}

fn render_block_tree(markdown: &mut String, blocks: &[EntityContextBlockItem]) {
    if blocks.is_empty() {
        markdown.push_str("(none)\n");
        return;
    }

    let id_set = blocks
        .iter()
        .map(|b| b.id.as_str())
        .collect::<BTreeSet<_>>();
    let mut blocks_by_id = HashMap::new();
    let mut root_ids = Vec::new();
    let mut orphan_ids = Vec::new();
    let mut children_by_parent = BTreeMap::<String, Vec<String>>::new();

    for block in blocks {
        blocks_by_id.insert(block.id.clone(), block);
    }

    for block in blocks {
        match block.parent_block_id.as_deref() {
            None => root_ids.push(block.id.clone()),
            Some(parent_id) if !id_set.contains(parent_id) => orphan_ids.push(block.id.clone()),
            Some(parent_id) => children_by_parent
                .entry(parent_id.to_string())
                .or_default()
                .push(block.id.clone()),
        }
    }

    root_ids.sort_by(|a, b| compare_blocks(a, b, &blocks_by_id));
    orphan_ids.sort_by(|a, b| compare_blocks(a, b, &blocks_by_id));

    for child_ids in children_by_parent.values_mut() {
        child_ids.sort_by(|a, b| compare_blocks(a, b, &blocks_by_id));
    }

    if !root_ids.is_empty() {
        markdown.push_str("### Root blocks\n\n");
        for root_id in root_ids {
            render_block_node(markdown, &root_id, 4, &blocks_by_id, &children_by_parent);
        }
    }

    if !orphan_ids.is_empty() {
        markdown.push_str("### Orphan blocks\n\n");
        for orphan_id in orphan_ids {
            render_block_node(markdown, &orphan_id, 4, &blocks_by_id, &children_by_parent);
        }
    }
}

fn render_block_node(
    markdown: &mut String,
    block_id: &str,
    heading_level: usize,
    blocks_by_id: &HashMap<String, &EntityContextBlockItem>,
    children_by_parent: &BTreeMap<String, Vec<String>>,
) {
    let Some(block) = blocks_by_id.get(block_id) else {
        return;
    };

    markdown.push_str(&format!(
        "{} Block `{}`\n\n",
        "#".repeat(heading_level),
        block.id
    ));
    markdown.push_str(&format!("- type_id: `{}`\n", block.type_id));
    markdown.push_str(&format!("- block_level: `{}`\n", block.block_level));
    markdown.push_str(&format!(
        "- parent_block_id: {}\n",
        block.parent_block_id.as_deref().unwrap_or("(none)")
    ));
    markdown.push_str(&format!(
        "- created_at: {}\n",
        block.created_at.as_deref().unwrap_or("(none)")
    ));
    markdown.push_str(&format!(
        "- updated_at: {}\n\n",
        block.updated_at.as_deref().unwrap_or("(none)")
    ));

    markdown.push_str("##### block_properties\n\n");
    render_properties_table(markdown, &block.properties);

    markdown.push_str("\n##### block_neighbors\n\n");
    if block.neighbors.is_empty() {
        markdown.push_str("(none)\n");
    } else {
        for (index, neighbor) in block.neighbors.iter().enumerate() {
            markdown.push_str(&format!("- Neighbor {}\n", index + 1));
            markdown.push_str(&format!(
                "  - direction: `{}`\n",
                render_direction(neighbor.direction)
            ));
            markdown.push_str(&format!("  - edge_type: `{}`\n", neighbor.edge_type));
            markdown.push_str(&format!(
                "  - other_entity_id: `{}`\n",
                neighbor.other_entity.id
            ));
        }
    }

    markdown.push_str("\n-----\n\n");
    if let Some(text) = block.text.as_deref() {
        if text.is_empty() {
            markdown.push_str("_(empty block text)_\n");
        } else {
            markdown.push_str(text);
            markdown.push('\n');
        }
    } else {
        markdown.push_str("_(empty block text)_\n");
    }
    markdown.push_str("\n-----\n\n");

    if let Some(children) = children_by_parent.get(block_id) {
        for child_id in children {
            render_block_node(
                markdown,
                child_id,
                heading_level + 1,
                blocks_by_id,
                children_by_parent,
            );
        }
    }
}

fn render_properties_table(markdown: &mut String, properties: &[PropertyValue]) {
    markdown.push_str("| Key | Value |\n");
    markdown.push_str("| --- | --- |\n");

    let mut sorted = properties.iter().collect::<Vec<_>>();
    sorted.sort_by(|a, b| a.key.cmp(&b.key));

    for property in &sorted {
        markdown.push_str(&format!(
            "| {} | {} |\n",
            property.key,
            render_property_scalar(&property.value)
        ));
    }

    if sorted.is_empty() {
        markdown.push_str("| (none) | (none) |\n");
    }
}

fn render_neighbor_section(markdown: &mut String, neighbor: &EntityContextNeighborItem) {
    markdown.push_str(&format!(
        "- direction: `{}`\n",
        render_direction(neighbor.direction)
    ));
    markdown.push_str(&format!("- edge_type: `{}`\n", neighbor.edge_type));
    markdown.push_str(&format!(
        "- other_entity.id: `{}`\n",
        neighbor.other_entity.id
    ));
    markdown.push_str(&format!(
        "- other_entity.name: {}\n",
        neighbor.other_entity.name.as_deref().unwrap_or("(none)")
    ));
    markdown.push_str(&format!(
        "- other_entity.description: {}\n\n",
        neighbor
            .other_entity
            .description
            .as_deref()
            .unwrap_or("(none)")
    ));

    markdown.push_str("#### neighbor_properties\n\n");
    render_properties_table(markdown, &neighbor.properties);
    markdown.push('\n');
}

fn compare_blocks(
    a: &str,
    b: &str,
    blocks_by_id: &HashMap<String, &EntityContextBlockItem>,
) -> std::cmp::Ordering {
    match (blocks_by_id.get(a), blocks_by_id.get(b)) {
        (Some(a_block), Some(b_block)) => a_block
            .block_level
            .cmp(&b_block.block_level)
            .then_with(|| a_block.id.cmp(&b_block.id)),
        (Some(_), None) => std::cmp::Ordering::Less,
        (None, Some(_)) => std::cmp::Ordering::Greater,
        (None, None) => a.cmp(b),
    }
}

fn render_visibility(visibility: crate::domain::Visibility) -> &'static str {
    match visibility {
        crate::domain::Visibility::Private => "PRIVATE",
        crate::domain::Visibility::Shared => "SHARED",
    }
}

fn render_direction(direction: NeighborDirection) -> &'static str {
    match direction {
        NeighborDirection::Outgoing => "outgoing",
        NeighborDirection::Incoming => "incoming",
    }
}

fn render_property_scalar(value: &PropertyScalar) -> String {
    match value {
        PropertyScalar::String(v) => v.clone(),
        PropertyScalar::Float(v) => v.to_string(),
        PropertyScalar::Int(v) => v.to_string(),
        PropertyScalar::Bool(v) => v.to_string(),
        PropertyScalar::Datetime(v) => v.clone(),
        PropertyScalar::Json(v) => v.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::render_entity_context_markdown;
    use crate::domain::{
        EntityContextBlockItem, EntityContextEntitySnapshot, EntityContextNeighborItem,
        EntityContextOtherEntity, GetEntityContextResult, NeighborDirection, PropertyScalar,
        PropertyValue, Visibility,
    };

    #[test]
    fn renders_entity_neighbors_and_block_tree_deterministically() {
        let result = GetEntityContextResult {
            entity: EntityContextEntitySnapshot {
                id: "entity-1".to_string(),
                type_id: "node.person".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                name: Some("Alex".to_string()),
                aliases: vec!["A".to_string()],
                created_at: None,
                updated_at: None,
                properties: vec![PropertyValue {
                    key: "summary".to_string(),
                    value: PropertyScalar::String("Core summary".to_string()),
                }],
            },
            blocks: vec![
                EntityContextBlockItem {
                    id: "child-2".to_string(),
                    type_id: "node.block".to_string(),
                    block_level: 2,
                    text: Some("## Child heading".to_string()),
                    created_at: None,
                    updated_at: None,
                    properties: vec![],
                    parent_block_id: Some("root-1".to_string()),
                    neighbors: vec![],
                },
                EntityContextBlockItem {
                    id: "root-1".to_string(),
                    type_id: "node.block".to_string(),
                    block_level: 0,
                    text: Some("# Root heading".to_string()),
                    created_at: None,
                    updated_at: None,
                    properties: vec![],
                    parent_block_id: None,
                    neighbors: vec![],
                },
                EntityContextBlockItem {
                    id: "orphan-1".to_string(),
                    type_id: "node.block".to_string(),
                    block_level: 1,
                    text: Some(String::new()),
                    created_at: None,
                    updated_at: None,
                    properties: vec![],
                    parent_block_id: Some("missing-parent".to_string()),
                    neighbors: vec![],
                },
            ],
            neighbors: vec![EntityContextNeighborItem {
                direction: NeighborDirection::Outgoing,
                edge_type: "edge.knows".to_string(),
                properties: vec![],
                other_entity: EntityContextOtherEntity {
                    id: "entity-2".to_string(),
                    description: Some("friend".to_string()),
                    name: Some("Taylor".to_string()),
                },
            }],
            prompt_context_markdown: String::new(),
        };

        let markdown = render_entity_context_markdown(&result);

        assert!(markdown.starts_with("# Entity context\n\n## Entity core summary"));
        assert!(markdown.contains("## entity_properties"));
        assert!(markdown.contains("### Neighbor 1"));
        assert!(markdown.contains("### Root blocks"));
        assert!(markdown.contains("#### Block `root-1`"));
        assert!(markdown.contains("##### Block `child-2`"));
        assert!(markdown.contains("### Orphan blocks"));
        assert!(markdown.contains("#### Block `orphan-1`"));

        let root_ix = markdown.find("#### Block `root-1`").unwrap();
        let child_ix = markdown.find("##### Block `child-2`").unwrap();
        assert!(root_ix < child_ix);

        assert!(markdown.contains("# Root heading"));
        assert!(markdown.contains("## Child heading"));
        assert!(markdown.contains("_(empty block text)_"));
    }

    #[test]
    fn sorts_roots_and_children_by_block_level_then_id() {
        let result = GetEntityContextResult {
            entity: EntityContextEntitySnapshot {
                id: "entity-1".to_string(),
                type_id: "node.person".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Shared,
                name: None,
                aliases: vec![],
                created_at: None,
                updated_at: None,
                properties: vec![],
            },
            blocks: vec![
                EntityContextBlockItem {
                    id: "b-root".to_string(),
                    type_id: "node.block".to_string(),
                    block_level: 1,
                    text: None,
                    created_at: None,
                    updated_at: None,
                    properties: vec![],
                    parent_block_id: None,
                    neighbors: vec![],
                },
                EntityContextBlockItem {
                    id: "a-root".to_string(),
                    type_id: "node.block".to_string(),
                    block_level: 1,
                    text: None,
                    created_at: None,
                    updated_at: None,
                    properties: vec![],
                    parent_block_id: None,
                    neighbors: vec![],
                },
                EntityContextBlockItem {
                    id: "child-z".to_string(),
                    type_id: "node.block".to_string(),
                    block_level: 2,
                    text: None,
                    created_at: None,
                    updated_at: None,
                    properties: vec![],
                    parent_block_id: Some("a-root".to_string()),
                    neighbors: vec![],
                },
                EntityContextBlockItem {
                    id: "child-a".to_string(),
                    type_id: "node.block".to_string(),
                    block_level: 2,
                    text: None,
                    created_at: None,
                    updated_at: None,
                    properties: vec![],
                    parent_block_id: Some("a-root".to_string()),
                    neighbors: vec![],
                },
            ],
            neighbors: vec![],
            prompt_context_markdown: String::new(),
        };

        let markdown = render_entity_context_markdown(&result);

        let a_root_ix = markdown.find("#### Block `a-root`").unwrap();
        let b_root_ix = markdown.find("#### Block `b-root`").unwrap();
        assert!(a_root_ix < b_root_ix);

        let child_a_ix = markdown.find("##### Block `child-a`").unwrap();
        let child_z_ix = markdown.find("##### Block `child-z`").unwrap();
        assert!(child_a_ix < child_z_ix);
    }
}
