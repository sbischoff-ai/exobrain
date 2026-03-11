use std::{fmt, str::FromStr};

use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SchemaKind {
    Node,
    Edge,
}

impl SchemaKind {
    pub fn as_db_str(self) -> &'static str {
        match self {
            Self::Node => "node",
            Self::Edge => "edge",
        }
    }

    pub fn from_db_str(value: &str) -> Option<Self> {
        match value {
            "node" => Some(Self::Node),
            "edge" => Some(Self::Edge),
            _ => None,
        }
    }

    pub fn as_proto_str(self) -> &'static str {
        self.as_db_str()
    }

    pub fn from_proto_str(value: &str) -> Option<Self> {
        Self::from_db_str(value)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct TypeId(String);

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IdParseError {
    kind: &'static str,
    input: String,
    reason: IdParseErrorReason,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum IdParseErrorReason {
    Required,
    InvalidUuid,
}

impl IdParseError {
    fn required(kind: &'static str) -> Self {
        Self {
            kind,
            input: String::new(),
            reason: IdParseErrorReason::Required,
        }
    }

    fn invalid_uuid(kind: &'static str, input: &str) -> Self {
        Self {
            kind,
            input: input.to_string(),
            reason: IdParseErrorReason::InvalidUuid,
        }
    }
}

impl fmt::Display for IdParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.reason {
            IdParseErrorReason::Required => write!(f, "{} id is required", self.kind),
            IdParseErrorReason::InvalidUuid => {
                write!(f, "{} id '{}' must be a valid UUID", self.kind, self.input)
            }
        }
    }
}

impl std::error::Error for IdParseError {}

impl TypeId {
    pub fn parse(value: &str) -> Result<Self, IdParseError> {
        value.parse()
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl FromStr for TypeId {
    type Err = IdParseError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            return Err(IdParseError::required("type"));
        }
        Ok(Self(trimmed.to_string()))
    }
}

impl TryFrom<&str> for TypeId {
    type Error = IdParseError;

    fn try_from(value: &str) -> Result<Self, Self::Error> {
        value.parse()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct EntityId(Uuid);

impl EntityId {
    pub fn parse(value: &str) -> Result<Self, IdParseError> {
        value.parse()
    }

    pub fn as_uuid(&self) -> &Uuid {
        &self.0
    }

    pub fn into_inner(self) -> Uuid {
        self.0
    }
}

impl FromStr for EntityId {
    type Err = IdParseError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            return Err(IdParseError::required("entity"));
        }
        let parsed =
            Uuid::parse_str(trimmed).map_err(|_| IdParseError::invalid_uuid("entity", value))?;
        Ok(Self(parsed))
    }
}

impl TryFrom<&str> for EntityId {
    type Error = IdParseError;

    fn try_from(value: &str) -> Result<Self, Self::Error> {
        value.parse()
    }
}

impl fmt::Display for EntityId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct UniverseId(Uuid);

impl UniverseId {
    pub fn parse(value: &str) -> Result<Self, IdParseError> {
        value.parse()
    }

    pub fn as_uuid(&self) -> &Uuid {
        &self.0
    }

    pub fn into_inner(self) -> Uuid {
        self.0
    }
}

impl FromStr for UniverseId {
    type Err = IdParseError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        let trimmed = value.trim();
        if trimmed.is_empty() {
            return Err(IdParseError::required("universe"));
        }
        let parsed =
            Uuid::parse_str(trimmed).map_err(|_| IdParseError::invalid_uuid("universe", value))?;
        Ok(Self(parsed))
    }
}

impl TryFrom<&str> for UniverseId {
    type Error = IdParseError;

    fn try_from(value: &str) -> Result<Self, Self::Error> {
        value.parse()
    }
}

impl fmt::Display for UniverseId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

#[derive(Debug, Clone)]
pub struct SchemaType {
    pub id: String,
    pub kind: String,
    pub name: String,
    pub description: String,
    pub active: bool,
}

impl SchemaType {
    pub fn schema_kind(&self) -> Option<SchemaKind> {
        SchemaKind::from_db_str(&self.kind)
    }
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
pub struct UserInitGraphNodeIds {
    pub person_entity_id: String,
    pub assistant_entity_id: String,
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
    pub entity_described_by_edges: usize,
    pub universe_described_by_edges: usize,
}

#[derive(Debug, Clone)]
pub struct ExistingBlockContext {
    pub root_entity_id: String,
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExtractionUniverse {
    pub id: String,
    pub name: String,
    pub described_by_text: Option<String>,
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
pub struct EntityLexicalMatch {
    pub id: String,
    pub name: String,
    pub type_id: String,
    pub score: f64,
    pub matched_tokens: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct EntitySemanticHit {
    pub entity_id: String,
    pub name: String,
    pub type_id: String,
    pub score: f64,
    pub described_by_text: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct RawEntityCandidateData {
    pub lexical_matches: Vec<EntityLexicalMatch>,
    pub semantic_hits: Vec<EntitySemanticHit>,
}

#[derive(Debug, Clone)]
pub struct FindEntityCandidatesResult {
    pub candidates: Vec<EntityCandidate>,
}

#[derive(Debug, Clone)]
pub struct FindTypeCandidatesQuery {
    pub name: String,
    pub description: String,
    pub limit: Option<usize>,
}

#[derive(Debug, Clone)]
pub struct TypeCandidate {
    pub type_id: String,
    pub name: String,
    pub description: String,
    pub score: f64,
}

#[derive(Debug, Clone)]
pub struct FindTypeCandidatesResult {
    pub candidates: Vec<TypeCandidate>,
}

#[derive(Debug, Clone)]
pub struct GetEntityContextQuery {
    pub entity_id: String,
    pub user_id: String,
    pub max_block_level: u32,
}

#[derive(Debug, Clone)]
pub struct EntityContextEntitySnapshot {
    pub id: String,
    pub type_id: String,
    pub user_id: String,
    pub visibility: Visibility,
    pub name: Option<String>,
    pub aliases: Vec<String>,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
    pub properties: Vec<PropertyValue>,
}

#[derive(Debug, Clone)]
pub struct EntityContextOtherEntity {
    pub id: String,
    pub description: Option<String>,
    pub name: Option<String>,
}

#[derive(Debug, Clone)]
pub struct EntityContextBlockItem {
    pub id: String,
    pub type_id: String,
    pub block_level: u32,
    pub text: Option<String>,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
    pub properties: Vec<PropertyValue>,
    pub parent_block_id: Option<String>,
    pub neighbors: Vec<EntityContextNeighborItem>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NeighborDirection {
    Outgoing,
    Incoming,
}

#[derive(Debug, Clone)]
pub struct EntityContextNeighborItem {
    pub direction: NeighborDirection,
    pub edge_type: String,
    pub properties: Vec<PropertyValue>,
    pub other_entity: EntityContextOtherEntity,
}

#[derive(Debug, Clone)]
pub struct GetEntityContextResult {
    pub entity: EntityContextEntitySnapshot,
    pub blocks: Vec<EntityContextBlockItem>,
    pub neighbors: Vec<EntityContextNeighborItem>,
}

#[derive(Debug, Clone)]
pub struct ListEntitiesByTypeQuery {
    pub user_id: String,
    pub type_id: String,
    pub page_size: Option<u32>,
    pub page_token: Option<String>,
    pub offset: Option<u64>,
}

#[derive(Debug, Clone)]
pub struct TypedEntityListItem {
    pub id: String,
    pub name: Option<String>,
    pub updated_at: Option<String>,
    pub description: Option<String>,
}

#[derive(Debug, Clone)]
pub struct ListEntitiesByTypeResult {
    pub entities: Vec<TypedEntityListItem>,
    pub offset: u64,
    pub next_page_token: Option<String>,
}

#[cfg(test)]
mod tests {
    use std::str::FromStr;

    use super::{EntityId, SchemaKind, TypeId, UniverseId};

    #[test]
    fn schema_kind_rejects_invalid_value() {
        assert!(SchemaKind::from_db_str("invalid").is_none());
        assert!(SchemaKind::from_proto_str("invalid").is_none());
    }

    #[test]
    fn entity_id_from_str_rejects_invalid_uuid() {
        let err = EntityId::from_str("not-a-uuid").expect_err("invalid entity id should fail");
        assert_eq!(
            err.to_string(),
            "entity id 'not-a-uuid' must be a valid UUID"
        );
    }

    #[test]
    fn universe_id_from_str_rejects_empty() {
        let err = UniverseId::from_str("   ").expect_err("empty universe id should fail");
        assert_eq!(err.to_string(), "universe id is required");
    }

    #[test]
    fn type_id_from_str_rejects_empty() {
        let err = TypeId::from_str("\n").expect_err("empty type id should fail");
        assert_eq!(err.to_string(), "type id is required");
    }

    #[test]
    fn entity_and_universe_ids_display_as_uuid() {
        let raw = "11111111-1111-1111-1111-111111111111";
        let entity = EntityId::from_str(raw).expect("entity id should parse");
        let universe = UniverseId::from_str(raw).expect("universe id should parse");

        assert_eq!(entity.to_string(), raw);
        assert_eq!(universe.to_string(), raw);
    }
}
