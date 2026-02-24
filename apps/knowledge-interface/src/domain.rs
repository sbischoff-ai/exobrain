#![allow(dead_code)]

#[derive(Debug, Clone)]
pub struct SchemaType {
    pub id: String,
    pub kind: String,
    pub name: String,
    pub description: String,
    pub active: bool,
}

#[derive(Debug, Clone)]
pub struct TypeInheritance {
    pub child_type_id: String,
    pub parent_type_id: String,
    pub description: String,
    pub active: bool,
}

#[derive(Debug, Clone)]
pub struct TypeProperty {
    pub owner_type_id: String,
    pub prop_name: String,
    pub value_type: String,
    pub required: bool,
    pub readable: bool,
    pub writable: bool,
    pub active: bool,
    pub description: String,
}

#[derive(Debug, Clone)]
pub struct EdgeEndpointRule {
    pub edge_type_id: String,
    pub from_node_type_id: String,
    pub to_node_type_id: String,
    pub active: bool,
    pub description: String,
}

#[derive(Debug, Clone)]
pub struct TimeWindow {
    pub start: Option<String>,
    pub end: Option<String>,
    pub due: Option<String>,
}

#[derive(Debug, Clone)]
pub struct EntityNode {
    pub id: String,
    pub name: String,
    pub labels: Vec<String>,
    pub universe_id: String,
    pub time_window: Option<TimeWindow>,
}

#[derive(Debug, Clone)]
pub struct BlockNode {
    pub id: String,
    pub text: String,
    pub labels: Vec<String>,
    pub root_entity_id: String,
    pub confidence: Option<f32>,
    pub status: Option<String>,
}

#[derive(Debug, Clone)]
pub struct GraphEdge {
    pub from_id: String,
    pub to_id: String,
    pub edge_type: String,
    pub confidence: Option<f32>,
    pub status: Option<String>,
    pub context: Option<String>,
}

#[derive(Debug, Clone)]
pub struct GraphDelta {
    pub universe_id: String,
    pub entities: Vec<EntityNode>,
    pub blocks: Vec<BlockNode>,
    pub edges: Vec<GraphEdge>,
}

#[derive(Debug, Clone)]
pub struct EmbeddedBlock {
    pub block: BlockNode,
    pub universe_id: String,
    pub vector: Vec<f32>,
    pub entity_ids: Vec<String>,
}
