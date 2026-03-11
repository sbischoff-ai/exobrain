use super::{KnowledgeGrpcService, KnowledgeInterface};
use crate::application::KnowledgeApplication;
use crate::domain::{
    EdgeEndpointRule, FullSchema, SchemaKind, SchemaType, TypeInheritance, TypeProperty,
};
use crate::ports::{Embedder, GraphRepository, SchemaRepository, TypeVectorRepository};
use crate::presentation::upsert_delta_json_schema::UPSERT_GRAPH_DELTA_SCHEMA_ID;
use crate::transport::proto::{
    FindEdgeTypeCandidatesRequest, FindNodeTypeCandidatesRequest,
    GetEdgeExtractionSchemaContextRequest, GetEntityExtractionSchemaContextRequest,
    GetEntityTypePropertyContextRequest, GetUpsertGraphDeltaJsonSchemaRequest, HealthRequest,
};
use anyhow::{anyhow, Result};
use async_trait::async_trait;
use serde_json::Value;
use std::sync::Arc;
use tonic::{Code, Request};

#[derive(Clone)]
struct SchemaRepoFixture {
    node_types: Vec<SchemaType>,
    edge_types: Vec<SchemaType>,
    inheritance: Vec<TypeInheritance>,
    properties: Vec<TypeProperty>,
    edge_rules: Vec<EdgeEndpointRule>,
    fail_get_by_kind: bool,
}

impl Default for SchemaRepoFixture {
    fn default() -> Self {
        Self {
            node_types: vec![
                SchemaType {
                    id: "node.entity".to_string(),
                    kind: "node".to_string(),
                    name: "Entity".to_string(),
                    description: "Root".to_string(),
                    active: true,
                },
                SchemaType {
                    id: "node.person".to_string(),
                    kind: "node".to_string(),
                    name: "Person".to_string(),
                    description: "Human".to_string(),
                    active: true,
                },
                SchemaType {
                    id: "node.task".to_string(),
                    kind: "node".to_string(),
                    name: "Task".to_string(),
                    description: "Work item".to_string(),
                    active: true,
                },
                SchemaType {
                    id: "node.legacy".to_string(),
                    kind: "node".to_string(),
                    name: "Legacy".to_string(),
                    description: "inactive".to_string(),
                    active: false,
                },
            ],
            edge_types: vec![SchemaType {
                id: "edge.assigned_to".to_string(),
                kind: "edge".to_string(),
                name: "ASSIGNED_TO".to_string(),
                description: "assignment".to_string(),
                active: true,
            }],
            inheritance: vec![TypeInheritance {
                child_type_id: "node.person".to_string(),
                parent_type_id: "node.entity".to_string(),
                description: "inherits".to_string(),
                active: true,
            }],
            properties: vec![
                TypeProperty {
                    owner_type_id: "node.entity".to_string(),
                    prop_name: "name".to_string(),
                    value_type: "string".to_string(),
                    required: true,
                    readable: true,
                    writable: true,
                    active: true,
                    description: "display name".to_string(),
                },
                TypeProperty {
                    owner_type_id: "node.person".to_string(),
                    prop_name: "nickname".to_string(),
                    value_type: "string".to_string(),
                    required: false,
                    readable: true,
                    writable: true,
                    active: true,
                    description: "nickname".to_string(),
                },
            ],
            edge_rules: vec![EdgeEndpointRule {
                edge_type_id: "edge.assigned_to".to_string(),
                from_node_type_id: "node.person".to_string(),
                to_node_type_id: "node.task".to_string(),
                active: true,
                description: "person assigned to task".to_string(),
            }],
            fail_get_by_kind: false,
        }
    }
}

#[async_trait]
impl SchemaRepository for SchemaRepoFixture {
    async fn get_by_kind(&self, kind: SchemaKind) -> Result<Vec<SchemaType>> {
        if self.fail_get_by_kind {
            return Err(anyhow!("schema backend unavailable"));
        }
        Ok(match kind {
            SchemaKind::Node => self.node_types.clone(),
            SchemaKind::Edge => self.edge_types.clone(),
        })
    }

    async fn upsert(&self, _schema_type: &SchemaType) -> Result<SchemaType> {
        Err(anyhow!("not implemented"))
    }
    async fn get_type_inheritance(&self) -> Result<Vec<TypeInheritance>> {
        Ok(self.inheritance.clone())
    }
    async fn get_all_properties(&self) -> Result<Vec<TypeProperty>> {
        Ok(self.properties.clone())
    }
    async fn get_edge_endpoint_rules(&self) -> Result<Vec<EdgeEndpointRule>> {
        Ok(self.edge_rules.clone())
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
    async fn delete_schema_type(&self, _id: &str) -> Result<()> {
        Err(anyhow!("not implemented"))
    }
}

#[derive(Clone, Default)]
struct GraphRepoFixture {
    universes: Vec<crate::domain::ExtractionUniverse>,
    fail_universes: bool,
}

#[async_trait]
impl GraphRepository for GraphRepoFixture {
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
    ) -> Result<crate::domain::RawEntityCandidateData> {
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
        if self.fail_universes {
            return Err(anyhow!("graph backend unavailable"));
        }
        Ok(self.universes.clone())
    }
}

#[derive(Clone, Default)]
struct TypeVectorRepoFixture {
    node_candidates: Vec<crate::domain::TypeCandidate>,
    edge_candidates: Vec<crate::domain::TypeCandidate>,
}

#[async_trait]
impl TypeVectorRepository for TypeVectorRepoFixture {
    async fn upsert_schema_type_vector(
        &self,
        _schema_type: &SchemaType,
        _vector: &[f32],
    ) -> Result<()> {
        Err(anyhow!("not implemented"))
    }

    async fn search_node_type_candidates(
        &self,
        _vector: &[f32],
        _limit: u64,
    ) -> Result<Vec<crate::domain::TypeCandidate>> {
        Ok(self.node_candidates.clone())
    }

    async fn search_edge_type_candidates(
        &self,
        _vector: &[f32],
        _limit: u64,
    ) -> Result<Vec<crate::domain::TypeCandidate>> {
        Ok(self.edge_candidates.clone())
    }
}

struct NoopEmbedder;

#[async_trait]
impl Embedder for NoopEmbedder {
    async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        Ok(texts.iter().map(|_| vec![0.1_f32, 0.2_f32]).collect())
    }
}

fn make_service(schema: SchemaRepoFixture, graph: GraphRepoFixture) -> KnowledgeGrpcService {
    make_service_with_type_vectors(schema, graph, TypeVectorRepoFixture::default())
}

fn make_service_with_type_vectors(
    schema: SchemaRepoFixture,
    graph: GraphRepoFixture,
    type_vectors: TypeVectorRepoFixture,
) -> KnowledgeGrpcService {
    KnowledgeGrpcService {
        app: Arc::new(
            KnowledgeApplication::new(Arc::new(schema), Arc::new(graph), Arc::new(NoopEmbedder))
                .with_type_vector_repository(Arc::new(type_vectors)),
        ),
    }
}

fn parse_schema_json(schema: &str) -> Value {
    serde_json::from_str(schema).expect("schema payload should be valid JSON")
}

#[tokio::test]
async fn health_rpc_returns_ok() {
    let service = make_service(SchemaRepoFixture::default(), GraphRepoFixture::default());
    let reply = service
        .health(Request::new(HealthRequest {}))
        .await
        .expect("health should succeed")
        .into_inner();

    assert_eq!(reply.status, "ok");
}

#[tokio::test]
async fn get_upsert_graph_delta_json_schema_contract_table() {
    let service = make_service(SchemaRepoFixture::default(), GraphRepoFixture::default());

    let reply = service
        .get_upsert_graph_delta_json_schema(Request::new(GetUpsertGraphDeltaJsonSchemaRequest {}))
        .await
        .expect("rpc should succeed")
        .into_inner();

    let schema = parse_schema_json(&reply.json_schema);
    let visibility_has_expected_values =
        reply.json_schema.contains("\"PRIVATE\"") && reply.json_schema.contains("\"SHARED\"");

    let checks = [
        (
            "schema_id",
            reply.schema_id.as_deref() == Some(UPSERT_GRAPH_DELTA_SCHEMA_ID),
        ),
        ("draft", reply.draft.as_deref() == Some("2020-12")),
        ("version", reply.version.as_deref() == Some("1.0.0")),
        (
            "root fields",
            ["universes", "entities", "blocks", "edges"]
                .iter()
                .all(|key| schema["properties"].get(*key).is_some()),
        ),
        ("visibility enum", visibility_has_expected_values),
    ];

    for (name, passed) in checks {
        assert!(passed, "schema contract check failed: {name}");
    }
}

#[tokio::test]
async fn get_entity_extraction_schema_context_contract_table() {
    struct Case {
        name: &'static str,
        request: GetEntityExtractionSchemaContextRequest,
        schema_fail: bool,
        graph_fail: bool,
        expected_code: Option<Code>,
    }

    let cases = vec![
        Case {
            name: "defaults include_inactive=false and maps response shape",
            request: GetEntityExtractionSchemaContextRequest {
                include_inactive: None,
                user_id: "user-1".to_string(),
            },
            schema_fail: false,
            graph_fail: false,
            expected_code: None,
        },
        Case {
            name: "include_inactive=true allows inactive entity type",
            request: GetEntityExtractionSchemaContextRequest {
                include_inactive: Some(true),
                user_id: "user-1".to_string(),
            },
            schema_fail: false,
            graph_fail: false,
            expected_code: None,
        },
        Case {
            name: "blank user maps to invalid argument",
            request: GetEntityExtractionSchemaContextRequest {
                include_inactive: None,
                user_id: "   ".to_string(),
            },
            schema_fail: false,
            graph_fail: false,
            expected_code: Some(Code::InvalidArgument),
        },
        Case {
            name: "schema repo failures map to internal",
            request: GetEntityExtractionSchemaContextRequest {
                include_inactive: None,
                user_id: "user-1".to_string(),
            },
            schema_fail: true,
            graph_fail: false,
            expected_code: Some(Code::Internal),
        },
    ];

    for case in cases {
        let service = make_service(
            SchemaRepoFixture {
                fail_get_by_kind: case.schema_fail,
                ..SchemaRepoFixture::default()
            },
            GraphRepoFixture {
                universes: vec![
                    crate::domain::ExtractionUniverse {
                        id: "universe-b".to_string(),
                        name: "B".to_string(),
                        described_by_text: None,
                    },
                    crate::domain::ExtractionUniverse {
                        id: "universe-a".to_string(),
                        name: "A".to_string(),
                        described_by_text: Some("desc".to_string()),
                    },
                ],
                fail_universes: case.graph_fail,
            },
        );

        let result = service
            .get_entity_extraction_schema_context(Request::new(case.request.clone()))
            .await;

        match case.expected_code {
            Some(code) => {
                let status = result.expect_err(case.name);
                assert_eq!(status.code(), code, "{0}", case.name);
            }
            None => {
                let reply = result.expect(case.name).into_inner();
                assert_eq!(reply.universes[0].id, "universe-a", "{0}", case.name);
                let has_legacy = reply
                    .entity_types
                    .iter()
                    .any(|t| t.type_id == "node.legacy");
                assert_eq!(has_legacy, case.request.include_inactive.unwrap_or(false));
                let person = reply
                    .entity_types
                    .iter()
                    .find(|t| t.type_id == "node.person")
                    .expect("person contract entity type");
                assert_eq!(person.inheritance_chain, vec!["node.entity", "node.person"]);
            }
        }
    }
}

#[tokio::test]
async fn get_edge_extraction_schema_context_contract_table() {
    struct Case {
        name: &'static str,
        request: GetEdgeExtractionSchemaContextRequest,
        schema_fail: bool,
        expected_code: Option<Code>,
    }

    let cases = vec![
        Case {
            name: "trims entity types and returns mapped edge",
            request: GetEdgeExtractionSchemaContextRequest {
                first_entity_type: " node.person ".to_string(),
                second_entity_type: " node.task ".to_string(),
                include_inactive: None,
                user_id: "user-1".to_string(),
            },
            schema_fail: false,
            expected_code: None,
        },
        Case {
            name: "blank type ids return invalid argument",
            request: GetEdgeExtractionSchemaContextRequest {
                first_entity_type: "   ".to_string(),
                second_entity_type: "node.task".to_string(),
                include_inactive: None,
                user_id: "user-1".to_string(),
            },
            schema_fail: false,
            expected_code: Some(Code::InvalidArgument),
        },
        Case {
            name: "schema failures map to internal",
            request: GetEdgeExtractionSchemaContextRequest {
                first_entity_type: "node.person".to_string(),
                second_entity_type: "node.task".to_string(),
                include_inactive: None,
                user_id: "user-1".to_string(),
            },
            schema_fail: true,
            expected_code: Some(Code::Internal),
        },
    ];

    for case in cases {
        let service = make_service(
            SchemaRepoFixture {
                fail_get_by_kind: case.schema_fail,
                ..SchemaRepoFixture::default()
            },
            GraphRepoFixture::default(),
        );
        let result = service
            .get_edge_extraction_schema_context(Request::new(case.request))
            .await;

        match case.expected_code {
            Some(code) => {
                let status = result.expect_err(case.name);
                assert_eq!(status.code(), code, "{0}", case.name);
            }
            None => {
                let reply = result.expect(case.name).into_inner();
                assert_eq!(reply.first_entity_type, "node.person");
                assert_eq!(reply.second_entity_type, "node.task");
                assert_eq!(reply.edge_types.len(), 1);
                assert_eq!(reply.edge_types[0].edge_type_id, "edge.assigned_to");
            }
        }
    }
}

#[tokio::test]
async fn get_entity_type_property_context_contract_table() {
    struct Case {
        name: &'static str,
        request: GetEntityTypePropertyContextRequest,
        schema_fail: bool,
        expected_code: Option<Code>,
    }

    let cases = vec![
        Case {
            name: "include_inherited defaults true",
            request: GetEntityTypePropertyContextRequest {
                type_id: "node.person".to_string(),
                include_inactive: Some(false),
                include_inherited: None,
                user_id: None,
            },
            schema_fail: false,
            expected_code: None,
        },
        Case {
            name: "blank type id maps to invalid argument",
            request: GetEntityTypePropertyContextRequest {
                type_id: "   ".to_string(),
                include_inactive: None,
                include_inherited: None,
                user_id: None,
            },
            schema_fail: false,
            expected_code: Some(Code::InvalidArgument),
        },
        Case {
            name: "unknown type id maps to invalid argument",
            request: GetEntityTypePropertyContextRequest {
                type_id: "node.unknown".to_string(),
                include_inactive: None,
                include_inherited: None,
                user_id: None,
            },
            schema_fail: false,
            expected_code: Some(Code::InvalidArgument),
        },
        Case {
            name: "schema backend errors map to internal",
            request: GetEntityTypePropertyContextRequest {
                type_id: "node.person".to_string(),
                include_inactive: None,
                include_inherited: None,
                user_id: None,
            },
            schema_fail: true,
            expected_code: Some(Code::Internal),
        },
    ];

    for case in cases {
        let service = make_service(
            SchemaRepoFixture {
                fail_get_by_kind: case.schema_fail,
                ..SchemaRepoFixture::default()
            },
            GraphRepoFixture::default(),
        );

        let result = service
            .get_entity_type_property_context(Request::new(case.request))
            .await;

        match case.expected_code {
            Some(code) => {
                let status = result.expect_err(case.name);
                assert_eq!(status.code(), code, "{0}", case.name);
            }
            None => {
                let reply = result.expect(case.name).into_inner();
                assert_eq!(reply.type_id, "node.person");
                assert_eq!(reply.inheritance_chain, vec!["node.entity", "node.person"]);
                assert_eq!(reply.properties.len(), 2);
                assert_eq!(reply.properties[0].prop_name, "name");
                assert_eq!(reply.properties[1].prop_name, "nickname");
            }
        }
    }
}

#[test]
fn extraction_schema_algorithm_filters_inactive_types_and_rules() {
    let schema = FullSchema {
        node_types: vec![
            crate::domain::SchemaNodeTypeHydrated {
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
            crate::domain::SchemaNodeTypeHydrated {
                schema_type: SchemaType {
                    id: "node.person".to_string(),
                    kind: "node".to_string(),
                    name: "Person".to_string(),
                    description: "Person entity".to_string(),
                    active: true,
                },
                properties: vec![],
                parents: vec![TypeInheritance {
                    child_type_id: "node.person".to_string(),
                    parent_type_id: "node.entity".to_string(),
                    description: "inherits".to_string(),
                    active: true,
                }],
            },
            crate::domain::SchemaNodeTypeHydrated {
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
        edge_types: vec![crate::domain::SchemaEdgeTypeHydrated {
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

    let entity_types = crate::application::build_extraction_entity_types_from_input(
        crate::application::ExtractionSchemaBuildInput {
            node_types: schema
                .node_types
                .iter()
                .map(|n| n.schema_type.clone())
                .collect(),
            edge_types: schema
                .edge_types
                .iter()
                .map(|e| e.schema_type.clone())
                .collect(),
            inheritance: schema
                .node_types
                .into_iter()
                .flat_map(|n| n.parents)
                .collect(),
            edge_rules: schema
                .edge_types
                .into_iter()
                .flat_map(|e| e.rules)
                .collect(),
        },
        crate::application::ExtractionSchemaOptions {
            include_inactive: false,
        },
    );

    assert_eq!(entity_types.len(), 2);
}

#[tokio::test]
async fn find_node_type_candidates_rpc_returns_candidates() {
    let service = make_service_with_type_vectors(
        SchemaRepoFixture::default(),
        GraphRepoFixture::default(),
        TypeVectorRepoFixture {
            node_candidates: vec![crate::domain::TypeCandidate {
                type_id: "node.person".to_string(),
                name: "Person".to_string(),
                description: "Human".to_string(),
                score: 0.88,
            }],
            edge_candidates: Vec::new(),
        },
    );

    let reply = service
        .find_node_type_candidates(Request::new(FindNodeTypeCandidatesRequest {
            name: " person ".to_string(),
            description: " human ".to_string(),
            limit: Some(5),
        }))
        .await
        .expect("rpc should succeed")
        .into_inner();

    assert_eq!(reply.candidates.len(), 1);
    assert_eq!(reply.candidates[0].type_id, "node.person");
}

#[tokio::test]
async fn find_node_type_candidates_rpc_rejects_empty_payload() {
    let service = make_service(SchemaRepoFixture::default(), GraphRepoFixture::default());

    let error = service
        .find_node_type_candidates(Request::new(FindNodeTypeCandidatesRequest {
            name: " ".to_string(),
            description: "\n".to_string(),
            limit: None,
        }))
        .await
        .expect_err("rpc should fail");

    assert_eq!(error.code(), Code::InvalidArgument);
    assert_eq!(
        error.message(),
        "at least one of name or description is required"
    );
}

#[tokio::test]
async fn find_edge_type_candidates_rpc_rejects_empty_payload() {
    let service = make_service(SchemaRepoFixture::default(), GraphRepoFixture::default());

    let error = service
        .find_edge_type_candidates(Request::new(FindEdgeTypeCandidatesRequest {
            name: " ".to_string(),
            description: "\n".to_string(),
            limit: None,
        }))
        .await
        .expect_err("rpc should fail");

    assert_eq!(error.code(), Code::InvalidArgument);
    assert_eq!(
        error.message(),
        "at least one of name or description is required"
    );
}

#[tokio::test]
async fn find_edge_type_candidates_rpc_returns_candidates() {
    let service = make_service_with_type_vectors(
        SchemaRepoFixture::default(),
        GraphRepoFixture::default(),
        TypeVectorRepoFixture {
            node_candidates: Vec::new(),
            edge_candidates: vec![crate::domain::TypeCandidate {
                type_id: "edge.assigned_to".to_string(),
                name: "ASSIGNED_TO".to_string(),
                description: "assignment".to_string(),
                score: 0.91,
            }],
        },
    );

    let reply = service
        .find_edge_type_candidates(Request::new(FindEdgeTypeCandidatesRequest {
            name: " assigned ".to_string(),
            description: " relationship ".to_string(),
            limit: Some(3),
        }))
        .await
        .expect("rpc should succeed")
        .into_inner();

    assert_eq!(reply.candidates.len(), 1);
    assert_eq!(reply.candidates[0].type_id, "edge.assigned_to");
}
