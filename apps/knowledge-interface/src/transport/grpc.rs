use std::sync::Arc;

use tonic::{transport::Server, Request, Response, Status};

use crate::domain::{
    SchemaKind, SchemaType, UpsertSchemaTypeCommand, UpsertSchemaTypePropertyInput,
};
use crate::presentation::extraction_prompt::ExtractionContextView;
use crate::presentation::upsert_delta_json_schema::{
    upsert_graph_delta_json_schema_string, UPSERT_GRAPH_DELTA_SCHEMA_ID,
};
use crate::service::{
    build_extraction_entity_types, EntityTypePropertyContextOptions,
    ExtractionAllowedEdge as ServiceAllowedEdge,
    ExtractionEntityType as ServiceExtractionEntityType, ExtractionSchemaOptions,
    ExtractionUniverseContext as ServiceExtractionUniverseContext, KnowledgeApplication,
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
    AllowedEdge, ExtractionEntityType, ExtractionUniverse, FindEntityCandidatesReply,
    FindEntityCandidatesRequest, GetEntityContextReply, GetEntityContextRequest,
    GetEntityTypePropertyContextReply, GetEntityTypePropertyContextRequest,
    GetExtractionSchemaContextReply, GetExtractionSchemaContextRequest, GetSchemaReply,
    GetSchemaRequest, GetUpsertGraphDeltaJsonSchemaReply, GetUpsertGraphDeltaJsonSchemaRequest,
    GetUserInitGraphReply, GetUserInitGraphRequest, HealthReply, HealthRequest,
    ListEntitiesByTypeReply, ListEntitiesByTypeRequest, UpsertGraphDeltaReply,
    UpsertGraphDeltaRequest, UpsertSchemaTypeReply, UpsertSchemaTypeRequest,
};
use super::FILE_DESCRIPTOR_SET;

pub struct KnowledgeGrpcService {
    pub app: Arc<KnowledgeApplication>,
}

fn extraction_options_from_request(
    request: &GetExtractionSchemaContextRequest,
) -> ExtractionSchemaOptions {
    ExtractionSchemaOptions {
        include_edge_properties: request.include_edge_properties.unwrap_or(false),
        include_inactive: request.include_inactive.unwrap_or(false),
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
        Ok(Response::new(GetUpsertGraphDeltaJsonSchemaReply {
            json_schema: upsert_graph_delta_json_schema_string(),
            schema_id: Some(UPSERT_GRAPH_DELTA_SCHEMA_ID.to_string()),
            draft: Some("2020-12".to_string()),
            version: Some("1.0.0".to_string()),
        }))
    }

    async fn get_extraction_schema_context(
        &self,
        request: Request<GetExtractionSchemaContextRequest>,
    ) -> Result<Response<GetExtractionSchemaContextReply>, Status> {
        let payload = request.into_inner();
        let schema = self
            .app
            .get_schema()
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        let entity_types =
            build_extraction_entity_types(schema, extraction_options_from_request(&payload));
        let universes = self
            .app
            .get_extraction_universes(&payload.user_id)
            .await
            .map_err(|e| Status::invalid_argument(e.to_string()))?;
        let structured_context_view = ExtractionContextView::structured(entity_types, universes);
        let prompt_context_markdown = match structured_context_view.to_rendered_markdown() {
            ExtractionContextView::RenderedMarkdown(markdown) => markdown,
            ExtractionContextView::Structured(_) => String::new(),
        };
        let structured_context = match structured_context_view {
            ExtractionContextView::Structured(structured) => structured,
            ExtractionContextView::RenderedMarkdown(_) => {
                unreachable!("context view should remain structured")
            }
        };

        Ok(Response::new(GetExtractionSchemaContextReply {
            entity_types: structured_context
                .entity_types
                .into_iter()
                .map(to_proto_extraction_entity_type)
                .collect(),
            prompt_context_markdown: Some(prompt_context_markdown),
            universes: structured_context
                .universes
                .into_iter()
                .map(to_proto_extraction_universe)
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
                EntityTypePropertyContextOptions {
                    include_inactive: payload.include_inactive.unwrap_or(false),
                    include_inherited: payload.include_inherited.unwrap_or(true),
                },
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
                .map(|prop| super::proto::PropertyContext {
                    prop_name: prop.prop_name,
                    value_type: prop.value_type,
                    required: prop.required,
                    readable: prop.readable,
                    writable: prop.writable,
                    description: prop.description,
                    declared_on_type_id: prop.declared_on_type_id,
                })
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
        extraction_options_from_request, to_proto_extraction_entity_type,
        to_proto_extraction_universe, upsert_graph_delta_json_schema_string,
    };
    use crate::domain::{
        EdgeEndpointRule, FullSchema, SchemaEdgeTypeHydrated, SchemaNodeTypeHydrated, SchemaType,
    };
    use crate::presentation::extraction_prompt::render_prompt_context_markdown;
    use crate::service::{
        build_extraction_entity_types, ExtractionAllowedEdge, ExtractionEntityType,
        ExtractionSchemaOptions, ExtractionUniverseContext,
    };
    use crate::transport::proto::{
        GetEntityTypePropertyContextRequest, GetExtractionSchemaContextRequest,
    };

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
                include_edge_properties: false,
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
                include_edge_properties: false,
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
    fn prompt_context_markdown_is_derived_from_sorted_structured_payload() {
        let entity_types = vec![
            ExtractionEntityType {
                type_id: "node.alpha".to_string(),
                name: "Alpha".to_string(),
                description: "A".to_string(),
                inheritance_chain: vec!["node.entity".to_string(), "node.alpha".to_string()],
                outgoing_edges: vec![ExtractionAllowedEdge {
                    edge_type_id: "edge.rel".to_string(),
                    edge_name: "REL".to_string(),
                    edge_description: "Relationship".to_string(),
                    other_entity_type_id: "node.entity".to_string(),
                    other_entity_type_name: "Entity".to_string(),
                    min_cardinality: None,
                    max_cardinality: None,
                }],
                incoming_edges: vec![],
            },
            ExtractionEntityType {
                type_id: "node.entity".to_string(),
                name: "Entity".to_string(),
                description: "Root".to_string(),
                inheritance_chain: vec!["node.entity".to_string()],
                outgoing_edges: vec![],
                incoming_edges: vec![ExtractionAllowedEdge {
                    edge_type_id: "edge.rel".to_string(),
                    edge_name: "REL".to_string(),
                    edge_description: "Relationship".to_string(),
                    other_entity_type_id: "node.alpha".to_string(),
                    other_entity_type_name: "Alpha".to_string(),
                    min_cardinality: None,
                    max_cardinality: None,
                }],
            },
        ];

        let markdown = render_prompt_context_markdown(&entity_types);
        assert!(markdown.contains("| node.alpha | Alpha | A | node.entity → node.alpha |"));
        assert!(markdown.contains(
            "| node.alpha | outgoing | edge.rel | REL | node.entity | Entity | Relationship |"
        ));
        assert!(markdown.contains(
            "| node.entity | incoming | edge.rel | REL | node.alpha | Alpha | Relationship |"
        ));
    }

    #[test]
    fn extraction_request_optional_flags_default_to_false() {
        let request = GetExtractionSchemaContextRequest {
            include_edge_properties: None,
            include_inactive: None,
            user_id: "user-1".to_string(),
        };

        let options = extraction_options_from_request(&request);

        assert!(!options.include_edge_properties);
        assert!(!options.include_inactive);
    }

    #[test]
    fn extraction_request_optional_flags_respect_explicit_true() {
        let request = GetExtractionSchemaContextRequest {
            include_edge_properties: Some(true),
            include_inactive: Some(true),
            user_id: "user-1".to_string(),
        };

        let options = extraction_options_from_request(&request);

        assert!(options.include_edge_properties);
        assert!(options.include_inactive);
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
        assert_eq!(proto.inheritance_chain, vec!["node.entity", "node.person"]);
        assert_eq!(proto.outgoing_edges.len(), 1);
        assert_eq!(proto.outgoing_edges[0].edge_type_id, "edge.related_to");
        assert_eq!(proto.outgoing_edges[0].min_cardinality, Some(1));
        assert_eq!(proto.outgoing_edges[0].max_cardinality, Some(2));
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

    #[test]
    fn upsert_graph_delta_json_schema_contains_core_sections() {
        let schema = upsert_graph_delta_json_schema_string();
        assert!(schema.contains("$schema"));
        assert!(schema.contains("$id"));
        assert!(schema.contains("universes"));
        assert!(schema.contains("entities"));
        assert!(schema.contains("blocks"));
        assert!(schema.contains("edges"));
    }
}
