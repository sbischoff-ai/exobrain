use super::{
    entity_type_property_context_options_from_request, extraction_options_from_entity_request,
    to_proto_extraction_edge_type, to_proto_extraction_entity_type, to_proto_extraction_universe,
    to_proto_property_context, KnowledgeGrpcService,
};
use crate::application::KnowledgeApplication;
use crate::application::{
    build_extraction_entity_types_from_input, ExtractionEdgeType, ExtractionEntityType,
    ExtractionPropertyContext, ExtractionSchemaBuildInput, ExtractionSchemaOptions,
    ExtractionUniverseContext,
};
use crate::domain::{
    EdgeEndpointRule, FullSchema, SchemaEdgeTypeHydrated, SchemaNodeTypeHydrated, SchemaType,
};
use crate::ports::{Embedder, GraphRepository, SchemaRepository};
use crate::presentation::upsert_delta_json_schema::UPSERT_GRAPH_DELTA_SCHEMA_ID;
use crate::transport::proto::knowledge_interface_server::KnowledgeInterface;
use crate::transport::proto::{
    GetEdgeExtractionSchemaContextRequest, GetEntityExtractionSchemaContextRequest,
    GetEntityTypePropertyContextRequest, GetUpsertGraphDeltaJsonSchemaRequest,
};
use anyhow::{anyhow, Result};
use async_trait::async_trait;
use serde_json::Value;
use std::sync::Arc;
use tonic::Request;

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

struct NoopSchemaRepository;

#[async_trait]
impl SchemaRepository for NoopSchemaRepository {
    async fn get_by_kind(&self, _kind: crate::domain::SchemaKind) -> Result<Vec<SchemaType>> {
        Err(anyhow!("not implemented"))
    }
    async fn upsert(&self, _schema_type: &SchemaType) -> Result<SchemaType> {
        Err(anyhow!("not implemented"))
    }
    async fn get_type_inheritance(&self) -> Result<Vec<crate::domain::TypeInheritance>> {
        Err(anyhow!("not implemented"))
    }
    async fn get_all_properties(&self) -> Result<Vec<crate::domain::TypeProperty>> {
        Err(anyhow!("not implemented"))
    }
    async fn get_edge_endpoint_rules(&self) -> Result<Vec<EdgeEndpointRule>> {
        Err(anyhow!("not implemented"))
    }
    async fn get_schema_type(&self, _id: &str) -> Result<Option<SchemaType>> {
        Err(anyhow!("not implemented"))
    }
    async fn get_parent_for_child(&self, _child_type_id: &str) -> Result<Option<String>> {
        Err(anyhow!("not implemented"))
    }
    async fn is_descendant_of_entity(&self, _node_type_id: &str) -> Result<bool> {
        Err(anyhow!("not implemented"))
    }
    async fn upsert_inheritance(
        &self,
        _child_type_id: &str,
        _parent_type_id: &str,
        _description: &str,
    ) -> Result<()> {
        Err(anyhow!("not implemented"))
    }
    async fn upsert_type_property(
        &self,
        _owner_type_id: &str,
        _property: &crate::domain::UpsertSchemaTypePropertyInput,
    ) -> Result<()> {
        Err(anyhow!("not implemented"))
    }
}

struct NoopGraphRepository;

#[async_trait]
impl GraphRepository for NoopGraphRepository {
    async fn apply_delta_with_blocks(
        &self,
        _delta: &crate::domain::GraphDelta,
        _blocks: &[crate::domain::EmbeddedBlock],
    ) -> Result<()> {
        Err(anyhow!("not implemented"))
    }
    async fn common_root_graph_exists(&self) -> Result<bool> {
        Err(anyhow!("not implemented"))
    }
    async fn user_graph_needs_initialization(&self, _user_id: &str) -> Result<bool> {
        Err(anyhow!("not implemented"))
    }
    async fn mark_user_graph_initialized(
        &self,
        _user_id: &str,
        _node_ids: &crate::domain::UserInitGraphNodeIds,
    ) -> Result<()> {
        Err(anyhow!("not implemented"))
    }
    async fn get_user_init_graph_node_ids(
        &self,
        _user_id: &str,
    ) -> Result<Option<crate::domain::UserInitGraphNodeIds>> {
        Err(anyhow!("not implemented"))
    }
    async fn update_person_name(&self, _person_entity_id: &str, _user_name: &str) -> Result<()> {
        Err(anyhow!("not implemented"))
    }
    async fn get_existing_block_context(
        &self,
        _block_id: &str,
        _user_id: &str,
        _visibility: crate::domain::Visibility,
    ) -> Result<Option<crate::domain::ExistingBlockContext>> {
        Err(anyhow!("not implemented"))
    }
    async fn get_node_relationship_counts(
        &self,
        _node_id: &str,
    ) -> Result<crate::domain::NodeRelationshipCounts> {
        Err(anyhow!("not implemented"))
    }
    async fn find_entity_candidates(
        &self,
        _query: &crate::domain::FindEntityCandidatesQuery,
        _query_vector: Option<&[f32]>,
    ) -> Result<Vec<crate::domain::EntityCandidate>> {
        Err(anyhow!("not implemented"))
    }
    async fn get_entity_context(
        &self,
        _query: &crate::domain::GetEntityContextQuery,
    ) -> Result<crate::domain::GetEntityContextResult> {
        Err(anyhow!("not implemented"))
    }
    async fn list_entities_by_type(
        &self,
        _query: &crate::domain::ListEntitiesByTypeQuery,
    ) -> Result<crate::domain::ListEntitiesByTypeResult> {
        Err(anyhow!("not implemented"))
    }
    async fn get_extraction_universes(
        &self,
        _user_id: &str,
    ) -> Result<Vec<crate::domain::ExtractionUniverse>> {
        Err(anyhow!("not implemented"))
    }
}

struct NoopEmbedder;

#[async_trait]
impl Embedder for NoopEmbedder {
    async fn embed_texts(&self, _texts: &[String]) -> Result<Vec<Vec<f32>>> {
        Err(anyhow!("not implemented"))
    }
}

fn make_service() -> KnowledgeGrpcService {
    KnowledgeGrpcService {
        app: Arc::new(KnowledgeApplication::new(
            Arc::new(NoopSchemaRepository),
            Arc::new(NoopGraphRepository),
            Arc::new(NoopEmbedder),
        )),
    }
}

#[test]
fn extraction_schema_context_filters_inactive_types_and_rules_by_default() {
    let schema = FullSchema {
        node_types: vec![
            SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.entity".to_string(),
                    kind: "node".to_string(),
                    name: "Entity".to_string(),
                    description: "Root entity".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![],
            },
            SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.person".to_string(),
                    kind: "node".to_string(),
                    name: "Person".to_string(),
                    description: "Person entity".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![crate::domain::TypeInheritance {
                    child_type_id: "node.person".to_string(),
                    parent_type_id: "node.entity".to_string(),
                    description: "inherits".to_string(),
                    active: true,
                }],
            },
            SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.deprecated".to_string(),
                    kind: "node".to_string(),
                    name: "Deprecated".to_string(),
                    description: "Inactive type".to_string(),
                    active: false,
                },
                properties: vec![],
                parents: vec![],
            },
        ],
        edge_types: vec![SchemaEdgeTypeHydrated {
            schema_type: SchemaType {
                id: "edge.related_to".to_string(),
                kind: "edge".to_string(),
                name: "RELATED_TO".to_string(),
                description: "Relationship".to_string(),
                active: true,
            },
            properties: vec![],
            rules: vec![
                EdgeEndpointRule {
                    edge_type_id: "edge.related_to".to_string(),
                    from_node_type_id: "node.person".to_string(),
                    to_node_type_id: "node.entity".to_string(),
                    active: true,
                    description: "active rule".to_string(),
                },
                EdgeEndpointRule {
                    edge_type_id: "edge.related_to".to_string(),
                    from_node_type_id: "node.person".to_string(),
                    to_node_type_id: "node.deprecated".to_string(),
                    active: false,
                    description: "inactive rule".to_string(),
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

    assert_eq!(entity_types.len(), 2);
    let person = entity_types
        .iter()
        .find(|entity| entity.type_id == "node.person")
        .expect("person type must be present");
    assert_eq!(person.inheritance_chain, vec!["node.entity", "node.person"]);
    assert_eq!(person.outgoing_edges.len(), 1);
    assert_eq!(person.outgoing_edges[0].other_entity_type_id, "node.entity");
}

#[test]
fn extraction_schema_context_is_deterministically_sorted() {
    let schema = FullSchema {
        node_types: vec![
            SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.zeta".to_string(),
                    kind: "node".to_string(),
                    name: "Zeta".to_string(),
                    description: "Z".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![crate::domain::TypeInheritance {
                    child_type_id: "node.zeta".to_string(),
                    parent_type_id: "node.entity".to_string(),
                    description: "inherits".to_string(),
                    active: true,
                }],
            },
            SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.entity".to_string(),
                    kind: "node".to_string(),
                    name: "Entity".to_string(),
                    description: "Root".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![],
            },
            SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.alpha".to_string(),
                    kind: "node".to_string(),
                    name: "Alpha".to_string(),
                    description: "A".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![crate::domain::TypeInheritance {
                    child_type_id: "node.alpha".to_string(),
                    parent_type_id: "node.entity".to_string(),
                    description: "inherits".to_string(),
                    active: true,
                }],
            },
        ],
        edge_types: vec![SchemaEdgeTypeHydrated {
            schema_type: SchemaType {
                id: "edge.rel".to_string(),
                kind: "edge".to_string(),
                name: "REL".to_string(),
                description: "Relationship".to_string(),
                active: true,
            },
            properties: vec![],
            rules: vec![
                EdgeEndpointRule {
                    edge_type_id: "edge.rel".to_string(),
                    from_node_type_id: "node.alpha".to_string(),
                    to_node_type_id: "node.zeta".to_string(),
                    active: true,
                    description: "alpha->zeta".to_string(),
                },
                EdgeEndpointRule {
                    edge_type_id: "edge.rel".to_string(),
                    from_node_type_id: "node.alpha".to_string(),
                    to_node_type_id: "node.entity".to_string(),
                    active: true,
                    description: "alpha->entity".to_string(),
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
            .map(|entity| entity.type_id.as_str())
            .collect::<Vec<_>>(),
        vec!["node.alpha", "node.entity", "node.zeta"]
    );

    let alpha = entity_types
        .iter()
        .find(|entity| entity.type_id == "node.alpha")
        .expect("alpha type should exist");

    assert_eq!(alpha.inheritance_chain, vec!["node.entity", "node.alpha"]);
    assert_eq!(
        alpha
            .outgoing_edges
            .iter()
            .map(|edge| edge.other_entity_type_id.as_str())
            .collect::<Vec<_>>(),
        vec!["node.entity", "node.zeta"]
    );
}

#[test]
fn extraction_request_optional_flags_default_to_false() {
    let request = GetEntityExtractionSchemaContextRequest {
        include_inactive: None,
        user_id: "user-1".to_string(),
    };

    let options = extraction_options_from_entity_request(&request);

    assert!(!options.include_inactive);
}

#[test]
fn extraction_request_optional_flags_respect_explicit_true() {
    let request = GetEntityExtractionSchemaContextRequest {
        include_inactive: Some(true),
        user_id: "user-1".to_string(),
    };

    let options = extraction_options_from_entity_request(&request);

    assert!(options.include_inactive);
}

#[test]
fn edge_extraction_request_uses_new_entity_type_fields() {
    let request = GetEdgeExtractionSchemaContextRequest {
        first_entity_type: "node.person".to_string(),
        second_entity_type: "node.task".to_string(),
        include_inactive: Some(true),
        user_id: "user-1".to_string(),
    };

    let options = super::extraction_options_from_edge_request(&request);

    assert!(options.include_inactive);
    assert_eq!(request.first_entity_type, "node.person");
    assert_eq!(request.second_entity_type, "node.task");
}

#[test]
fn entity_type_property_context_request_defaults_include_inherited() {
    let request = GetEntityTypePropertyContextRequest {
        type_id: "node.person".to_string(),
        include_inactive: None,
        include_inherited: None,
        user_id: None,
    };

    let options = entity_type_property_context_options_from_request(&request);

    assert!(!options.include_inactive);
    assert!(options.include_inherited);
}

#[test]
fn proto_mapping_preserves_property_context_shape() {
    let proto = to_proto_property_context(ExtractionPropertyContext {
        prop_name: "name".to_string(),
        value_type: "string".to_string(),
        required: true,
        readable: true,
        writable: false,
        description: "Display name".to_string(),
        declared_on_type_id: "node.entity".to_string(),
    });

    assert_eq!(proto.prop_name, "name");
    assert_eq!(proto.value_type, "string");
    assert!(proto.required);
    assert!(proto.readable);
    assert!(!proto.writable);
    assert_eq!(proto.description, "Display name");
    assert_eq!(proto.declared_on_type_id, "node.entity");
}

#[test]
fn proto_mapping_preserves_extraction_universe_shape() {
    let proto = to_proto_extraction_universe(ExtractionUniverseContext {
        id: "universe-1".to_string(),
        name: "Middle-earth".to_string(),
        described_by_text: Some("Fictional setting".to_string()),
    });

    assert_eq!(proto.id, "universe-1");
    assert_eq!(proto.name, "Middle-earth");
    assert_eq!(
        proto.described_by_text.as_deref(),
        Some("Fictional setting")
    );
}

#[test]
fn proto_mapping_preserves_extraction_entity_shape() {
    let proto = to_proto_extraction_entity_type(ExtractionEntityType {
        type_id: "node.person".to_string(),
        name: "Person".to_string(),
        description: "A person".to_string(),
        inheritance_chain: vec!["node.entity".to_string(), "node.person".to_string()],
        outgoing_edges: vec![],
        incoming_edges: vec![],
    });

    assert_eq!(proto.type_id, "node.person");
    assert_eq!(proto.inheritance_chain, vec!["node.entity", "node.person"]);
}

#[test]
fn proto_mapping_preserves_extraction_edge_type_shape() {
    let proto = to_proto_extraction_edge_type(ExtractionEdgeType {
        edge_type_id: "edge.assigned_to".to_string(),
        edge_name: "ASSIGNED_TO".to_string(),
        edge_description: "assignment".to_string(),
        source_entity_type_id: "node.person".to_string(),
        target_entity_type_id: "node.task".to_string(),
    });

    assert_eq!(proto.edge_type_id, "edge.assigned_to");
    assert_eq!(proto.source_entity_type_id, "node.person");
    assert_eq!(proto.target_entity_type_id, "node.task");
}

#[test]
fn entity_type_property_context_rejects_blank_type_id() {
    let schema = FullSchema {
        node_types: vec![],
        edge_types: vec![],
    };
    let request = GetEntityTypePropertyContextRequest {
        type_id: "   ".to_string(),
        include_inactive: None,
        include_inherited: None,
        user_id: None,
    };

    let err = crate::application::build_entity_type_property_context(
        schema,
        &request.type_id,
        crate::application::EntityTypePropertyContextOptions {
            include_inactive: request.include_inactive.unwrap_or(false),
            include_inherited: request.include_inherited.unwrap_or(true),
        },
    )
    .expect_err("blank type_id should fail");
    assert!(err.to_string().contains("type_id is required"));
}

#[test]
fn entity_type_property_context_rejects_unknown_type_id() {
    let schema = FullSchema {
        node_types: vec![SchemaNodeTypeHydrated {
            schema_type: SchemaType {
                id: "node.person".to_string(),
                kind: "node".to_string(),
                name: "Person".to_string(),
                description: "Person".to_string(),
                active: true,
            },
            properties: vec![],
            parents: vec![],
        }],
        edge_types: vec![],
    };
    let request = GetEntityTypePropertyContextRequest {
        type_id: "node.unknown".to_string(),
        include_inactive: None,
        include_inherited: None,
        user_id: None,
    };

    let err = crate::application::build_entity_type_property_context(
        schema,
        &request.type_id,
        crate::application::EntityTypePropertyContextOptions {
            include_inactive: request.include_inactive.unwrap_or(false),
            include_inherited: request.include_inherited.unwrap_or(true),
        },
    )
    .expect_err("unknown type_id should fail");
    assert!(err.to_string().contains("unknown type_id"));
}

#[test]
fn entity_type_property_context_sorts_properties_and_includes_inherited() {
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
                properties: vec![crate::domain::TypeProperty {
                    owner_type_id: "node.entity".to_string(),
                    prop_name: "zeta".to_string(),
                    value_type: "string".to_string(),
                    required: false,
                    readable: true,
                    writable: true,
                    active: true,
                    description: "z".to_string(),
                }],
                parents: vec![],
            },
            SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.person".to_string(),
                    kind: "node".to_string(),
                    name: "Person".to_string(),
                    description: "Person".to_string(),
                    active: true,
                },
                properties: vec![crate::domain::TypeProperty {
                    owner_type_id: "node.person".to_string(),
                    prop_name: "alpha".to_string(),
                    value_type: "string".to_string(),
                    required: true,
                    readable: true,
                    writable: false,
                    active: true,
                    description: "a".to_string(),
                }],
                parents: vec![crate::domain::TypeInheritance {
                    child_type_id: "node.person".to_string(),
                    parent_type_id: "node.entity".to_string(),
                    description: "inherits".to_string(),
                    active: true,
                }],
            },
        ],
        edge_types: vec![],
    };
    let request = GetEntityTypePropertyContextRequest {
        type_id: "node.person".to_string(),
        include_inactive: Some(false),
        include_inherited: Some(true),
        user_id: None,
    };

    let reply = crate::application::build_entity_type_property_context(
        schema,
        &request.type_id,
        crate::application::EntityTypePropertyContextOptions {
            include_inactive: request.include_inactive.unwrap_or(false),
            include_inherited: request.include_inherited.unwrap_or(true),
        },
    )
    .expect("valid request should succeed");

    assert_eq!(reply.type_id, "node.person");
    assert_eq!(reply.type_name, "Person");
    assert_eq!(reply.inheritance_chain, vec!["node.entity", "node.person"]);
    assert_eq!(
        reply
            .properties
            .iter()
            .map(|prop| prop.prop_name.as_str())
            .collect::<Vec<_>>(),
        vec!["alpha", "zeta"]
    );
    assert_eq!(reply.properties[0].declared_on_type_id, "node.person");
    assert_eq!(reply.properties[1].declared_on_type_id, "node.entity");
}

fn parse_schema_json(schema: &str) -> Value {
    serde_json::from_str(schema).expect("schema payload should be valid JSON")
}

#[tokio::test]
async fn get_upsert_graph_delta_json_schema_returns_parseable_json_payload() {
    let service = make_service();

    let reply = service
        .get_upsert_graph_delta_json_schema(Request::new(GetUpsertGraphDeltaJsonSchemaRequest {}))
        .await
        .expect("rpc should succeed")
        .into_inner();

    let parsed = parse_schema_json(&reply.json_schema);
    assert!(parsed.is_object());
    assert_eq!(
        reply.schema_id.as_deref(),
        Some(UPSERT_GRAPH_DELTA_SCHEMA_ID)
    );
}

#[tokio::test]
async fn get_upsert_graph_delta_json_schema_includes_core_root_fields() {
    let service = make_service();

    let reply = service
        .get_upsert_graph_delta_json_schema(Request::new(GetUpsertGraphDeltaJsonSchemaRequest {}))
        .await
        .expect("rpc should succeed")
        .into_inner();

    let schema = parse_schema_json(&reply.json_schema);
    let properties = schema["properties"]
        .as_object()
        .expect("schema properties must be an object");
    for key in ["universes", "entities", "blocks", "edges"] {
        assert!(properties.contains_key(key), "missing root property {key}");
    }
}

#[tokio::test]
async fn get_upsert_graph_delta_json_schema_property_value_uses_oneof() {
    let service = make_service();

    let reply = service
        .get_upsert_graph_delta_json_schema(Request::new(GetUpsertGraphDeltaJsonSchemaRequest {}))
        .await
        .expect("rpc should succeed")
        .into_inner();

    let property_value = &parse_schema_json(&reply.json_schema)["properties"]["entities"]["items"]
        ["properties"]["properties"]["items"];

    assert_eq!(property_value["required"], serde_json::json!(["key"]));
    let one_of = property_value["oneOf"]
        .as_array()
        .expect("property value oneOf must be an array");
    assert_eq!(one_of.len(), 6);
}

#[tokio::test]
async fn get_upsert_graph_delta_json_schema_includes_visibility_enum_values() {
    let service = make_service();

    let reply = service
        .get_upsert_graph_delta_json_schema(Request::new(GetUpsertGraphDeltaJsonSchemaRequest {}))
        .await
        .expect("rpc should succeed")
        .into_inner();

    let schema = parse_schema_json(&reply.json_schema);
    let enum_values = schema["properties"]["entities"]["items"]["properties"]["visibility"]["enum"]
        .as_array()
        .expect("visibility enum should be an array")
        .iter()
        .filter_map(|value| value.as_str())
        .collect::<Vec<_>>();

    assert!(enum_values.contains(&"PRIVATE"));
    assert!(enum_values.contains(&"SHARED"));
}

#[tokio::test]
async fn get_upsert_graph_delta_json_schema_snapshot_stability_fragments() {
    let service = make_service();

    let reply = service
        .get_upsert_graph_delta_json_schema(Request::new(GetUpsertGraphDeltaJsonSchemaRequest {}))
        .await
        .expect("rpc should succeed")
        .into_inner();

    assert!(reply.json_schema.contains(
        r#""required": [
    "universes",
    "entities",
    "blocks",
    "edges"
  ]"#
    ));
    assert!(reply.json_schema.contains(r#""oneOf": ["#));
    assert!(reply.json_schema.contains(r#""string_value""#));
    assert!(reply.json_schema.contains(r#""enum": ["#));
    assert!(reply.json_schema.contains(r#""PRIVATE""#));
    assert!(reply.json_schema.contains(r#""SHARED""#));
}
