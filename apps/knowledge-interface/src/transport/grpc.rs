use std::sync::Arc;

use tonic::{transport::Server, Request, Response, Status};

use crate::domain::{
    SchemaKind, SchemaType, UpsertSchemaTypeCommand, UpsertSchemaTypePropertyInput,
};
use crate::presentation::upsert_delta_json_schema::{
    try_upsert_graph_delta_json_schema_string, UPSERT_GRAPH_DELTA_SCHEMA_ID,
};
use crate::service::{
    EntityTypePropertyContextOptions, ExtractionAllowedEdge as ServiceAllowedEdge,
    ExtractionEdgeType as ServiceExtractionEdgeType,
    ExtractionEntityType as ServiceExtractionEntityType, ExtractionPropertyContext,
    ExtractionSchemaOptions, ExtractionUniverseContext as ServiceExtractionUniverseContext,
    KnowledgeApplication,
};

use super::errors::map_ingest_error;
use super::mappers::{
    to_domain_block_node, to_domain_entity_node, to_domain_find_entity_candidates_query,
    to_domain_get_entity_context_query, to_domain_graph_edge,
    to_domain_list_entities_by_type_query, to_domain_universe_node, to_proto_edge_endpoint_rule,
    to_proto_entity_candidate, to_proto_get_entity_context_reply,
    to_proto_list_entities_by_type_reply, to_proto_schema_type, to_proto_type_inheritance,
    to_proto_type_property,
};
use super::proto::knowledge_interface_server::{KnowledgeInterface, KnowledgeInterfaceServer};
use super::proto::{
    AllowedEdge, ExtractionEdgeType, ExtractionEntityType, ExtractionEntityTypeWithEdges,
    ExtractionUniverse, FindEntityCandidatesReply, FindEntityCandidatesRequest,
    GetEdgeExtractionSchemaContextReply, GetEdgeExtractionSchemaContextRequest,
    GetEntityContextReply, GetEntityContextRequest, GetEntityExtractionSchemaContextReply,
    GetEntityExtractionSchemaContextRequest, GetEntityTypePropertyContextReply,
    GetEntityTypePropertyContextRequest, GetSchemaReply, GetSchemaRequest,
    GetUpsertGraphDeltaJsonSchemaReply, GetUpsertGraphDeltaJsonSchemaRequest,
    GetUserInitGraphReply, GetUserInitGraphRequest, HealthReply, HealthRequest,
    ListEntitiesByTypeReply, ListEntitiesByTypeRequest, UpsertGraphDeltaReply,
    UpsertGraphDeltaRequest, UpsertSchemaTypeReply, UpsertSchemaTypeRequest,
};
use super::FILE_DESCRIPTOR_SET;

pub struct KnowledgeGrpcService {
    pub app: Arc<KnowledgeApplication>,
}

fn extraction_options_from_entity_request(
    request: &GetEntityExtractionSchemaContextRequest,
) -> ExtractionSchemaOptions {
    ExtractionSchemaOptions {
        include_inactive: request.include_inactive.unwrap_or(false),
    }
}

fn extraction_options_from_edge_request(
    request: &GetEdgeExtractionSchemaContextRequest,
) -> ExtractionSchemaOptions {
    ExtractionSchemaOptions {
        include_inactive: request.include_inactive.unwrap_or(false),
    }
}

fn entity_type_property_context_options_from_request(
    request: &GetEntityTypePropertyContextRequest,
) -> EntityTypePropertyContextOptions {
    EntityTypePropertyContextOptions {
        include_inactive: request.include_inactive.unwrap_or(false),
        include_inherited: request.include_inherited.unwrap_or(true),
    }
}

fn to_proto_property_context(prop: ExtractionPropertyContext) -> super::proto::PropertyContext {
    super::proto::PropertyContext {
        prop_name: prop.prop_name,
        value_type: prop.value_type,
        required: prop.required,
        readable: prop.readable,
        writable: prop.writable,
        description: prop.description,
        declared_on_type_id: prop.declared_on_type_id,
    }
}

fn to_proto_allowed_edge(edge: ServiceAllowedEdge) -> AllowedEdge {
    AllowedEdge {
        edge_type_id: edge.edge_type_id,
        edge_name: edge.edge_name,
        edge_description: edge.edge_description,
        other_entity_type_id: edge.other_entity_type_id,
        other_entity_type_name: edge.other_entity_type_name,
        min_cardinality: edge.min_cardinality,
        max_cardinality: edge.max_cardinality,
    }
}

fn to_proto_extraction_entity_type(entity: ServiceExtractionEntityType) -> ExtractionEntityType {
    ExtractionEntityType {
        type_id: entity.type_id,
        name: entity.name,
        description: entity.description,
        inheritance_chain: entity.inheritance_chain,
    }
}

fn to_proto_extraction_entity_type_with_edges(
    entity: ServiceExtractionEntityType,
) -> ExtractionEntityTypeWithEdges {
    ExtractionEntityTypeWithEdges {
        type_id: entity.type_id,
        name: entity.name,
        description: entity.description,
        inheritance_chain: entity.inheritance_chain,
        outgoing_edges: entity
            .outgoing_edges
            .into_iter()
            .map(to_proto_allowed_edge)
            .collect(),
        incoming_edges: entity
            .incoming_edges
            .into_iter()
            .map(to_proto_allowed_edge)
            .collect(),
    }
}

fn to_proto_extraction_edge_type(edge: ServiceExtractionEdgeType) -> ExtractionEdgeType {
    ExtractionEdgeType {
        edge_type_id: edge.edge_type_id,
        edge_name: edge.edge_name,
        edge_description: edge.edge_description,
        source_entity_type_id: edge.source_entity_type_id,
        target_entity_type_id: edge.target_entity_type_id,
    }
}

fn to_proto_extraction_universe(universe: ServiceExtractionUniverseContext) -> ExtractionUniverse {
    ExtractionUniverse {
        id: universe.id,
        name: universe.name,
        described_by_text: universe.described_by_text,
    }
}

#[tonic::async_trait]
impl KnowledgeInterface for KnowledgeGrpcService {
    async fn health(
        &self,
        _request: Request<HealthRequest>,
    ) -> Result<Response<HealthReply>, Status> {
        Ok(Response::new(HealthReply {
            status: "ok".to_string(),
        }))
    }

    async fn get_schema(
        &self,
        _request: Request<GetSchemaRequest>,
    ) -> Result<Response<GetSchemaReply>, Status> {
        let schema = self
            .app
            .get_schema()
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        Ok(Response::new(GetSchemaReply {
            node_types: schema
                .node_types
                .into_iter()
                .map(|node| super::proto::SchemaNodeType {
                    r#type: Some(to_proto_schema_type(node.schema_type)),
                    properties: node
                        .properties
                        .into_iter()
                        .map(to_proto_type_property)
                        .collect(),
                    parents: node
                        .parents
                        .into_iter()
                        .map(to_proto_type_inheritance)
                        .collect(),
                })
                .collect(),
            edge_types: schema
                .edge_types
                .into_iter()
                .map(|edge| super::proto::SchemaEdgeType {
                    r#type: Some(to_proto_schema_type(edge.schema_type)),
                    properties: edge
                        .properties
                        .into_iter()
                        .map(to_proto_type_property)
                        .collect(),
                    rules: edge
                        .rules
                        .into_iter()
                        .map(to_proto_edge_endpoint_rule)
                        .collect(),
                })
                .collect(),
        }))
    }

    async fn get_upsert_graph_delta_json_schema(
        &self,
        _request: Request<GetUpsertGraphDeltaJsonSchemaRequest>,
    ) -> Result<Response<GetUpsertGraphDeltaJsonSchemaReply>, Status> {
        let json_schema = try_upsert_graph_delta_json_schema_string()
            .map_err(|err| Status::internal(format!("failed to serialize json schema: {err}")))?;

        Ok(Response::new(GetUpsertGraphDeltaJsonSchemaReply {
            json_schema,
            schema_id: Some(UPSERT_GRAPH_DELTA_SCHEMA_ID.to_string()),
            draft: Some("2020-12".to_string()),
            version: Some("1.0.0".to_string()),
        }))
    }

    async fn get_entity_extraction_schema_context(
        &self,
        request: Request<GetEntityExtractionSchemaContextRequest>,
    ) -> Result<Response<GetEntityExtractionSchemaContextReply>, Status> {
        let payload = request.into_inner();
        let entity_types = self
            .app
            .get_entity_extraction_schema_types(extraction_options_from_entity_request(&payload))
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        let universes = self
            .app
            .get_extraction_universes(&payload.user_id)
            .await
            .map_err(|e| Status::invalid_argument(e.to_string()))?;

        Ok(Response::new(GetEntityExtractionSchemaContextReply {
            entity_types: entity_types
                .into_iter()
                .map(to_proto_extraction_entity_type)
                .collect(),
            universes: universes
                .into_iter()
                .map(to_proto_extraction_universe)
                .collect(),
        }))
    }

    async fn get_edge_extraction_schema_context(
        &self,
        request: Request<GetEdgeExtractionSchemaContextRequest>,
    ) -> Result<Response<GetEdgeExtractionSchemaContextReply>, Status> {
        let payload = request.into_inner();
        let first_entity_type = payload.first_entity_type.trim().to_string();
        let second_entity_type = payload.second_entity_type.trim().to_string();

        if first_entity_type.is_empty() || second_entity_type.is_empty() {
            return Err(Status::invalid_argument(
                "first_entity_type and second_entity_type are required",
            ));
        }

        let edge_types = self
            .app
            .get_edge_extraction_schema_types(
                &first_entity_type,
                &second_entity_type,
                extraction_options_from_edge_request(&payload),
            )
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        Ok(Response::new(GetEdgeExtractionSchemaContextReply {
            first_entity_type,
            second_entity_type,
            edge_types: edge_types
                .into_iter()
                .map(to_proto_extraction_edge_type)
                .collect(),
        }))
    }

    async fn get_entity_type_property_context(
        &self,
        request: Request<GetEntityTypePropertyContextRequest>,
    ) -> Result<Response<GetEntityTypePropertyContextReply>, Status> {
        let payload = request.into_inner();
        let reply = self
            .app
            .get_entity_type_property_context(
                &payload.type_id,
                entity_type_property_context_options_from_request(&payload),
            )
            .await
            .map_err(|e| Status::invalid_argument(e.to_string()))?;

        Ok(Response::new(GetEntityTypePropertyContextReply {
            type_id: reply.type_id,
            type_name: reply.type_name,
            inheritance_chain: reply.inheritance_chain,
            properties: reply
                .properties
                .into_iter()
                .map(to_proto_property_context)
                .collect(),
        }))
    }

    async fn upsert_schema_type(
        &self,
        request: Request<UpsertSchemaTypeRequest>,
    ) -> Result<Response<UpsertSchemaTypeReply>, Status> {
        let payload = request.into_inner();
        let upserted = self
            .app
            .upsert_schema_type(UpsertSchemaTypeCommand {
                schema_type: SchemaType {
                    id: payload.id,
                    kind: SchemaKind::from_proto_str(&payload.kind)
                        .map(SchemaKind::as_db_str)
                        .unwrap_or(payload.kind.as_str())
                        .to_string(),
                    name: payload.name,
                    description: payload.description,
                    active: payload.active,
                },
                parent_type_id: payload.parent_type_id,
                properties: payload
                    .properties
                    .into_iter()
                    .map(|prop| UpsertSchemaTypePropertyInput {
                        prop_name: prop.prop_name,
                        value_type: prop.value_type,
                        required: prop.required,
                        readable: prop.readable,
                        writable: prop.writable,
                        active: prop.active,
                        description: prop.description,
                    })
                    .collect(),
            })
            .await
            .map_err(|e| Status::invalid_argument(e.to_string()))?;

        Ok(Response::new(UpsertSchemaTypeReply {
            schema_type: Some(super::proto::SchemaType {
                id: upserted.id,
                kind: upserted.kind,
                name: upserted.name,
                description: upserted.description,
                active: upserted.active,
            }),
        }))
    }

    async fn get_user_init_graph(
        &self,
        request: Request<GetUserInitGraphRequest>,
    ) -> Result<Response<GetUserInitGraphReply>, Status> {
        let payload = request.into_inner();
        let node_ids = self
            .app
            .get_user_init_graph(&payload.user_id, &payload.user_name)
            .await
            .map_err(|e| Status::invalid_argument(e.to_string()))?;

        Ok(Response::new(GetUserInitGraphReply {
            person_entity_id: node_ids.person_entity_id,
            assistant_entity_id: node_ids.assistant_entity_id,
        }))
    }

    async fn find_entity_candidates(
        &self,
        request: Request<FindEntityCandidatesRequest>,
    ) -> Result<Response<FindEntityCandidatesReply>, Status> {
        let query = to_domain_find_entity_candidates_query(request.into_inner());
        let result = self
            .app
            .find_entity_candidates(query)
            .await
            .map_err(|e| Status::invalid_argument(e.to_string()))?;

        Ok(Response::new(FindEntityCandidatesReply {
            candidates: result
                .candidates
                .into_iter()
                .map(to_proto_entity_candidate)
                .collect(),
        }))
    }

    async fn list_entities_by_type(
        &self,
        request: Request<ListEntitiesByTypeRequest>,
    ) -> Result<Response<ListEntitiesByTypeReply>, Status> {
        let query = to_domain_list_entities_by_type_query(request.into_inner());
        let result = self
            .app
            .list_entities_by_type(query)
            .await
            .map_err(|e| Status::invalid_argument(e.to_string()))?;

        Ok(Response::new(to_proto_list_entities_by_type_reply(result)))
    }

    async fn get_entity_context(
        &self,
        request: Request<GetEntityContextRequest>,
    ) -> Result<Response<GetEntityContextReply>, Status> {
        let query = to_domain_get_entity_context_query(request.into_inner());
        let result = self
            .app
            .get_entity_context(query)
            .await
            .map_err(|e| Status::invalid_argument(e.to_string()))?;

        Ok(Response::new(to_proto_get_entity_context_reply(result)))
    }

    async fn upsert_graph_delta(
        &self,
        request: Request<UpsertGraphDeltaRequest>,
    ) -> Result<Response<UpsertGraphDeltaReply>, Status> {
        let payload = request.into_inner();

        let universes = payload
            .universes
            .into_iter()
            .map(to_domain_universe_node)
            .collect::<Result<Vec<_>, Status>>()?;

        let entities = payload
            .entities
            .into_iter()
            .map(to_domain_entity_node)
            .collect::<Result<Vec<_>, Status>>()?;

        let blocks = payload
            .blocks
            .into_iter()
            .map(to_domain_block_node)
            .collect::<Result<Vec<_>, Status>>()?;

        let edges = payload
            .edges
            .into_iter()
            .map(to_domain_graph_edge)
            .collect::<Result<Vec<_>, Status>>()?;

        self.app
            .upsert_graph_delta(crate::domain::GraphDelta {
                universes,
                entities: entities.clone(),
                blocks: blocks.clone(),
                edges: edges.clone(),
            })
            .await
            .map_err(map_ingest_error)?;

        Ok(Response::new(UpsertGraphDeltaReply {
            entities_upserted: entities.len() as u32,
            blocks_upserted: blocks.len() as u32,
            edges_upserted: edges.len() as u32,
        }))
    }
}

pub async fn run_server(
    app: Arc<KnowledgeApplication>,
    enable_reflection: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    let addr = "0.0.0.0:50051".parse()?;
    let grpc = KnowledgeInterfaceServer::new(KnowledgeGrpcService { app });

    if enable_reflection {
        let reflection = tonic_reflection::server::Builder::configure()
            .register_encoded_file_descriptor_set(FILE_DESCRIPTOR_SET)
            .build()?;

        Server::builder()
            .add_service(reflection)
            .add_service(grpc)
            .serve(addr)
            .await?;
    } else {
        Server::builder().add_service(grpc).serve(addr).await?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{
        entity_type_property_context_options_from_request, extraction_options_from_entity_request,
        to_proto_extraction_edge_type, to_proto_extraction_entity_type,
        to_proto_extraction_entity_type_with_edges, to_proto_extraction_universe,
        to_proto_property_context, KnowledgeGrpcService,
    };
    use crate::domain::{
        EdgeEndpointRule, FullSchema, SchemaEdgeTypeHydrated, SchemaNodeTypeHydrated, SchemaType,
    };
    use crate::ports::{Embedder, GraphRepository, SchemaRepository};
    use crate::presentation::upsert_delta_json_schema::UPSERT_GRAPH_DELTA_SCHEMA_ID;
    use crate::service::KnowledgeApplication;
    use crate::service::{
        build_extraction_entity_types, ExtractionAllowedEdge, ExtractionEdgeType,
        ExtractionEntityType, ExtractionPropertyContext, ExtractionSchemaOptions,
        ExtractionUniverseContext,
    };
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
        async fn update_person_name(
            &self,
            _person_entity_id: &str,
            _user_name: &str,
        ) -> Result<()> {
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

        let entity_types = build_extraction_entity_types(
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

        let entity_types = build_extraction_entity_types(
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
    fn proto_mapping_preserves_extraction_entity_with_edges_shape() {
        let proto = to_proto_extraction_entity_type_with_edges(ExtractionEntityType {
            type_id: "node.person".to_string(),
            name: "Person".to_string(),
            description: "A person".to_string(),
            inheritance_chain: vec!["node.entity".to_string(), "node.person".to_string()],
            outgoing_edges: vec![ExtractionAllowedEdge {
                edge_type_id: "edge.related_to".to_string(),
                edge_name: "RELATED_TO".to_string(),
                edge_description: "rel".to_string(),
                other_entity_type_id: "node.concept".to_string(),
                other_entity_type_name: "Concept".to_string(),
                min_cardinality: Some(1),
                max_cardinality: Some(2),
            }],
            incoming_edges: vec![],
        });

        assert_eq!(proto.type_id, "node.person");
        assert_eq!(proto.outgoing_edges.len(), 1);
        assert_eq!(proto.outgoing_edges[0].edge_type_id, "edge.related_to");
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

        let err = crate::service::build_entity_type_property_context(
            schema,
            &request.type_id,
            crate::service::EntityTypePropertyContextOptions {
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

        let err = crate::service::build_entity_type_property_context(
            schema,
            &request.type_id,
            crate::service::EntityTypePropertyContextOptions {
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

        let reply = crate::service::build_entity_type_property_context(
            schema,
            &request.type_id,
            crate::service::EntityTypePropertyContextOptions {
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
            .get_upsert_graph_delta_json_schema(Request::new(
                GetUpsertGraphDeltaJsonSchemaRequest {},
            ))
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
            .get_upsert_graph_delta_json_schema(Request::new(
                GetUpsertGraphDeltaJsonSchemaRequest {},
            ))
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
            .get_upsert_graph_delta_json_schema(Request::new(
                GetUpsertGraphDeltaJsonSchemaRequest {},
            ))
            .await
            .expect("rpc should succeed")
            .into_inner();

        let property_value = &parse_schema_json(&reply.json_schema)["properties"]["entities"]
            ["items"]["properties"]["properties"]["items"];

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
            .get_upsert_graph_delta_json_schema(Request::new(
                GetUpsertGraphDeltaJsonSchemaRequest {},
            ))
            .await
            .expect("rpc should succeed")
            .into_inner();

        let schema = parse_schema_json(&reply.json_schema);
        let enum_values = schema["properties"]["entities"]["items"]["properties"]["visibility"]
            ["enum"]
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
            .get_upsert_graph_delta_json_schema(Request::new(
                GetUpsertGraphDeltaJsonSchemaRequest {},
            ))
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
}
