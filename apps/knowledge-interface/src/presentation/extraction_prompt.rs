use crate::service::{ExtractionAllowedEdge, ExtractionEntityType, ExtractionUniverseContext};

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ExtractionContextStructured {
    pub entity_types: Vec<ExtractionEntityType>,
    pub universes: Vec<ExtractionUniverseContext>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum ExtractionContextView {
    Structured(ExtractionContextStructured),
    RenderedMarkdown(String),
}

impl ExtractionContextView {
    pub(crate) fn structured(
        entity_types: Vec<ExtractionEntityType>,
        universes: Vec<ExtractionUniverseContext>,
    ) -> Self {
        Self::Structured(ExtractionContextStructured {
            entity_types,
            universes,
        })
    }

    pub(crate) fn to_rendered_markdown(&self) -> Self {
        match self {
            Self::Structured(structured) => {
                Self::RenderedMarkdown(render_prompt_context_markdown(&structured.entity_types))
            }
            Self::RenderedMarkdown(markdown) => Self::RenderedMarkdown(markdown.clone()),
        }
    }
}

pub(crate) fn render_prompt_context_markdown(entity_types: &[ExtractionEntityType]) -> String {
    let mut markdown = String::from("# Extraction schema context\n\n");

    markdown.push_str("## Entity types\n\n");
    markdown.push_str("| Type ID | Name | Description | Inheritance |\n");
    markdown.push_str("| --- | --- | --- | --- |\n");
    for entity in entity_types {
        let inheritance = if entity.inheritance_chain.is_empty() {
            "-".to_string()
        } else {
            entity.inheritance_chain.join(" → ")
        };
        markdown.push_str(&format!(
            "| {} | {} | {} | {} |\n",
            entity.type_id, entity.name, entity.description, inheritance
        ));
    }

    markdown.push_str("\n## Allowed edges\n\n");
    markdown.push_str("| Entity Type | Direction | Edge Type | Edge Name | Other Entity Type | Other Entity Name | Description |\n");
    markdown.push_str("| --- | --- | --- | --- | --- | --- | --- |\n");

    let mut all_edges: Vec<(&str, &ExtractionAllowedEdge, &str)> = entity_types
        .iter()
        .flat_map(|entity| {
            entity
                .outgoing_edges
                .iter()
                .map(move |edge| (entity.type_id.as_str(), edge, "outgoing"))
                .chain(
                    entity
                        .incoming_edges
                        .iter()
                        .map(move |edge| (entity.type_id.as_str(), edge, "incoming")),
                )
        })
        .collect();

    all_edges.sort_by(
        |(a_type, a_edge, a_direction), (b_type, b_edge, b_direction)| {
            a_type
                .cmp(b_type)
                .then_with(|| a_edge.edge_type_id.cmp(&b_edge.edge_type_id))
                .then_with(|| {
                    a_edge
                        .other_entity_type_id
                        .cmp(&b_edge.other_entity_type_id)
                })
                .then_with(|| a_direction.cmp(b_direction))
                .then_with(|| a_edge.edge_name.cmp(&b_edge.edge_name))
        },
    );

    for (entity_type, edge, direction) in all_edges {
        markdown.push_str(&format!(
            "| {} | {} | {} | {} | {} | {} | {} |\n",
            entity_type,
            direction,
            edge.edge_type_id,
            edge.edge_name,
            edge.other_entity_type_id,
            edge.other_entity_type_name,
            edge.edge_description,
        ));
    }

    markdown
}

#[cfg(test)]
mod tests {
    use super::render_prompt_context_markdown;
    use crate::service::{ExtractionAllowedEdge, ExtractionEntityType};

    #[test]
    fn sorts_edges_stably_by_markdown_key() {
        let markdown = render_prompt_context_markdown(&[ExtractionEntityType {
            type_id: "node.person".to_string(),
            name: "Person".to_string(),
            description: "A person".to_string(),
            inheritance_chain: vec!["node.entity".to_string(), "node.person".to_string()],
            outgoing_edges: vec![ExtractionAllowedEdge {
                edge_type_id: "edge.mentions".to_string(),
                edge_name: "Mentions".to_string(),
                edge_description: "Mentions another entity".to_string(),
                other_entity_type_id: "node.project".to_string(),
                other_entity_type_name: "Project".to_string(),
                min_cardinality: None,
                max_cardinality: None,
            }],
            incoming_edges: vec![
                ExtractionAllowedEdge {
                    edge_type_id: "edge.works_on".to_string(),
                    edge_name: "Works On".to_string(),
                    edge_description: "Connected from project".to_string(),
                    other_entity_type_id: "node.project".to_string(),
                    other_entity_type_name: "Project".to_string(),
                    min_cardinality: None,
                    max_cardinality: None,
                },
                ExtractionAllowedEdge {
                    edge_type_id: "edge.mentions".to_string(),
                    edge_name: "Mentions".to_string(),
                    edge_description: "Mentioned by project".to_string(),
                    other_entity_type_id: "node.project".to_string(),
                    other_entity_type_name: "Project".to_string(),
                    min_cardinality: None,
                    max_cardinality: None,
                },
            ],
        }]);

        let mentions_incoming = "| node.person | incoming | edge.mentions | Mentions | node.project | Project | Mentioned by project |";
        let mentions_outgoing = "| node.person | outgoing | edge.mentions | Mentions | node.project | Project | Mentions another entity |";
        let works_on_incoming = "| node.person | incoming | edge.works_on | Works On | node.project | Project | Connected from project |";

        let mentions_incoming_ix = markdown.find(mentions_incoming).unwrap();
        let mentions_outgoing_ix = markdown.find(mentions_outgoing).unwrap();
        let works_on_incoming_ix = markdown.find(works_on_incoming).unwrap();

        assert!(mentions_incoming_ix < mentions_outgoing_ix);
        assert!(mentions_outgoing_ix < works_on_incoming_ix);
    }

    #[test]
    fn renders_expected_markdown_shape() {
        let markdown = render_prompt_context_markdown(&[ExtractionEntityType {
            type_id: "node.person".to_string(),
            name: "Person".to_string(),
            description: "A person".to_string(),
            inheritance_chain: vec!["node.entity".to_string(), "node.person".to_string()],
            outgoing_edges: vec![],
            incoming_edges: vec![],
        }]);

        assert!(markdown.starts_with("# Extraction schema context\n\n## Entity types\n\n"));
        assert!(markdown.contains("| Type ID | Name | Description | Inheritance |"));
        assert!(
            markdown.contains("| node.person | Person | A person | node.entity → node.person |")
        );
        assert!(markdown.contains("\n## Allowed edges\n\n"));
        assert!(markdown.contains("| Entity Type | Direction | Edge Type | Edge Name | Other Entity Type | Other Entity Name | Description |"));
    }
}
