use super::*;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use async_trait::async_trait;

use crate::application::graph_resolution::{block_levels_for_blocks, root_entity_ids_for_blocks};
use crate::application::pagination::{
    LIST_ENTITIES_BY_TYPE_DEFAULT_PAGE_SIZE, LIST_ENTITIES_BY_TYPE_MAX_PAGE_SIZE,
};

use crate::{
    domain::{
        BlockNode, EdgeEndpointRule, EntityLexicalMatch, EntityNode, EntitySemanticHit,
        ExistingBlockContext, ExtractionUniverse, FindEntityCandidatesQuery, GraphEdge,
        NodeRelationshipCounts, PropertyValue, RawEntityCandidateData, TypeInheritance,
        TypeProperty, UpsertSchemaTypePropertyInput, UserInitGraphNodeIds, Visibility,
    },
    ports::{Embedder, GraphRepository, SchemaRepository, TypeVectorRepository},
};

fn build_extraction_entity_types_from_schema(
    schema: FullSchema,
    options: ExtractionSchemaOptions,
) -> Vec<ExtractionEntityType> {
    let FullSchema {
        node_types: hydrated_node_types,
        edge_types: hydrated_edge_types,
    } = schema;

    let node_types = hydrated_node_types
        .iter()
        .map(|node| node.schema_type.clone())
        .collect();
    let edge_types = hydrated_edge_types
        .iter()
        .map(|edge| edge.schema_type.clone())
        .collect();
    let inheritance = hydrated_node_types
        .into_iter()
        .flat_map(|node| node.parents)
        .collect();
    let edge_rules = hydrated_edge_types
        .into_iter()
        .flat_map(|edge| edge.rules)
        .collect();

    build_extraction_entity_types_from_input(
        ExtractionSchemaBuildInput {
            node_types,
            edge_types,
            inheritance,
            edge_rules,
        },
        options,
    )
}

struct FakeSchemaRepo {
    types: Mutex<HashMap<String, SchemaType>>,
    parents: Mutex<HashMap<String, String>>,
    properties: Mutex<Vec<TypeProperty>>,
}

impl FakeSchemaRepo {
    fn new() -> Self {
        let mut types = HashMap::new();
        types.insert(
            "node.entity".to_string(),
            SchemaType {
                id: "node.entity".to_string(),
                kind: "node".to_string(),
                name: "Entity".to_string(),
                description: "".to_string(),
                active: true,
            },
        );
        Self {
            types: Mutex::new(types),
            parents: Mutex::new(HashMap::new()),
            properties: Mutex::new(default_schema_properties()),
        }
    }
}

fn default_schema_properties() -> Vec<TypeProperty> {
    vec![
        TypeProperty {
            owner_type_id: "node.entity".to_string(),
            prop_name: "name".to_string(),
            value_type: "string".to_string(),
            required: true,
            readable: true,
            writable: true,
            active: true,
            description: String::new(),
        },
        TypeProperty {
            owner_type_id: "node.entity".to_string(),
            prop_name: "aliases".to_string(),
            value_type: "json".to_string(),
            required: false,
            readable: true,
            writable: true,
            active: true,
            description: String::new(),
        },
        TypeProperty {
            owner_type_id: "node.block".to_string(),
            prop_name: "text".to_string(),
            value_type: "string".to_string(),
            required: true,
            readable: true,
            writable: true,
            active: true,
            description: String::new(),
        },
        TypeProperty {
            owner_type_id: "edge".to_string(),
            prop_name: "confidence".to_string(),
            value_type: "float".to_string(),
            required: true,
            readable: true,
            writable: true,
            active: true,
            description: String::new(),
        },
        TypeProperty {
            owner_type_id: "edge".to_string(),
            prop_name: "status".to_string(),
            value_type: "string".to_string(),
            required: true,
            readable: true,
            writable: true,
            active: true,
            description: String::new(),
        },
        TypeProperty {
            owner_type_id: "edge".to_string(),
            prop_name: "provenance_hint".to_string(),
            value_type: "string".to_string(),
            required: true,
            readable: true,
            writable: true,
            active: true,
            description: String::new(),
        },
    ]
}

#[async_trait]
impl SchemaRepository for FakeSchemaRepo {
    async fn get_by_kind(&self, kind: SchemaKind) -> Result<Vec<SchemaType>> {
        let values = match kind {
            SchemaKind::Node => vec![
                SchemaType {
                    id: "node.entity".to_string(),
                    kind: "node".to_string(),
                    name: "Entity".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.person".to_string(),
                    kind: "node".to_string(),
                    name: "Person".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.object".to_string(),
                    kind: "node".to_string(),
                    name: "Object".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.concept".to_string(),
                    kind: "node".to_string(),
                    name: "Concept".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.event".to_string(),
                    kind: "node".to_string(),
                    name: "Event".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.task".to_string(),
                    kind: "node".to_string(),
                    name: "Task".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.message".to_string(),
                    kind: "node".to_string(),
                    name: "Message".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.chat_message".to_string(),
                    kind: "node".to_string(),
                    name: "Chat Message".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.ai_agent".to_string(),
                    kind: "node".to_string(),
                    name: "AI Agent".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.place".to_string(),
                    kind: "node".to_string(),
                    name: "Place".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.block".to_string(),
                    kind: "node".to_string(),
                    name: "Block".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "node.universe".to_string(),
                    kind: "node".to_string(),
                    name: "Universe".to_string(),
                    description: String::new(),
                    active: true,
                },
            ],
            SchemaKind::Edge => vec![
                SchemaType {
                    id: "edge.related_to".to_string(),
                    kind: "edge".to_string(),
                    name: "RELATED_TO".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "edge.described_by".to_string(),
                    kind: "edge".to_string(),
                    name: "DESCRIBED_BY".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "edge.is_part_of".to_string(),
                    kind: "edge".to_string(),
                    name: "IS_PART_OF".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "edge.located_at".to_string(),
                    kind: "edge".to_string(),
                    name: "LOCATED_AT".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "edge.sent_to".to_string(),
                    kind: "edge".to_string(),
                    name: "SENT_TO".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "edge.sent_by".to_string(),
                    kind: "edge".to_string(),
                    name: "SENT_BY".to_string(),
                    description: String::new(),
                    active: true,
                },
                SchemaType {
                    id: "edge.contradicts".to_string(),
                    kind: "edge".to_string(),
                    name: "CONTRADICTS".to_string(),
                    description: String::new(),
                    active: true,
                },
            ],
        };
        Ok(values)
    }

    async fn upsert(&self, schema_type: &SchemaType) -> Result<SchemaType> {
        self.types
            .lock()
            .expect("lock")
            .insert(schema_type.id.clone(), schema_type.clone());
        Ok(schema_type.clone())
    }

    async fn get_type_inheritance(&self) -> Result<Vec<TypeInheritance>> {
        Ok(vec![
            TypeInheritance {
                child_type_id: "node.person".to_string(),
                parent_type_id: "node.entity".to_string(),
                description: String::new(),
                active: true,
            },
            TypeInheritance {
                child_type_id: "node.object".to_string(),
                parent_type_id: "node.entity".to_string(),
                description: String::new(),
                active: true,
            },
            TypeInheritance {
                child_type_id: "node.concept".to_string(),
                parent_type_id: "node.entity".to_string(),
                description: String::new(),
                active: true,
            },
            TypeInheritance {
                child_type_id: "node.event".to_string(),
                parent_type_id: "node.entity".to_string(),
                description: String::new(),
                active: true,
            },
            TypeInheritance {
                child_type_id: "node.task".to_string(),
                parent_type_id: "node.event".to_string(),
                description: String::new(),
                active: true,
            },
            TypeInheritance {
                child_type_id: "node.message".to_string(),
                parent_type_id: "node.event".to_string(),
                description: String::new(),
                active: true,
            },
            TypeInheritance {
                child_type_id: "node.chat_message".to_string(),
                parent_type_id: "node.message".to_string(),
                description: String::new(),
                active: true,
            },
            TypeInheritance {
                child_type_id: "node.ai_agent".to_string(),
                parent_type_id: "node.person".to_string(),
                description: String::new(),
                active: true,
            },
            TypeInheritance {
                child_type_id: "node.place".to_string(),
                parent_type_id: "node.entity".to_string(),
                description: String::new(),
                active: true,
            },
        ])
    }

    async fn get_all_properties(&self) -> Result<Vec<TypeProperty>> {
        Ok(self.properties.lock().expect("lock").clone())
    }

    async fn get_edge_endpoint_rules(&self) -> Result<Vec<EdgeEndpointRule>> {
        Ok(vec![
            EdgeEndpointRule {
                edge_type_id: "edge.related_to".to_string(),
                from_node_type_id: "node.entity".to_string(),
                to_node_type_id: "node.entity".to_string(),
                active: true,
                description: String::new(),
            },
            EdgeEndpointRule {
                edge_type_id: "edge.described_by".to_string(),
                from_node_type_id: "node.entity".to_string(),
                to_node_type_id: "node.block".to_string(),
                active: true,
                description: String::new(),
            },
            EdgeEndpointRule {
                edge_type_id: "edge.described_by".to_string(),
                from_node_type_id: "node.universe".to_string(),
                to_node_type_id: "node.block".to_string(),
                active: true,
                description: String::new(),
            },
            EdgeEndpointRule {
                edge_type_id: "edge.is_part_of".to_string(),
                from_node_type_id: "node.entity".to_string(),
                to_node_type_id: "node.universe".to_string(),
                active: true,
                description: String::new(),
            },
            EdgeEndpointRule {
                edge_type_id: "edge.located_at".to_string(),
                from_node_type_id: "node.event".to_string(),
                to_node_type_id: "node.place".to_string(),
                active: true,
                description: String::new(),
            },
            EdgeEndpointRule {
                edge_type_id: "edge.sent_to".to_string(),
                from_node_type_id: "node.message".to_string(),
                to_node_type_id: "node.person".to_string(),
                active: true,
                description: String::new(),
            },
            EdgeEndpointRule {
                edge_type_id: "edge.sent_by".to_string(),
                from_node_type_id: "node.message".to_string(),
                to_node_type_id: "node.person".to_string(),
                active: true,
                description: String::new(),
            },
            EdgeEndpointRule {
                edge_type_id: "edge.contradicts".to_string(),
                from_node_type_id: "node.block".to_string(),
                to_node_type_id: "node.block".to_string(),
                active: true,
                description: String::new(),
            },
        ])
    }

    async fn get_schema_type(&self, id: &str) -> Result<Option<SchemaType>> {
        Ok(self.types.lock().expect("lock").get(id).cloned())
    }

    async fn get_parent_for_child(&self, child_type_id: &str) -> Result<Option<String>> {
        Ok(self
            .parents
            .lock()
            .expect("lock")
            .get(child_type_id)
            .cloned())
    }

    async fn is_descendant_of_entity(&self, node_type_id: &str) -> Result<bool> {
        if node_type_id == "node.entity" {
            return Ok(true);
        }
        let parents = self.parents.lock().expect("lock");
        Ok(matches!(parents.get(node_type_id), Some(v) if v == "node.entity"))
    }

    async fn upsert_inheritance(
        &self,
        child_type_id: &str,
        parent_type_id: &str,
        _description: &str,
    ) -> Result<()> {
        self.parents
            .lock()
            .expect("lock")
            .insert(child_type_id.to_string(), parent_type_id.to_string());
        Ok(())
    }

    async fn upsert_type_property(
        &self,
        _owner_type_id: &str,
        _property: &UpsertSchemaTypePropertyInput,
    ) -> Result<()> {
        Ok(())
    }

    async fn delete_schema_type(&self, id: &str) -> Result<()> {
        self.types.lock().expect("lock").remove(id);
        self.parents.lock().expect("lock").remove(id);
        Ok(())
    }
}

struct FakeGraphRepository {
    root_exists: bool,
}

#[async_trait]
impl GraphRepository for FakeGraphRepository {
    async fn apply_delta_with_blocks(
        &self,
        _delta: &GraphDelta,
        _blocks: &[EmbeddedBlock],
    ) -> Result<()> {
        Ok(())
    }

    async fn common_root_graph_exists(&self) -> Result<bool> {
        Ok(self.root_exists)
    }

    async fn user_graph_needs_initialization(&self, _user_id: &str) -> Result<bool> {
        Ok(true)
    }

    async fn mark_user_graph_initialized(
        &self,
        _user_id: &str,
        _node_ids: &UserInitGraphNodeIds,
    ) -> Result<()> {
        Ok(())
    }

    async fn get_user_init_graph_node_ids(
        &self,
        _user_id: &str,
    ) -> Result<Option<UserInitGraphNodeIds>> {
        Ok(None)
    }

    async fn update_person_name(&self, _person_entity_id: &str, _user_name: &str) -> Result<()> {
        Ok(())
    }

    async fn get_existing_block_context(
        &self,
        _block_id: &str,
        _user_id: &str,
        _visibility: Visibility,
    ) -> Result<Option<ExistingBlockContext>> {
        Ok(None)
    }

    async fn get_node_relationship_counts(&self, _node_id: &str) -> Result<NodeRelationshipCounts> {
        Ok(NodeRelationshipCounts::default())
    }

    async fn find_entity_candidates(
        &self,
        _query: &FindEntityCandidatesQuery,
        _query_vector: Option<&[f32]>,
    ) -> Result<RawEntityCandidateData> {
        Ok(RawEntityCandidateData::default())
    }

    async fn list_entities_by_type(
        &self,
        _query: &ListEntitiesByTypeQuery,
    ) -> Result<ListEntitiesByTypeResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_entity_context(
        &self,
        _query: &GetEntityContextQuery,
    ) -> Result<GetEntityContextResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_extraction_universes(&self, _user_id: &str) -> Result<Vec<ExtractionUniverse>> {
        Ok(Vec::new())
    }
}

struct CapturingTypeVectorRepository {
    seen: Arc<Mutex<Vec<(SchemaType, Vec<f32>)>>>,
    fail_for_type_id: Option<String>,
}

#[async_trait]
impl TypeVectorRepository for CapturingTypeVectorRepository {
    async fn upsert_schema_type_vector(
        &self,
        schema_type: &SchemaType,
        vector: &[f32],
    ) -> Result<()> {
        if self
            .fail_for_type_id
            .as_ref()
            .is_some_and(|id| id == &schema_type.id)
        {
            return Err(anyhow!(
                "forced type-vector upsert failure for {}",
                schema_type.id
            ));
        }

        self.seen
            .lock()
            .expect("type vector lock should not be poisoned")
            .push((schema_type.clone(), vector.to_vec()));
        Ok(())
    }

    async fn search_node_type_vectors(
        &self,
        _query_vector: &[f32],
        _limit: u64,
    ) -> Result<Vec<crate::domain::TypeScoredCandidate>> {
        Ok(Vec::new())
    }

    async fn search_edge_type_vectors(
        &self,
        _query_vector: &[f32],
        _limit: u64,
    ) -> Result<Vec<crate::domain::TypeScoredCandidate>> {
        Ok(Vec::new())
    }
}

struct FakeEmbedder;

#[async_trait]
impl Embedder for FakeEmbedder {
    async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        Ok(texts.iter().map(|_| vec![0.1_f32, 0.2_f32]).collect())
    }
}

struct CapturingGraphRepository {
    seen: Arc<Mutex<Vec<EmbeddedBlock>>>,
    root_exists: bool,
    user_graph_initialized: bool,
    marked_user_ids: Arc<Mutex<Vec<String>>>,
    block_contexts: HashMap<String, ExistingBlockContext>,
}

#[async_trait]
impl GraphRepository for CapturingGraphRepository {
    async fn apply_delta_with_blocks(
        &self,
        _delta: &GraphDelta,
        blocks: &[EmbeddedBlock],
    ) -> Result<()> {
        let mut guard = self.seen.lock().expect("lock should be available");
        guard.extend(blocks.to_vec());
        Ok(())
    }

    async fn common_root_graph_exists(&self) -> Result<bool> {
        Ok(self.root_exists)
    }

    async fn user_graph_needs_initialization(&self, _user_id: &str) -> Result<bool> {
        Ok(!self.user_graph_initialized)
    }

    async fn mark_user_graph_initialized(
        &self,
        user_id: &str,
        node_ids: &UserInitGraphNodeIds,
    ) -> Result<()> {
        self.marked_user_ids
            .lock()
            .expect("lock should be available")
            .push(format!(
                "{}:{}:{}",
                user_id, node_ids.person_entity_id, node_ids.assistant_entity_id
            ));
        Ok(())
    }

    async fn get_user_init_graph_node_ids(
        &self,
        _user_id: &str,
    ) -> Result<Option<UserInitGraphNodeIds>> {
        Ok(Some(UserInitGraphNodeIds {
            person_entity_id: uuid::Uuid::new_v5(&uuid::Uuid::NAMESPACE_OID, b"person:user-1")
                .to_string(),
            assistant_entity_id: uuid::Uuid::new_v5(
                &uuid::Uuid::NAMESPACE_OID,
                b"assistant:user-1",
            )
            .to_string(),
        }))
    }

    async fn update_person_name(&self, _person_entity_id: &str, _user_name: &str) -> Result<()> {
        Ok(())
    }

    async fn get_existing_block_context(
        &self,
        block_id: &str,
        _user_id: &str,
        _visibility: Visibility,
    ) -> Result<Option<ExistingBlockContext>> {
        Ok(self.block_contexts.get(block_id).cloned())
    }

    async fn get_node_relationship_counts(&self, _node_id: &str) -> Result<NodeRelationshipCounts> {
        Ok(NodeRelationshipCounts::default())
    }

    async fn find_entity_candidates(
        &self,
        _query: &FindEntityCandidatesQuery,
        _query_vector: Option<&[f32]>,
    ) -> Result<RawEntityCandidateData> {
        Ok(RawEntityCandidateData::default())
    }

    async fn list_entities_by_type(
        &self,
        _query: &ListEntitiesByTypeQuery,
    ) -> Result<ListEntitiesByTypeResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_entity_context(
        &self,
        _query: &GetEntityContextQuery,
    ) -> Result<GetEntityContextResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_extraction_universes(&self, _user_id: &str) -> Result<Vec<ExtractionUniverse>> {
        Ok(Vec::new())
    }
}

struct CountingGraphRepository {
    counts: HashMap<String, NodeRelationshipCounts>,
    block_contexts: HashMap<String, ExistingBlockContext>,
}

#[async_trait]
impl GraphRepository for CountingGraphRepository {
    async fn apply_delta_with_blocks(
        &self,
        _delta: &GraphDelta,
        _blocks: &[EmbeddedBlock],
    ) -> Result<()> {
        Ok(())
    }

    async fn common_root_graph_exists(&self) -> Result<bool> {
        Ok(false)
    }

    async fn user_graph_needs_initialization(&self, _user_id: &str) -> Result<bool> {
        Ok(true)
    }

    async fn mark_user_graph_initialized(
        &self,
        _user_id: &str,
        _node_ids: &UserInitGraphNodeIds,
    ) -> Result<()> {
        Ok(())
    }

    async fn get_user_init_graph_node_ids(
        &self,
        _user_id: &str,
    ) -> Result<Option<UserInitGraphNodeIds>> {
        Ok(None)
    }

    async fn update_person_name(&self, _person_entity_id: &str, _user_name: &str) -> Result<()> {
        Ok(())
    }

    async fn get_existing_block_context(
        &self,
        block_id: &str,
        _user_id: &str,
        _visibility: Visibility,
    ) -> Result<Option<ExistingBlockContext>> {
        Ok(self.block_contexts.get(block_id).cloned())
    }

    async fn get_node_relationship_counts(&self, node_id: &str) -> Result<NodeRelationshipCounts> {
        Ok(self.counts.get(node_id).cloned().unwrap_or_default())
    }

    async fn find_entity_candidates(
        &self,
        _query: &FindEntityCandidatesQuery,
        _query_vector: Option<&[f32]>,
    ) -> Result<RawEntityCandidateData> {
        Ok(RawEntityCandidateData::default())
    }

    async fn list_entities_by_type(
        &self,
        _query: &ListEntitiesByTypeQuery,
    ) -> Result<ListEntitiesByTypeResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_entity_context(
        &self,
        _query: &GetEntityContextQuery,
    ) -> Result<GetEntityContextResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_extraction_universes(&self, _user_id: &str) -> Result<Vec<ExtractionUniverse>> {
        Ok(Vec::new())
    }
}

struct TrackingInitGraphRepository {
    initialized: Arc<Mutex<HashSet<String>>>,
    call_order: Arc<Mutex<Vec<String>>>,
}

#[async_trait]
impl GraphRepository for TrackingInitGraphRepository {
    async fn apply_delta_with_blocks(
        &self,
        delta: &GraphDelta,
        _blocks: &[EmbeddedBlock],
    ) -> Result<()> {
        let marker = if delta
            .entities
            .iter()
            .any(|entity| entity.type_id == "node.ai_agent")
        {
            "init"
        } else {
            "main"
        };
        self.call_order
            .lock()
            .expect("lock should be available")
            .push(marker.to_string());
        Ok(())
    }

    async fn common_root_graph_exists(&self) -> Result<bool> {
        Ok(true)
    }

    async fn user_graph_needs_initialization(&self, user_id: &str) -> Result<bool> {
        Ok(!self
            .initialized
            .lock()
            .expect("lock should be available")
            .contains(user_id))
    }

    async fn mark_user_graph_initialized(
        &self,
        user_id: &str,
        _node_ids: &UserInitGraphNodeIds,
    ) -> Result<()> {
        self.initialized
            .lock()
            .expect("lock should be available")
            .insert(user_id.to_string());
        Ok(())
    }

    async fn get_user_init_graph_node_ids(
        &self,
        _user_id: &str,
    ) -> Result<Option<UserInitGraphNodeIds>> {
        Ok(None)
    }

    async fn update_person_name(&self, _person_entity_id: &str, _user_name: &str) -> Result<()> {
        Ok(())
    }

    async fn get_existing_block_context(
        &self,
        _block_id: &str,
        _user_id: &str,
        _visibility: Visibility,
    ) -> Result<Option<ExistingBlockContext>> {
        Ok(None)
    }

    async fn get_node_relationship_counts(&self, _node_id: &str) -> Result<NodeRelationshipCounts> {
        Ok(NodeRelationshipCounts::default())
    }

    async fn find_entity_candidates(
        &self,
        _query: &FindEntityCandidatesQuery,
        _query_vector: Option<&[f32]>,
    ) -> Result<RawEntityCandidateData> {
        Ok(RawEntityCandidateData::default())
    }

    async fn list_entities_by_type(
        &self,
        _query: &ListEntitiesByTypeQuery,
    ) -> Result<ListEntitiesByTypeResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_entity_context(
        &self,
        _query: &GetEntityContextQuery,
    ) -> Result<GetEntityContextResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_extraction_universes(&self, _user_id: &str) -> Result<Vec<ExtractionUniverse>> {
        Ok(Vec::new())
    }
}

#[tokio::test]
async fn accepts_block_text_update_without_parent_edges_when_graph_state_is_valid() {
    let block_id = "550e8400-e29b-41d4-a716-4466554400be".to_string();
    let mut counts = HashMap::new();
    counts.insert(
        block_id.clone(),
        NodeRelationshipCounts {
            total: 1,
            entity_is_part_of: 0,
            block_parent_edges: 1,
            entity_described_by_edges: 0,
            universe_described_by_edges: 0,
        },
    );
    let mut block_contexts = HashMap::new();
    block_contexts.insert(
        block_id.clone(),
        ExistingBlockContext {
            root_entity_id: "550e8400-e29b-41d4-a716-4466554400aa".to_string(),
            block_level: 0,
        },
    );

    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CountingGraphRepository {
            counts,
            block_contexts,
        }),
        Arc::new(FakeEmbedder),
    );

    app.upsert_graph_delta(GraphDelta {
        universes: vec![],
        entities: vec![],
        blocks: vec![BlockNode {
            id: block_id,
            type_id: "node.block".to_string(),
            user_id: "user-1".to_string(),
            visibility: Visibility::Private,
            properties: vec![PropertyValue {
                key: "text".to_string(),
                value: PropertyScalar::String("updated block text".to_string()),
            }],
            resolved_labels: vec![],
        }],
        edges: vec![],
    })
    .await
    .expect("existing graph relationships should satisfy block parent validation");
}

#[tokio::test]
async fn rejects_block_without_parent_edge_when_target_graph_state_is_invalid() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CountingGraphRepository {
            counts: HashMap::new(),
            block_contexts: HashMap::new(),
        }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .upsert_graph_delta(GraphDelta {
            universes: vec![],
            entities: vec![],
            blocks: vec![BlockNode {
                id: "550e8400-e29b-41d4-a716-4466554400bf".to_string(),
                type_id: "node.block".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("new block".to_string()),
                }],
                resolved_labels: vec![],
            }],
            edges: vec![],
        })
        .await
        .expect_err("block without existing/payload parent edge should fail");

    assert!(err
        .to_string()
        .contains("must have exactly one incoming DESCRIBED_BY or SUMMARIZES edge"));
}

#[tokio::test]
async fn rejects_entity_with_multiple_described_by_edges() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .upsert_graph_delta(GraphDelta {
            universes: vec![],
            entities: vec![EntityNode {
                id: "550e8400-e29b-41d4-a716-446655440010".to_string(),
                type_id: "node.person".to_string(),
                universe_id: None,
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Entity".to_string()),
                }],
                resolved_labels: vec![],
            }],
            blocks: vec![
                BlockNode {
                    id: "550e8400-e29b-41d4-a716-446655440011".to_string(),
                    type_id: "node.block".to_string(),
                    user_id: "exobrain".to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![PropertyValue {
                        key: "text".to_string(),
                        value: PropertyScalar::String("root a".to_string()),
                    }],
                    resolved_labels: vec![],
                },
                BlockNode {
                    id: "550e8400-e29b-41d4-a716-446655440012".to_string(),
                    type_id: "node.block".to_string(),
                    user_id: "exobrain".to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![PropertyValue {
                        key: "text".to_string(),
                        value: PropertyScalar::String("root b".to_string()),
                    }],
                    resolved_labels: vec![],
                },
            ],
            edges: vec![
                GraphEdge {
                    from_id: "550e8400-e29b-41d4-a716-446655440010".to_string(),
                    to_id: "550e8400-e29b-41d4-a716-446655440011".to_string(),
                    edge_type: "DESCRIBED_BY".to_string(),
                    user_id: "exobrain".to_string(),
                    visibility: Visibility::Shared,
                    properties: default_edge_properties("root a"),
                },
                GraphEdge {
                    from_id: "550e8400-e29b-41d4-a716-446655440010".to_string(),
                    to_id: "550e8400-e29b-41d4-a716-446655440012".to_string(),
                    edge_type: "DESCRIBED_BY".to_string(),
                    user_id: "exobrain".to_string(),
                    visibility: Visibility::Shared,
                    properties: default_edge_properties("root b"),
                },
            ],
        })
        .await
        .expect_err("entity should not allow multiple DESCRIBED_BY edges");

    assert!(err
        .to_string()
        .contains("must have exactly one outgoing DESCRIBED_BY edge"));
}

#[tokio::test]
async fn rejects_invalid_schema_kind() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .upsert_schema_type(UpsertSchemaTypeCommand {
            schema_type: SchemaType {
                id: "x".to_string(),
                kind: "invalid".to_string(),
                name: "x".to_string(),
                description: String::new(),
                active: true,
            },
            parent_type_id: None,
            properties: vec![],
        })
        .await
        .expect_err("invalid schema kind should fail");

    assert!(err.to_string().contains("schema kind must be one of"));
}

#[tokio::test]
async fn rejects_node_without_parent() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .upsert_schema_type(UpsertSchemaTypeCommand {
            schema_type: SchemaType {
                id: "node.person".to_string(),
                kind: "node".to_string(),
                name: "Person".to_string(),
                description: String::new(),
                active: true,
            },
            parent_type_id: None,
            properties: vec![],
        })
        .await
        .expect_err("missing parent should fail");

    assert!(err.to_string().contains("must declare parent_type_id"));
}

#[tokio::test]
async fn upsert_schema_type_syncs_type_vector_with_active_payload_support() {
    let seen = Arc::new(Mutex::new(Vec::new()));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    )
    .with_type_vector_repository(Arc::new(CapturingTypeVectorRepository {
        seen: seen.clone(),
        fail_for_type_id: None,
    }));

    let upserted = app
        .upsert_schema_type(UpsertSchemaTypeCommand {
            schema_type: SchemaType {
                id: "node.person".to_string(),
                kind: "node".to_string(),
                name: "Person".to_string(),
                description: "A human being".to_string(),
                active: false,
            },
            parent_type_id: Some("node.entity".to_string()),
            properties: vec![],
        })
        .await
        .expect("upsert should succeed");

    assert!(!upserted.active);
    let seen = seen
        .lock()
        .expect("type vector lock should not be poisoned");
    assert_eq!(seen.len(), 1);
    assert_eq!(seen[0].0.id, "node.person");
    assert!(!seen[0].0.active);
    assert_eq!(seen[0].1, vec![0.1, 0.2]);
}

#[tokio::test]
async fn upsert_schema_type_rolls_back_when_type_vector_sync_fails() {
    let repo = Arc::new(FakeSchemaRepo::new());
    let app = KnowledgeApplication::new(
        repo.clone(),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    )
    .with_type_vector_repository(Arc::new(CapturingTypeVectorRepository {
        seen: Arc::new(Mutex::new(Vec::new())),
        fail_for_type_id: Some("node.person".to_string()),
    }));

    let err = app
        .upsert_schema_type(UpsertSchemaTypeCommand {
            schema_type: SchemaType {
                id: "node.person".to_string(),
                kind: "node".to_string(),
                name: "Person".to_string(),
                description: "A human being".to_string(),
                active: true,
            },
            parent_type_id: Some("node.entity".to_string()),
            properties: vec![],
        })
        .await
        .expect_err("upsert should fail when type vector sync fails");

    assert!(!err.to_string().is_empty());

    let schema_type = repo
        .get_schema_type("node.person")
        .await
        .expect("repo call should succeed");
    assert!(
        schema_type.is_none(),
        "schema write should have been rolled back"
    );
}

#[tokio::test]
async fn ingests_blocks_and_creates_embeddings() {
    let captured = Arc::new(Mutex::new(vec![]));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CapturingGraphRepository {
            seen: captured.clone(),
            root_exists: false,
            user_graph_initialized: true,
            marked_user_ids: Arc::new(Mutex::new(vec![])),
            block_contexts: HashMap::new(),
        }),
        Arc::new(FakeEmbedder),
    );
    app.upsert_graph_delta(GraphDelta {
        universes: vec![],
        entities: vec![EntityNode {
            id: "550e8400-e29b-41d4-a716-446655440001".to_string(),
            type_id: "node.person".to_string(),
            user_id: "user-1".to_string(),
            visibility: Visibility::Private,
            universe_id: None,
            properties: vec![PropertyValue {
                key: "name".to_string(),
                value: PropertyScalar::String("Alex".to_string()),
            }],
            resolved_labels: vec![],
        }],
        blocks: vec![BlockNode {
            id: "550e8400-e29b-41d4-a716-446655440002".to_string(),
            type_id: "node.block".to_string(),
            user_id: "user-1".to_string(),
            visibility: Visibility::Private,
            properties: vec![PropertyValue {
                key: "text".to_string(),
                value: PropertyScalar::String("Alex is a close friend.".to_string()),
            }],
            resolved_labels: vec![],
        }],
        edges: vec![
            GraphEdge {
                from_id: "550e8400-e29b-41d4-a716-446655440001".to_string(),
                to_id: "9d7f0fa5-78c1-4805-9efb-3f8f16090d7f".to_string(),
                edge_type: "IS_PART_OF".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: default_edge_properties("test universe assignment"),
            },
            GraphEdge {
                from_id: "550e8400-e29b-41d4-a716-446655440001".to_string(),
                to_id: "550e8400-e29b-41d4-a716-446655440002".to_string(),
                edge_type: "DESCRIBED_BY".to_string(),
                user_id: "user-1".to_string(),
                visibility: Visibility::Private,
                properties: default_edge_properties("test location"),
            },
        ],
    })
    .await
    .expect("ingestion should succeed");

    let guard = captured.lock().expect("lock should be available");
    assert_eq!(guard.len(), 1);
    assert_eq!(guard[0].block.id, "550e8400-e29b-41d4-a716-446655440002");
    assert_eq!(guard[0].vector.len(), 2);
    assert_eq!(guard[0].block_level, 0);
    assert_eq!(guard[0].text, "Alex is a close friend.");
    assert_eq!(guard[0].user_id, "user-1");
    assert_eq!(guard[0].visibility, Visibility::Private);
}

#[tokio::test]
async fn seeds_common_root_when_missing() {
    let captured = Arc::new(Mutex::new(vec![]));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CapturingGraphRepository {
            seen: captured.clone(),
            root_exists: false,
            user_graph_initialized: false,
            marked_user_ids: Arc::new(Mutex::new(vec![])),
            block_contexts: HashMap::new(),
        }),
        Arc::new(FakeEmbedder),
    );

    app.ensure_common_root_graph()
        .await
        .expect("root graph seeding should succeed");

    let guard = captured.lock().expect("lock should be available");
    assert_eq!(guard.len(), 1);
    assert_eq!(guard[0].block.id, "ea5ca80f-346b-4f66-bff2-d307ce5d7da9");
    assert_eq!(guard[0].user_id, "exobrain");
    assert_eq!(guard[0].visibility, Visibility::Shared);
}

#[tokio::test]
async fn initializes_user_graph() {
    let captured = Arc::new(Mutex::new(vec![]));
    let marked_user_ids = Arc::new(Mutex::new(vec![]));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CapturingGraphRepository {
            seen: captured.clone(),
            root_exists: true,
            user_graph_initialized: false,
            marked_user_ids: marked_user_ids.clone(),
            block_contexts: HashMap::new(),
        }),
        Arc::new(FakeEmbedder),
    );

    let node_ids = app
        .get_user_init_graph("user-1", "Alex")
        .await
        .expect("user graph init should succeed");

    assert!(!node_ids.person_entity_id.is_empty());
    assert!(!node_ids.assistant_entity_id.is_empty());

    let guard = captured.lock().expect("lock should be available");
    assert_eq!(guard.len(), 1);
    assert_eq!(guard[0].block_level, 0);
    assert_eq!(guard[0].visibility, Visibility::Private);

    let marked = marked_user_ids.lock().expect("lock should be available");
    assert_eq!(marked.len(), 1);
    assert!(marked[0].starts_with("user-1:"));
}

#[test]
fn user_init_delta_sets_private_visibility_for_all_nodes() {
    let delta = KnowledgeApplication::user_init_delta("user-1", "Alex");

    assert!(delta
        .entities
        .iter()
        .all(|entity| entity.visibility == Visibility::Private));
    assert!(delta
        .blocks
        .iter()
        .all(|block| block.visibility == Visibility::Private));
    assert!(delta
        .edges
        .iter()
        .all(|edge| edge.visibility == Visibility::Private));
}

#[tokio::test]
async fn skips_user_graph_init_when_marker_already_exists() {
    let captured = Arc::new(Mutex::new(vec![]));
    let marked_user_ids = Arc::new(Mutex::new(vec![]));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CapturingGraphRepository {
            seen: captured.clone(),
            root_exists: true,
            user_graph_initialized: true,
            marked_user_ids: marked_user_ids.clone(),
            block_contexts: HashMap::new(),
        }),
        Arc::new(FakeEmbedder),
    );

    let node_ids = app
        .get_user_init_graph("user-1", "Alex")
        .await
        .expect("user graph init should short-circuit");

    assert!(!node_ids.person_entity_id.is_empty());
    assert!(!node_ids.assistant_entity_id.is_empty());

    let guard = captured.lock().expect("lock should be available");
    assert!(guard.is_empty());

    let marked = marked_user_ids.lock().expect("lock should be available");
    assert!(marked.is_empty());
}

#[tokio::test]
async fn upsert_graph_delta_initializes_missing_users_before_main_write() {
    let initialized = Arc::new(Mutex::new(HashSet::from(["user-ready".to_string()])));
    let call_order = Arc::new(Mutex::new(vec![]));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(TrackingInitGraphRepository {
            initialized: initialized.clone(),
            call_order: call_order.clone(),
        }),
        Arc::new(FakeEmbedder),
    );

    app.upsert_graph_delta(GraphDelta {
        universes: vec![],
        entities: vec![EntityNode {
            id: "550e8400-e29b-41d4-a716-446655440011".to_string(),
            type_id: "node.person".to_string(),
            universe_id: Some(COMMON_UNIVERSE_ID.to_string()),
            user_id: "user-missing".to_string(),
            visibility: Visibility::Private,
            properties: vec![PropertyValue {
                key: "name".to_string(),
                value: PropertyScalar::String("Taylor".to_string()),
            }],
            resolved_labels: vec![],
        }],
        blocks: vec![BlockNode {
            id: "550e8400-e29b-41d4-a716-446655440012".to_string(),
            type_id: "node.block".to_string(),
            user_id: "user-ready".to_string(),
            visibility: Visibility::Private,
            properties: vec![PropertyValue {
                key: "text".to_string(),
                value: PropertyScalar::String("A note from an initialized user".to_string()),
            }],
            resolved_labels: vec![],
        }],
        edges: vec![GraphEdge {
            from_id: "550e8400-e29b-41d4-a716-446655440011".to_string(),
            to_id: "550e8400-e29b-41d4-a716-446655440012".to_string(),
            edge_type: "DESCRIBED_BY".to_string(),
            user_id: "user-ready".to_string(),
            visibility: Visibility::Private,
            properties: default_edge_properties("test linkage"),
        }],
    })
    .await
    .expect("upsert should initialize missing user then apply main delta");

    let initialized_guard = initialized.lock().expect("lock should be available");
    assert!(initialized_guard.contains("user-missing"));
    assert!(initialized_guard.contains("user-ready"));

    let order_guard = call_order.lock().expect("lock should be available");
    assert_eq!(order_guard.as_slice(), ["init", "main"]);
}

#[tokio::test]
async fn computes_block_levels_from_described_by_and_summarizes_edges() {
    let root_block_id = "550e8400-e29b-41d4-a716-446655440099";
    let child_block_id = "550e8400-e29b-41d4-a716-446655440098";
    let blocks = vec![
        BlockNode {
            id: root_block_id.to_string(),
            type_id: "node.block".to_string(),
            user_id: "user-1".to_string(),
            visibility: Visibility::Private,
            properties: vec![],
            resolved_labels: vec![],
        },
        BlockNode {
            id: child_block_id.to_string(),
            type_id: "node.block".to_string(),
            user_id: "user-1".to_string(),
            visibility: Visibility::Private,
            properties: vec![],
            resolved_labels: vec![],
        },
    ];
    let edges = vec![
        GraphEdge {
            from_id: "550e8400-e29b-41d4-a716-446655440001".to_string(),
            to_id: root_block_id.to_string(),
            edge_type: "DESCRIBED_BY".to_string(),
            user_id: "user-1".to_string(),
            visibility: Visibility::Private,
            properties: vec![],
        },
        GraphEdge {
            from_id: root_block_id.to_string(),
            to_id: child_block_id.to_string(),
            edge_type: "SUMMARIZES".to_string(),
            user_id: "user-1".to_string(),
            visibility: Visibility::Private,
            properties: vec![],
        },
    ];

    let levels =
        block_levels_for_blocks(&blocks, &edges, &FakeGraphRepository { root_exists: false })
            .await
            .expect("levels should be computed");
    assert_eq!(levels.get(root_block_id).copied(), Some(0));
    assert_eq!(levels.get(child_block_id).copied(), Some(1));
}

#[tokio::test]
async fn resolves_root_entity_and_level_from_existing_summarize_parent_block() {
    let existing_parent_block_id = "9a8c589c-51ea-4e36-b60e-505769f19b7a";
    let new_block_id = "0fdfb642-1ec0-48c9-a8e1-3120e8da5d0f";
    let blocks = vec![BlockNode {
        id: new_block_id.to_string(),
        type_id: "node.block".to_string(),
        user_id: "exobrain".to_string(),
        visibility: Visibility::Shared,
        properties: vec![PropertyValue {
            key: "text".to_string(),
            value: PropertyScalar::String("child".to_string()),
        }],
        resolved_labels: vec![],
    }];
    let edges = vec![GraphEdge {
        from_id: existing_parent_block_id.to_string(),
        to_id: new_block_id.to_string(),
        edge_type: "SUMMARIZES".to_string(),
        user_id: "exobrain".to_string(),
        visibility: Visibility::Shared,
        properties: default_edge_properties("existing summarize parent"),
    }];
    let graph_repo = CapturingGraphRepository {
        seen: Arc::new(Mutex::new(vec![])),
        root_exists: false,
        user_graph_initialized: false,
        marked_user_ids: Arc::new(Mutex::new(vec![])),
        block_contexts: HashMap::from([(
            existing_parent_block_id.to_string(),
            ExistingBlockContext {
                root_entity_id: "8c75cc89-6204-4fed-aec1-34d032ff95ee".to_string(),
                block_level: 0,
            },
        )]),
    };

    let root_ids = root_entity_ids_for_blocks(&blocks, &edges, &graph_repo)
        .await
        .expect("root entity id should resolve from existing summarize parent");
    assert_eq!(
        root_ids.get(new_block_id).map(String::as_str),
        Some("8c75cc89-6204-4fed-aec1-34d032ff95ee")
    );

    let levels = block_levels_for_blocks(&blocks, &edges, &graph_repo)
        .await
        .expect("level should resolve from existing summarize parent");
    assert_eq!(levels.get(new_block_id).copied(), Some(1));
}
#[tokio::test]
async fn accepts_implicit_is_part_of_from_entity_universe_assignment() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    );

    app.upsert_graph_delta(GraphDelta {
        universes: vec![UniverseNode {
            id: "26bcdef7-41ce-4dc5-81e2-d2ba786270c1".to_string(),
            name: "Fake World".to_string(),
            user_id: "exobrain".to_string(),
            visibility: Visibility::Shared,
        }],
        entities: vec![
            EntityNode {
                id: "7ca59d34-ec3f-42a5-9500-0342f1690680".to_string(),
                type_id: "node.person".to_string(),
                universe_id: Some("26bcdef7-41ce-4dc5-81e2-d2ba786270c1".to_string()),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Fake Person".to_string()),
                }],
                resolved_labels: vec![],
            },
            EntityNode {
                id: "f78e0747-8948-4a2b-9540-06dc46a868f8".to_string(),
                type_id: "node.object".to_string(),
                universe_id: None,
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Real Object".to_string()),
                }],
                resolved_labels: vec![],
            },
        ],
        blocks: vec![],
        edges: vec![],
    })
    .await
    .expect("implicit IS_PART_OF relationships should satisfy topology rules");
}

#[tokio::test]
async fn accepts_message_edges_and_located_at_rules() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    );

    app.upsert_graph_delta(GraphDelta {
        universes: vec![],
        entities: vec![
            EntityNode {
                id: "8fca4f08-c305-4d16-91b5-e283f5f723aa".to_string(),
                type_id: "node.message".to_string(),
                universe_id: None,
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Update Message".to_string()),
                }],
                resolved_labels: vec![],
            },
            EntityNode {
                id: "46a0475f-76da-4f50-8875-844fd4cb1770".to_string(),
                type_id: "node.person".to_string(),
                universe_id: None,
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Alex".to_string()),
                }],
                resolved_labels: vec![],
            },
            EntityNode {
                id: "a327877d-e8c4-4cd8-a889-a5251120cce5".to_string(),
                type_id: "node.place".to_string(),
                universe_id: None,
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Workspace".to_string()),
                }],
                resolved_labels: vec![],
            },
        ],
        blocks: vec![],
        edges: vec![
            GraphEdge {
                from_id: "8fca4f08-c305-4d16-91b5-e283f5f723aa".to_string(),
                to_id: "46a0475f-76da-4f50-8875-844fd4cb1770".to_string(),
                edge_type: "SENT_TO".to_string(),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: default_edge_properties("test recipient"),
            },
            GraphEdge {
                from_id: "8fca4f08-c305-4d16-91b5-e283f5f723aa".to_string(),
                to_id: "46a0475f-76da-4f50-8875-844fd4cb1770".to_string(),
                edge_type: "SENT_BY".to_string(),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: default_edge_properties("test sender"),
            },
            GraphEdge {
                from_id: "8fca4f08-c305-4d16-91b5-e283f5f723aa".to_string(),
                to_id: "a327877d-e8c4-4cd8-a889-a5251120cce5".to_string(),
                edge_type: "LOCATED_AT".to_string(),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: default_edge_properties("test location"),
            },
        ],
    })
    .await
    .expect("message and located_at edge rules should be accepted");
}

#[tokio::test]
async fn rejects_edges_missing_required_global_metadata() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .upsert_graph_delta(GraphDelta {
            universes: vec![],
            entities: vec![
                EntityNode {
                    id: "2b9bdcc4-2f4a-4b58-9097-8ab205d8d506".to_string(),
                    type_id: "node.person".to_string(),
                    universe_id: None,
                    user_id: "exobrain".to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![PropertyValue {
                        key: "name".to_string(),
                        value: PropertyScalar::String("Alex".to_string()),
                    }],
                    resolved_labels: vec![],
                },
                EntityNode {
                    id: "f904fdb6-1770-4638-a2fd-65eae6553be8".to_string(),
                    type_id: "node.person".to_string(),
                    universe_id: None,
                    user_id: "exobrain".to_string(),
                    visibility: Visibility::Shared,
                    properties: vec![PropertyValue {
                        key: "name".to_string(),
                        value: PropertyScalar::String("Morgan".to_string()),
                    }],
                    resolved_labels: vec![],
                },
            ],
            blocks: vec![],
            edges: vec![GraphEdge {
                from_id: "2b9bdcc4-2f4a-4b58-9097-8ab205d8d506".to_string(),
                to_id: "f904fdb6-1770-4638-a2fd-65eae6553be8".to_string(),
                edge_type: "RELATED_TO".to_string(),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![],
            }],
        })
        .await
        .expect_err("edge metadata should be required for all edges");

    let message = err.to_string();
    assert!(message.contains("required property 'confidence'"));
    assert!(message.contains("required property 'status'"));
    assert!(message.contains("required property 'provenance_hint'"));
}

#[tokio::test]
async fn rejects_client_supplied_internal_timestamps() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .upsert_graph_delta(GraphDelta {
            universes: vec![],
            entities: vec![EntityNode {
                id: "2b9bdcc4-2f4a-4b58-9097-8ab205d8d506".to_string(),
                type_id: "node.person".to_string(),
                universe_id: None,
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![
                    PropertyValue {
                        key: "name".to_string(),
                        value: PropertyScalar::String("Alex".to_string()),
                    },
                    PropertyValue {
                        key: "created_at".to_string(),
                        value: PropertyScalar::String("2025-01-01T00:00:00Z".to_string()),
                    },
                ],
                resolved_labels: vec![],
            }],
            blocks: vec![],
            edges: vec![],
        })
        .await
        .expect_err("created_at should be internal-only");

    assert!(err
        .to_string()
        .contains("cannot set internal property 'created_at'"));
}

#[tokio::test]
async fn accepts_block_contradicts_edge() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    );

    app.upsert_graph_delta(GraphDelta {
        universes: vec![],
        entities: vec![
            EntityNode {
                id: "64357dfa-389d-401e-a246-c7a97147f627".to_string(),
                type_id: "node.person".to_string(),
                universe_id: None,
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Witness A".to_string()),
                }],
                resolved_labels: vec![],
            },
            EntityNode {
                id: "74357dfa-389d-401e-a246-c7a97147f627".to_string(),
                type_id: "node.person".to_string(),
                universe_id: None,
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "name".to_string(),
                    value: PropertyScalar::String("Witness B".to_string()),
                }],
                resolved_labels: vec![],
            },
        ],
        blocks: vec![
            BlockNode {
                id: "352832a6-fe04-4697-9de0-dbec398adf13".to_string(),
                type_id: "node.block".to_string(),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Statement A".to_string()),
                }],
                resolved_labels: vec![],
            },
            BlockNode {
                id: "afc3bff2-2478-43f0-bb88-9199f960d0c1".to_string(),
                type_id: "node.block".to_string(),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: vec![PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("Statement B".to_string()),
                }],
                resolved_labels: vec![],
            },
        ],
        edges: vec![
            GraphEdge {
                from_id: "64357dfa-389d-401e-a246-c7a97147f627".to_string(),
                to_id: "352832a6-fe04-4697-9de0-dbec398adf13".to_string(),
                edge_type: "DESCRIBED_BY".to_string(),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: default_edge_properties("test root a"),
            },
            GraphEdge {
                from_id: "74357dfa-389d-401e-a246-c7a97147f627".to_string(),
                to_id: "afc3bff2-2478-43f0-bb88-9199f960d0c1".to_string(),
                edge_type: "DESCRIBED_BY".to_string(),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: default_edge_properties("test root b"),
            },
            GraphEdge {
                from_id: "352832a6-fe04-4697-9de0-dbec398adf13".to_string(),
                to_id: "afc3bff2-2478-43f0-bb88-9199f960d0c1".to_string(),
                edge_type: "CONTRADICTS".to_string(),
                user_id: "exobrain".to_string(),
                visibility: Visibility::Shared,
                properties: default_edge_properties("test contradiction"),
            },
        ],
    })
    .await
    .expect("block CONTRADICTS edge should be accepted");
}

#[tokio::test]
async fn accepts_cross_user_scope_in_single_delta() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(FakeGraphRepository { root_exists: false }),
        Arc::new(FakeEmbedder),
    );

    app.upsert_graph_delta(GraphDelta {
        universes: vec![],
        entities: vec![EntityNode {
            id: "550e8400-e29b-41d4-a716-4466554400ab".to_string(),
            type_id: "node.person".to_string(),
            universe_id: None,
            user_id: "user-2".to_string(),
            visibility: Visibility::Private,
            properties: vec![PropertyValue {
                key: "name".to_string(),
                value: PropertyScalar::String("Cross User Person".to_string()),
            }],
            resolved_labels: vec![],
        }],
        blocks: vec![BlockNode {
            id: "d0e2ceb6-3daa-441f-a87b-2168ac723ca7".to_string(),
            type_id: "node.block".to_string(),
            user_id: "user-3".to_string(),
            visibility: Visibility::Shared,
            properties: vec![PropertyValue {
                key: "text".to_string(),
                value: PropertyScalar::String("cross-user block".to_string()),
            }],
            resolved_labels: vec![],
        }],
        edges: vec![GraphEdge {
            from_id: "550e8400-e29b-41d4-a716-4466554400ab".to_string(),
            to_id: "d0e2ceb6-3daa-441f-a87b-2168ac723ca7".to_string(),
            edge_type: "DESCRIBED_BY".to_string(),
            user_id: "user-4".to_string(),
            visibility: Visibility::Shared,
            properties: default_edge_properties("cross-user edge"),
        }],
    })
    .await
    .expect("cross-user records should be accepted in a single delta");
}

struct CandidateGraphRepository {
    seen_queries: Arc<Mutex<Vec<FindEntityCandidatesQuery>>>,
    seen_vectors: Arc<Mutex<Vec<Option<Vec<f32>>>>>,
    candidates: RawEntityCandidateData,
}

#[async_trait]
impl GraphRepository for CandidateGraphRepository {
    async fn apply_delta_with_blocks(
        &self,
        _delta: &GraphDelta,
        _blocks: &[EmbeddedBlock],
    ) -> Result<()> {
        Ok(())
    }

    async fn common_root_graph_exists(&self) -> Result<bool> {
        Ok(true)
    }

    async fn user_graph_needs_initialization(&self, _user_id: &str) -> Result<bool> {
        Ok(false)
    }

    async fn mark_user_graph_initialized(
        &self,
        _user_id: &str,
        _node_ids: &UserInitGraphNodeIds,
    ) -> Result<()> {
        Ok(())
    }

    async fn get_user_init_graph_node_ids(
        &self,
        _user_id: &str,
    ) -> Result<Option<UserInitGraphNodeIds>> {
        Ok(None)
    }

    async fn update_person_name(&self, _person_entity_id: &str, _user_name: &str) -> Result<()> {
        Ok(())
    }

    async fn get_existing_block_context(
        &self,
        _block_id: &str,
        _user_id: &str,
        _visibility: Visibility,
    ) -> Result<Option<ExistingBlockContext>> {
        Ok(None)
    }

    async fn get_node_relationship_counts(&self, _node_id: &str) -> Result<NodeRelationshipCounts> {
        Ok(NodeRelationshipCounts::default())
    }

    async fn find_entity_candidates(
        &self,
        query: &FindEntityCandidatesQuery,
        query_vector: Option<&[f32]>,
    ) -> Result<RawEntityCandidateData> {
        self.seen_queries
            .lock()
            .expect("lock should be available")
            .push(query.clone());
        self.seen_vectors
            .lock()
            .expect("lock should be available")
            .push(query_vector.map(|v| v.to_vec()));
        Ok(self.candidates.clone())
    }

    async fn list_entities_by_type(
        &self,
        _query: &ListEntitiesByTypeQuery,
    ) -> Result<ListEntitiesByTypeResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_entity_context(
        &self,
        _query: &GetEntityContextQuery,
    ) -> Result<GetEntityContextResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_extraction_universes(&self, _user_id: &str) -> Result<Vec<ExtractionUniverse>> {
        Ok(Vec::new())
    }
}

struct TrackingEmbedder {
    seen_texts: Arc<Mutex<Vec<Vec<String>>>>,
    vectors: Vec<Vec<f32>>,
}

#[async_trait]
impl Embedder for TrackingEmbedder {
    async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        self.seen_texts
            .lock()
            .expect("lock should be available")
            .push(texts.to_vec());
        Ok(self.vectors.clone())
    }
}

#[tokio::test]
async fn find_entity_candidates_normalizes_embeds_sorts_and_limits() {
    let seen_queries = Arc::new(Mutex::new(Vec::new()));
    let seen_vectors = Arc::new(Mutex::new(Vec::new()));
    let seen_texts = Arc::new(Mutex::new(Vec::new()));

    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CandidateGraphRepository {
            seen_queries: Arc::clone(&seen_queries),
            seen_vectors: Arc::clone(&seen_vectors),
            candidates: RawEntityCandidateData {
                lexical_matches: vec![
                    EntityLexicalMatch {
                        id: "2".to_string(),
                        name: "Beta".to_string(),
                        score: 0.2,
                        type_id: "node.person".to_string(),
                        matched_tokens: vec!["beta".to_string()],
                    },
                    EntityLexicalMatch {
                        id: "1".to_string(),
                        name: "Alpha".to_string(),
                        score: 0.9,
                        type_id: "node.person".to_string(),
                        matched_tokens: vec!["alpha".to_string()],
                    },
                ],
                semantic_hits: vec![EntitySemanticHit {
                    entity_id: "1".to_string(),
                    name: "Alpha".to_string(),
                    type_id: "node.person".to_string(),
                    score: 0.2,
                    described_by_text: Some("alpha description".to_string()),
                }],
            },
        }),
        Arc::new(TrackingEmbedder {
            seen_texts: Arc::clone(&seen_texts),
            vectors: vec![vec![0.3, 0.4]],
        }),
    );

    let result = app
        .find_entity_candidates(FindEntityCandidatesQuery {
            names: vec!["  Alice ".to_string(), "".to_string(), "Bob".to_string()],
            potential_type_ids: vec![" node.person ".to_string(), "   ".to_string()],
            short_description: Some("  knows rust  ".to_string()),
            user_id: " user-1 ".to_string(),
            limit: Some(1),
        })
        .await
        .expect("query should succeed");

    assert_eq!(result.candidates.len(), 1);
    assert_eq!(result.candidates[0].id, "1");

    let queries = seen_queries.lock().expect("lock should be available");
    assert_eq!(queries.len(), 1);
    assert_eq!(
        queries[0].names,
        vec!["alice".to_string(), "bob".to_string()]
    );
    assert_eq!(
        queries[0].potential_type_ids,
        vec!["node.person".to_string()]
    );
    assert_eq!(queries[0].short_description.as_deref(), Some("knows rust"));
    assert_eq!(queries[0].user_id, "user-1");

    let vectors = seen_vectors.lock().expect("lock should be available");
    assert_eq!(vectors.len(), 1);
    assert_eq!(vectors[0], Some(vec![0.3, 0.4]));

    let texts = seen_texts.lock().expect("lock should be available");
    assert_eq!(texts.as_slice(), &[vec!["knows rust".to_string()]]);
}

#[tokio::test]
async fn find_entity_candidates_rejects_empty_payload() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CandidateGraphRepository {
            seen_queries: Arc::new(Mutex::new(Vec::new())),
            seen_vectors: Arc::new(Mutex::new(Vec::new())),
            candidates: RawEntityCandidateData::default(),
        }),
        Arc::new(TrackingEmbedder {
            seen_texts: Arc::new(Mutex::new(Vec::new())),
            vectors: vec![],
        }),
    );

    let err = app
        .find_entity_candidates(FindEntityCandidatesQuery {
            names: vec!["  ".to_string()],
            potential_type_ids: vec![],
            short_description: Some("   ".to_string()),
            user_id: "user-1".to_string(),
            limit: Some(10),
        })
        .await
        .expect_err("empty query payload should fail");

    assert!(err
        .to_string()
        .contains("at least one name or short_description is required"));
}

#[tokio::test]
async fn find_entity_candidates_rejects_blank_user_id() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CandidateGraphRepository {
            seen_queries: Arc::new(Mutex::new(Vec::new())),
            seen_vectors: Arc::new(Mutex::new(Vec::new())),
            candidates: RawEntityCandidateData::default(),
        }),
        Arc::new(TrackingEmbedder {
            seen_texts: Arc::new(Mutex::new(Vec::new())),
            vectors: vec![],
        }),
    );

    let err = app
        .find_entity_candidates(FindEntityCandidatesQuery {
            names: vec!["alice".to_string()],
            potential_type_ids: vec![],
            short_description: None,
            user_id: "   ".to_string(),
            limit: None,
        })
        .await
        .expect_err("blank user_id should fail");

    assert!(err.to_string().contains("user_id is required"));
}

#[tokio::test]
async fn find_entity_candidates_orders_by_score_without_limit() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CandidateGraphRepository {
            seen_queries: Arc::new(Mutex::new(Vec::new())),
            seen_vectors: Arc::new(Mutex::new(Vec::new())),
            candidates: RawEntityCandidateData {
                lexical_matches: vec![
                    EntityLexicalMatch {
                        id: "low".to_string(),
                        name: "Low".to_string(),
                        score: 0.1,
                        type_id: "node.person".to_string(),
                        matched_tokens: vec![],
                    },
                    EntityLexicalMatch {
                        id: "high".to_string(),
                        name: "High".to_string(),
                        score: 0.9,
                        type_id: "node.person".to_string(),
                        matched_tokens: vec![],
                    },
                    EntityLexicalMatch {
                        id: "mid".to_string(),
                        name: "Mid".to_string(),
                        score: 0.4,
                        type_id: "node.person".to_string(),
                        matched_tokens: vec![],
                    },
                ],
                semantic_hits: vec![],
            },
        }),
        Arc::new(TrackingEmbedder {
            seen_texts: Arc::new(Mutex::new(Vec::new())),
            vectors: vec![],
        }),
    );

    let result = app
        .find_entity_candidates(FindEntityCandidatesQuery {
            names: vec!["high".to_string()],
            potential_type_ids: vec![],
            short_description: None,
            user_id: "u-1".to_string(),
            limit: None,
        })
        .await
        .expect("query should succeed");

    assert_eq!(
        result
            .candidates
            .into_iter()
            .map(|candidate| candidate.id)
            .collect::<Vec<_>>(),
        vec!["high".to_string(), "mid".to_string(), "low".to_string()]
    );
}

#[tokio::test]
async fn find_entity_candidates_combines_lexical_and_semantic_scores() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(CandidateGraphRepository {
            seen_queries: Arc::new(Mutex::new(Vec::new())),
            seen_vectors: Arc::new(Mutex::new(Vec::new())),
            candidates: RawEntityCandidateData {
                lexical_matches: vec![
                    EntityLexicalMatch {
                        id: "lexical-only".to_string(),
                        name: "Lexical".to_string(),
                        score: 1.0,
                        type_id: "node.person".to_string(),
                        matched_tokens: vec!["lexical".to_string()],
                    },
                    EntityLexicalMatch {
                        id: "blended".to_string(),
                        name: "Blended".to_string(),
                        score: 0.5,
                        type_id: "node.person".to_string(),
                        matched_tokens: vec!["blend".to_string()],
                    },
                ],
                semantic_hits: vec![
                    EntitySemanticHit {
                        entity_id: "blended".to_string(),
                        name: "Blended".to_string(),
                        type_id: "node.person".to_string(),
                        score: 1.0,
                        described_by_text: Some("best match".to_string()),
                    },
                    EntitySemanticHit {
                        entity_id: "semantic-only".to_string(),
                        name: "Semantic".to_string(),
                        type_id: "node.person".to_string(),
                        score: 0.9,
                        described_by_text: Some("semantic context".to_string()),
                    },
                ],
            },
        }),
        Arc::new(TrackingEmbedder {
            seen_texts: Arc::new(Mutex::new(Vec::new())),
            vectors: vec![vec![0.7, 0.3]],
        }),
    );

    let result = app
        .find_entity_candidates(FindEntityCandidatesQuery {
            names: vec!["blend".to_string()],
            potential_type_ids: vec![],
            short_description: Some("desc".to_string()),
            user_id: "u-1".to_string(),
            limit: None,
        })
        .await
        .expect("query should succeed");

    assert_eq!(
        result
            .candidates
            .iter()
            .map(|candidate| candidate.id.as_str())
            .collect::<Vec<_>>(),
        vec!["blended", "lexical-only", "semantic-only"]
    );
    assert_eq!(
        result.candidates[0].described_by_text.as_deref(),
        Some("best match")
    );
}

struct ContextGraphRepository {
    seen_queries: Arc<Mutex<Vec<GetEntityContextQuery>>>,
    result: GetEntityContextResult,
}

#[async_trait]
impl GraphRepository for ContextGraphRepository {
    async fn apply_delta_with_blocks(
        &self,
        _delta: &GraphDelta,
        _blocks: &[EmbeddedBlock],
    ) -> Result<()> {
        Ok(())
    }

    async fn common_root_graph_exists(&self) -> Result<bool> {
        Ok(true)
    }

    async fn user_graph_needs_initialization(&self, _user_id: &str) -> Result<bool> {
        Ok(false)
    }

    async fn mark_user_graph_initialized(
        &self,
        _user_id: &str,
        _node_ids: &UserInitGraphNodeIds,
    ) -> Result<()> {
        Ok(())
    }

    async fn get_user_init_graph_node_ids(
        &self,
        _user_id: &str,
    ) -> Result<Option<UserInitGraphNodeIds>> {
        Ok(None)
    }

    async fn update_person_name(&self, _person_entity_id: &str, _user_name: &str) -> Result<()> {
        Ok(())
    }

    async fn get_existing_block_context(
        &self,
        _block_id: &str,
        _user_id: &str,
        _visibility: Visibility,
    ) -> Result<Option<ExistingBlockContext>> {
        Ok(None)
    }

    async fn get_node_relationship_counts(&self, _node_id: &str) -> Result<NodeRelationshipCounts> {
        Ok(NodeRelationshipCounts::default())
    }

    async fn find_entity_candidates(
        &self,
        _query: &FindEntityCandidatesQuery,
        _query_vector: Option<&[f32]>,
    ) -> Result<RawEntityCandidateData> {
        Ok(RawEntityCandidateData::default())
    }

    async fn list_entities_by_type(
        &self,
        _query: &ListEntitiesByTypeQuery,
    ) -> Result<ListEntitiesByTypeResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_entity_context(
        &self,
        query: &GetEntityContextQuery,
    ) -> Result<GetEntityContextResult> {
        self.seen_queries
            .lock()
            .expect("lock should be available")
            .push(query.clone());
        Ok(self.result.clone())
    }

    async fn get_extraction_universes(&self, _user_id: &str) -> Result<Vec<ExtractionUniverse>> {
        Ok(Vec::new())
    }
}

#[tokio::test]
async fn get_entity_context_rejects_blank_entity_id() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ContextGraphRepository {
            seen_queries: Arc::new(Mutex::new(Vec::new())),
            result: sample_entity_context_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .get_entity_context(GetEntityContextQuery {
            entity_id: "   ".to_string(),
            user_id: "u-1".to_string(),
            max_block_level: 3,
        })
        .await
        .expect_err("blank entity_id should fail");

    assert!(err.to_string().contains("entity_id is required"));
}

#[tokio::test]
async fn get_entity_context_rejects_blank_user_id() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ContextGraphRepository {
            seen_queries: Arc::new(Mutex::new(Vec::new())),
            result: sample_entity_context_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .get_entity_context(GetEntityContextQuery {
            entity_id: "entity-1".to_string(),
            user_id: "   ".to_string(),
            max_block_level: 3,
        })
        .await
        .expect_err("blank user_id should fail");

    assert!(err.to_string().contains("user_id is required"));
}

#[tokio::test]
async fn get_entity_context_passes_max_block_level_and_keeps_top_level_fields() {
    let seen_queries = Arc::new(Mutex::new(Vec::new()));
    let expected = sample_entity_context_result();
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ContextGraphRepository {
            seen_queries: Arc::clone(&seen_queries),
            result: expected.clone(),
        }),
        Arc::new(FakeEmbedder),
    );

    let result = app
        .get_entity_context(GetEntityContextQuery {
            entity_id: "entity-1".to_string(),
            user_id: "user-1".to_string(),
            max_block_level: 7,
        })
        .await
        .expect("query should succeed");

    assert_eq!(result.entity.id, expected.entity.id);
    assert_eq!(result.entity.type_id, expected.entity.type_id);
    assert_eq!(result.entity.user_id, expected.entity.user_id);
    assert_eq!(result.entity.name, expected.entity.name);
    assert_eq!(result.entity.aliases, expected.entity.aliases);
    assert_eq!(
        format!("{:?}", result.entity.visibility),
        format!("{:?}", expected.entity.visibility)
    );
    assert_eq!(result.blocks.len(), expected.blocks.len());
    assert_eq!(result.neighbors.len(), expected.neighbors.len());
    let seen = seen_queries.lock().expect("lock should be available");
    assert_eq!(seen.len(), 1);
    assert_eq!(seen[0].max_block_level, 7);
}

#[tokio::test]
async fn get_entity_context_filters_readable_properties() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ContextGraphRepository {
            seen_queries: Arc::new(Mutex::new(Vec::new())),
            result: sample_entity_context_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    let result = app
        .get_entity_context(GetEntityContextQuery {
            entity_id: "entity-1".to_string(),
            user_id: "user-1".to_string(),
            max_block_level: 7,
        })
        .await
        .expect("query should succeed");

    assert_eq!(result.entity.id, "entity-1");
    assert_eq!(result.blocks.len(), 1);
}

#[tokio::test]
async fn get_entity_context_keeps_all_entity_properties_from_graph_context() {
    let seen_queries = Arc::new(Mutex::new(Vec::new()));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ContextGraphRepository {
            seen_queries: Arc::clone(&seen_queries),
            result: sample_entity_context_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    let result = app
        .get_entity_context(GetEntityContextQuery {
            entity_id: "entity-1".to_string(),
            user_id: "user-1".to_string(),
            max_block_level: 7,
        })
        .await
        .expect("query should succeed");

    assert_eq!(result.entity.properties.len(), 3);
    assert_eq!(result.entity.properties[0].key, "favorite_color");
    assert_eq!(result.entity.properties[1].key, "created_at");
    assert_eq!(result.entity.properties[2].key, "non_schema_extra");
}

#[tokio::test]
async fn get_entity_context_keeps_all_block_properties_from_graph_context() {
    let seen_queries = Arc::new(Mutex::new(Vec::new()));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ContextGraphRepository {
            seen_queries: Arc::clone(&seen_queries),
            result: sample_entity_context_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    let result = app
        .get_entity_context(GetEntityContextQuery {
            entity_id: "entity-1".to_string(),
            user_id: "user-1".to_string(),
            max_block_level: 7,
        })
        .await
        .expect("query should succeed");

    assert_eq!(result.blocks.len(), 1);
    assert_eq!(result.blocks[0].properties.len(), 4);
    assert_eq!(result.blocks[0].properties[0].key, "summary");
    assert_eq!(result.blocks[0].properties[1].key, "created_at");
    assert_eq!(result.blocks[0].properties[2].key, "text");
    assert_eq!(result.blocks[0].properties[3].key, "non_schema_extra");
    assert_eq!(result.blocks[0].neighbors.len(), 1);
    assert_eq!(result.blocks[0].neighbors[0].properties.len(), 1);
    assert_eq!(result.blocks[0].neighbors[0].properties[0].key, "since");
}

#[tokio::test]
async fn get_entity_context_applies_input_normalization_rules() {
    let seen_queries = Arc::new(Mutex::new(Vec::new()));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ContextGraphRepository {
            seen_queries: Arc::clone(&seen_queries),
            result: sample_entity_context_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    app.get_entity_context(GetEntityContextQuery {
        entity_id: " entity-1 ".to_string(),
        user_id: " user-1 ".to_string(),
        max_block_level: 99,
    })
    .await
    .expect("query should succeed");

    let seen = seen_queries.lock().expect("lock should be available");
    assert_eq!(seen.len(), 1);
    assert_eq!(seen[0].entity_id, "entity-1");
    assert_eq!(seen[0].user_id, "user-1");
    assert_eq!(seen[0].max_block_level, 32);
}

struct ListByTypeGraphRepository {
    seen_queries: Arc<Mutex<Vec<ListEntitiesByTypeQuery>>>,
    result: ListEntitiesByTypeResult,
}

#[async_trait]
impl GraphRepository for ListByTypeGraphRepository {
    async fn apply_delta_with_blocks(
        &self,
        _delta: &GraphDelta,
        _blocks: &[EmbeddedBlock],
    ) -> Result<()> {
        Ok(())
    }

    async fn common_root_graph_exists(&self) -> Result<bool> {
        Ok(true)
    }

    async fn user_graph_needs_initialization(&self, _user_id: &str) -> Result<bool> {
        Ok(false)
    }

    async fn mark_user_graph_initialized(
        &self,
        _user_id: &str,
        _node_ids: &UserInitGraphNodeIds,
    ) -> Result<()> {
        Ok(())
    }

    async fn get_user_init_graph_node_ids(
        &self,
        _user_id: &str,
    ) -> Result<Option<UserInitGraphNodeIds>> {
        Ok(None)
    }

    async fn update_person_name(&self, _person_entity_id: &str, _user_name: &str) -> Result<()> {
        Ok(())
    }

    async fn get_existing_block_context(
        &self,
        _block_id: &str,
        _user_id: &str,
        _visibility: Visibility,
    ) -> Result<Option<ExistingBlockContext>> {
        Ok(None)
    }

    async fn get_node_relationship_counts(&self, _node_id: &str) -> Result<NodeRelationshipCounts> {
        Ok(NodeRelationshipCounts::default())
    }

    async fn find_entity_candidates(
        &self,
        _query: &FindEntityCandidatesQuery,
        _query_vector: Option<&[f32]>,
    ) -> Result<RawEntityCandidateData> {
        Ok(RawEntityCandidateData::default())
    }

    async fn list_entities_by_type(
        &self,
        query: &ListEntitiesByTypeQuery,
    ) -> Result<ListEntitiesByTypeResult> {
        self.seen_queries
            .lock()
            .expect("lock should be available")
            .push(query.clone());
        Ok(self.result.clone())
    }

    async fn get_entity_context(
        &self,
        _query: &GetEntityContextQuery,
    ) -> Result<GetEntityContextResult> {
        Err(anyhow!("not implemented"))
    }

    async fn get_extraction_universes(&self, _user_id: &str) -> Result<Vec<ExtractionUniverse>> {
        Ok(Vec::new())
    }
}

fn sample_list_entities_by_type_result() -> ListEntitiesByTypeResult {
    ListEntitiesByTypeResult {
        entities: vec![crate::domain::TypedEntityListItem {
            id: "entity-1".to_string(),
            name: Some("Entity One".to_string()),
            updated_at: Some("2025-01-01T00:00:00Z".to_string()),
            description: Some("Example entity".to_string()),
        }],
        offset: 10,
        next_page_token: Some("next-token".to_string()),
    }
}

#[tokio::test]
async fn list_entities_by_type_rejects_blank_user_id() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ListByTypeGraphRepository {
            seen_queries: Arc::new(Mutex::new(Vec::new())),
            result: sample_list_entities_by_type_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .list_entities_by_type(ListEntitiesByTypeQuery {
            user_id: "   ".to_string(),
            type_id: "node.person".to_string(),
            page_size: Some(10),
            page_token: None,
            offset: Some(0),
        })
        .await
        .expect_err("blank user_id should fail");

    assert!(err.to_string().contains("user_id is required"));
}

#[tokio::test]
async fn list_entities_by_type_rejects_blank_type_id() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ListByTypeGraphRepository {
            seen_queries: Arc::new(Mutex::new(Vec::new())),
            result: sample_list_entities_by_type_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .list_entities_by_type(ListEntitiesByTypeQuery {
            user_id: "user-1".to_string(),
            type_id: "   ".to_string(),
            page_size: Some(10),
            page_token: None,
            offset: Some(0),
        })
        .await
        .expect_err("blank type_id should fail");

    assert!(err.to_string().contains("type_id is required"));
}

#[tokio::test]
async fn list_entities_by_type_normalizes_and_clamps_pagination() {
    let seen_queries = Arc::new(Mutex::new(Vec::new()));
    let expected = sample_list_entities_by_type_result();
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ListByTypeGraphRepository {
            seen_queries: Arc::clone(&seen_queries),
            result: expected.clone(),
        }),
        Arc::new(FakeEmbedder),
    );

    let result = app
        .list_entities_by_type(ListEntitiesByTypeQuery {
            user_id: " user-1 ".to_string(),
            type_id: " node.person ".to_string(),
            page_size: Some(999),
            page_token: Some("   ".to_string()),
            offset: None,
        })
        .await
        .expect("query should succeed");

    assert_eq!(result.entities.len(), expected.entities.len());
    assert_eq!(result.offset, expected.offset);
    assert_eq!(result.next_page_token, expected.next_page_token);

    let seen = seen_queries.lock().expect("lock should be available");
    assert_eq!(seen.len(), 1);
    assert_eq!(seen[0].user_id, "user-1");
    assert_eq!(seen[0].type_id, "node.person");
    assert_eq!(seen[0].page_size, Some(LIST_ENTITIES_BY_TYPE_MAX_PAGE_SIZE));
    assert_eq!(seen[0].page_token, None);
    assert_eq!(seen[0].offset, Some(0));
}

#[tokio::test]
async fn list_entities_by_type_derives_offset_from_page_token() {
    let seen_queries = Arc::new(Mutex::new(Vec::new()));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ListByTypeGraphRepository {
            seen_queries: Arc::clone(&seen_queries),
            result: sample_list_entities_by_type_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    app.list_entities_by_type(ListEntitiesByTypeQuery {
        user_id: "user-1".to_string(),
        type_id: "node.person".to_string(),
        page_size: Some(20),
        page_token: Some(" 77 ".to_string()),
        offset: None,
    })
    .await
    .expect("query should succeed");

    let seen = seen_queries.lock().expect("lock should be available");
    assert_eq!(seen.len(), 1);
    assert_eq!(seen[0].page_token, Some("77".to_string()));
    assert_eq!(seen[0].offset, Some(77));
}

#[tokio::test]
async fn list_entities_by_type_rejects_invalid_page_token() {
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ListByTypeGraphRepository {
            seen_queries: Arc::new(Mutex::new(Vec::new())),
            result: sample_list_entities_by_type_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    let err = app
        .list_entities_by_type(ListEntitiesByTypeQuery {
            user_id: "user-1".to_string(),
            type_id: "node.person".to_string(),
            page_size: Some(20),
            page_token: Some("cursor-not-a-number".to_string()),
            offset: None,
        })
        .await
        .expect_err("invalid cursor should fail");

    assert!(err
        .to_string()
        .contains("page_token must be a valid pagination cursor"));
}
#[tokio::test]
async fn list_entities_by_type_applies_default_page_size() {
    let seen_queries = Arc::new(Mutex::new(Vec::new()));
    let app = KnowledgeApplication::new(
        Arc::new(FakeSchemaRepo::new()),
        Arc::new(ListByTypeGraphRepository {
            seen_queries: Arc::clone(&seen_queries),
            result: sample_list_entities_by_type_result(),
        }),
        Arc::new(FakeEmbedder),
    );

    app.list_entities_by_type(ListEntitiesByTypeQuery {
        user_id: "user-1".to_string(),
        type_id: "node.person".to_string(),
        page_size: None,
        page_token: Some(" tok-1 ".to_string()),
        offset: Some(42),
    })
    .await
    .expect("query should succeed");

    let seen = seen_queries.lock().expect("lock should be available");
    assert_eq!(seen.len(), 1);
    assert_eq!(
        seen[0].page_size,
        Some(LIST_ENTITIES_BY_TYPE_DEFAULT_PAGE_SIZE)
    );
    assert_eq!(seen[0].page_token, Some("tok-1".to_string()));
    assert_eq!(seen[0].offset, Some(42));
}

#[test]
fn extraction_builder_excludes_abstract_node_type() {
    let schema = crate::domain::FullSchema {
        node_types: vec![
            crate::domain::SchemaNodeTypeHydrated {
                schema_type: crate::domain::SchemaType {
                    id: "node".to_string(),
                    kind: "node".to_string(),
                    name: "Node".to_string(),
                    description: "Abstract".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![],
            },
            crate::domain::SchemaNodeTypeHydrated {
                schema_type: crate::domain::SchemaType {
                    id: "node.entity".to_string(),
                    kind: "node".to_string(),
                    name: "Entity".to_string(),
                    description: "Root".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![crate::domain::TypeInheritance {
                    child_type_id: "node.entity".to_string(),
                    parent_type_id: "node".to_string(),
                    description: "inherits".to_string(),
                    active: true,
                }],
            },
        ],
        edge_types: vec![],
    };

    let entity_types = build_extraction_entity_types_from_schema(
        schema,
        ExtractionSchemaOptions {
            include_inactive: false,
        },
    );

    assert!(entity_types.iter().all(|entity| entity.type_id != "node"));
}

#[test]
fn extraction_builder_flattens_multi_level_inheritance_chain() {
    let schema = crate::domain::FullSchema {
        node_types: vec![
            crate::domain::SchemaNodeTypeHydrated {
                schema_type: crate::domain::SchemaType {
                    id: "node.entity".to_string(),
                    kind: "node".to_string(),
                    name: "Entity".to_string(),
                    description: "Root".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![],
            },
            crate::domain::SchemaNodeTypeHydrated {
                schema_type: crate::domain::SchemaType {
                    id: "node.concept".to_string(),
                    kind: "node".to_string(),
                    name: "Concept".to_string(),
                    description: "Concept".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![crate::domain::TypeInheritance {
                    child_type_id: "node.concept".to_string(),
                    parent_type_id: "node.entity".to_string(),
                    description: "inherits".to_string(),
                    active: true,
                }],
            },
            crate::domain::SchemaNodeTypeHydrated {
                schema_type: crate::domain::SchemaType {
                    id: "node.book".to_string(),
                    kind: "node".to_string(),
                    name: "Book".to_string(),
                    description: "Book".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![crate::domain::TypeInheritance {
                    child_type_id: "node.book".to_string(),
                    parent_type_id: "node.concept".to_string(),
                    description: "inherits".to_string(),
                    active: true,
                }],
            },
        ],
        edge_types: vec![],
    };

    let entity_types = build_extraction_entity_types_from_schema(
        schema,
        ExtractionSchemaOptions {
            include_inactive: false,
        },
    );

    let book = entity_types
        .iter()
        .find(|entity| entity.type_id == "node.book")
        .expect("book type should exist");
    assert_eq!(
        book.inheritance_chain,
        vec!["node.entity", "node.concept", "node.book"]
    );
}

#[test]
fn extraction_builder_orders_types_and_edges_deterministically() {
    let schema = crate::domain::FullSchema {
        node_types: vec![
            crate::domain::SchemaNodeTypeHydrated {
                schema_type: crate::domain::SchemaType {
                    id: "node.zeta".to_string(),
                    kind: "node".to_string(),
                    name: "Zeta".to_string(),
                    description: "Z".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![],
            },
            crate::domain::SchemaNodeTypeHydrated {
                schema_type: crate::domain::SchemaType {
                    id: "node.alpha".to_string(),
                    kind: "node".to_string(),
                    name: "Alpha".to_string(),
                    description: "A".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![],
            },
        ],
        edge_types: vec![crate::domain::SchemaEdgeTypeHydrated {
            schema_type: crate::domain::SchemaType {
                id: "edge.rel".to_string(),
                kind: "edge".to_string(),
                name: "REL".to_string(),
                description: "rel".to_string(),
                active: true,
            },
            properties: vec![],
            rules: vec![
                crate::domain::EdgeEndpointRule {
                    edge_type_id: "edge.rel".to_string(),
                    from_node_type_id: "node.alpha".to_string(),
                    to_node_type_id: "node.zeta".to_string(),
                    active: true,
                    description: "a->z".to_string(),
                },
                crate::domain::EdgeEndpointRule {
                    edge_type_id: "edge.rel".to_string(),
                    from_node_type_id: "node.alpha".to_string(),
                    to_node_type_id: "node.alpha".to_string(),
                    active: true,
                    description: "a->a".to_string(),
                },
            ],
        }],
    };

    let entity_types = build_extraction_entity_types_from_schema(
        schema,
        ExtractionSchemaOptions {
            include_inactive: false,
        },
    );

    assert_eq!(
        entity_types
            .iter()
            .map(|item| item.type_id.as_str())
            .collect::<Vec<_>>(),
        vec!["node.alpha", "node.zeta"]
    );
}

fn sample_entity_context_result() -> GetEntityContextResult {
    GetEntityContextResult {
        entity: crate::domain::EntityContextEntitySnapshot {
            id: "entity-1".to_string(),
            type_id: "node.person".to_string(),
            user_id: "user-1".to_string(),
            visibility: Visibility::Private,
            name: None,
            aliases: vec![],
            created_at: None,
            updated_at: None,
            properties: vec![
                PropertyValue {
                    key: "favorite_color".to_string(),
                    value: crate::domain::PropertyScalar::String("blue".to_string()),
                },
                PropertyValue {
                    key: "created_at".to_string(),
                    value: crate::domain::PropertyScalar::String(
                        "2024-01-01T00:00:00Z".to_string(),
                    ),
                },
                PropertyValue {
                    key: "non_schema_extra".to_string(),
                    value: crate::domain::PropertyScalar::String("extra".to_string()),
                },
            ],
        },
        blocks: vec![crate::domain::EntityContextBlockItem {
            id: "block-1".to_string(),
            type_id: "block.note".to_string(),
            block_level: 0,
            text: Some("Top level text".to_string()),
            created_at: None,
            updated_at: None,
            properties: vec![
                PropertyValue {
                    key: "summary".to_string(),
                    value: PropertyScalar::String("allowed".to_string()),
                },
                PropertyValue {
                    key: "created_at".to_string(),
                    value: PropertyScalar::String("2024-01-01T00:00:00Z".to_string()),
                },
                PropertyValue {
                    key: "text".to_string(),
                    value: PropertyScalar::String("duplicate text".to_string()),
                },
                PropertyValue {
                    key: "non_schema_extra".to_string(),
                    value: PropertyScalar::String("extra".to_string()),
                },
            ],
            parent_block_id: None,
            neighbors: vec![crate::domain::EntityContextNeighborItem {
                direction: crate::domain::NeighborDirection::Outgoing,
                edge_type: "edge.related_to".to_string(),
                properties: vec![PropertyValue {
                    key: "since".to_string(),
                    value: PropertyScalar::String("2024".to_string()),
                }],
                other_entity: crate::domain::EntityContextOtherEntity {
                    id: "entity-2".to_string(),
                    description: Some("neighbor".to_string()),
                    name: Some("Neighbor Entity".to_string()),
                },
            }],
        }],
        neighbors: vec![],
    }
}
