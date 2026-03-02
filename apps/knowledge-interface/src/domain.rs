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
pub struct UpsertSchemaTypePropertyInput {
    pub prop_name: String,
    pub value_type: String,
    pub required: bool,
    pub readable: bool,
    pub writable: bool,
    pub active: bool,
    pub description: String,
}

#[derive(Debug, Clone)]
pub struct UpsertSchemaTypeCommand {
    pub schema_type: SchemaType,
    pub parent_type_id: Option<String>,
    pub properties: Vec<UpsertSchemaTypePropertyInput>,
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
pub enum PropertyScalar {
    String(String),
    Float(f64),
    Int(i64),
    Bool(bool),
    Datetime(String),
    Json(String),
}

#[derive(Debug, Clone)]
pub struct PropertyValue {
    pub key: String,
    pub value: PropertyScalar,
}

#[derive(Debug, Clone)]
pub struct EntityNode {
    pub id: String,
    pub type_id: String,
    pub universe_id: Option<String>,
    pub user_id: String,
    pub visibility: Visibility,
    pub properties: Vec<PropertyValue>,
    pub resolved_labels: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct UniverseNode {
    pub id: String,
    pub name: String,
    pub user_id: String,
    pub visibility: Visibility,
}

#[derive(Debug, Clone)]
pub struct BlockNode {
    pub id: String,
    pub type_id: String,
    pub user_id: String,
    pub visibility: Visibility,
    pub properties: Vec<PropertyValue>,
    pub resolved_labels: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct GraphEdge {
    pub from_id: String,
    pub to_id: String,
    pub edge_type: String,
    pub user_id: String,
    pub visibility: Visibility,
    pub properties: Vec<PropertyValue>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Visibility {
    Private,
    Shared,
}

#[derive(Debug, Clone)]
pub struct GraphDelta {
    pub universes: Vec<UniverseNode>,
    pub entities: Vec<EntityNode>,
    pub blocks: Vec<BlockNode>,
    pub edges: Vec<GraphEdge>,
}

#[derive(Debug, Clone)]
pub struct EmbeddedBlock {
    pub block: BlockNode,
    pub universe_id: String,
    pub root_entity_id: String,
    pub user_id: String,
    pub visibility: Visibility,
    pub vector: Vec<f32>,
    pub block_level: i64,
    pub text: String,
}

#[derive(Debug, Clone, Default)]
pub struct NodeRelationshipCounts {
    pub total: usize,
    pub entity_is_part_of: usize,
    pub block_parent_edges: usize,
}

#[derive(Debug, Clone)]
pub struct ExistingBlockContext {
    pub root_entity_id: String,
    pub universe_id: String,
    pub block_level: i64,
}

#[derive(Debug, Clone)]
pub struct SchemaNodeTypeHydrated {
    pub schema_type: SchemaType,
    pub properties: Vec<TypeProperty>,
    pub parents: Vec<TypeInheritance>,
}

#[derive(Debug, Clone)]
pub struct SchemaEdgeTypeHydrated {
    pub schema_type: SchemaType,
    pub properties: Vec<TypeProperty>,
    pub rules: Vec<EdgeEndpointRule>,
}

#[derive(Debug, Clone)]
pub struct FullSchema {
    pub node_types: Vec<SchemaNodeTypeHydrated>,
    pub edge_types: Vec<SchemaEdgeTypeHydrated>,
}

#[derive(Debug, Clone)]
pub struct FindEntityCandidatesQuery {
    pub names: Vec<String>,
    pub potential_type_ids: Vec<String>,
    pub short_description: Option<String>,
    pub user_id: String,
    pub limit: Option<usize>,
}

#[derive(Debug, Clone)]
pub struct EntityCandidate {
    pub id: String,
    pub name: String,
    pub described_by_text: Option<String>,
    pub score: f64,
    pub type_id: String,
    pub matched_tokens: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct FindEntityCandidatesResult {
    pub candidates: Vec<EntityCandidate>,
}
