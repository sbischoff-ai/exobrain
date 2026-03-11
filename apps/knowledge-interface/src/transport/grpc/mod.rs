use std::sync::Arc;

use tonic::{transport::Server, Request, Response, Status};

use crate::application::{
    EntityTypePropertyContextOptions, ExtractionEdgeType as ServiceExtractionEdgeType,
    ExtractionEntityType as ServiceExtractionEntityType, ExtractionPropertyContext,
    ExtractionSchemaOptions, ExtractionUniverseContext as ServiceExtractionUniverseContext,
    KnowledgeApplication,
};
use crate::domain::{
    SchemaKind, SchemaType, UpsertSchemaTypeCommand, UpsertSchemaTypePropertyInput,
};
use crate::presentation::upsert_delta_json_schema::{
    try_upsert_graph_delta_json_schema_string, UPSERT_GRAPH_DELTA_SCHEMA_ID,
};

use super::errors::map_application_error;
use super::mapping::{
    to_domain_block_node, to_domain_entity_node, to_domain_find_entity_candidates_query,
    to_domain_get_entity_context_query, to_domain_graph_edge,
    to_domain_list_entities_by_type_query, to_domain_universe_node, to_proto_edge_endpoint_rule,
    to_proto_entity_candidate, to_proto_get_entity_context_reply,
    to_proto_list_entities_by_type_reply, to_proto_schema_type, to_proto_type_inheritance,
    to_proto_type_property,
};
use super::proto::knowledge_interface_server::{KnowledgeInterface, KnowledgeInterfaceServer};
use super::proto::{
    ExtractionEdgeType, ExtractionEntityType, ExtractionUniverse, FindEntityCandidatesReply,
    FindEntityCandidatesRequest, GetEdgeExtractionSchemaContextReply,
    GetEdgeExtractionSchemaContextRequest, GetEntityContextReply, GetEntityContextRequest,
    GetEntityExtractionSchemaContextReply, GetEntityExtractionSchemaContextRequest,
    GetEntityTypePropertyContextReply, GetEntityTypePropertyContextRequest, GetSchemaReply,
    GetSchemaRequest, GetUpsertGraphDeltaJsonSchemaReply, GetUpsertGraphDeltaJsonSchemaRequest,
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

fn to_proto_extraction_entity_type(entity: ServiceExtractionEntityType) -> ExtractionEntityType {
    ExtractionEntityType {
        type_id: entity.type_id,
        name: entity.name,
        description: entity.description,
        inheritance_chain: entity.inheritance_chain,
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
        let schema = self.app.get_schema().await.map_err(map_application_error)?;

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
            .map_err(map_application_error)?;
        let universes = self
            .app
            .get_extraction_universes(&payload.user_id)
            .await
            .map_err(map_application_error)?;

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
            .map_err(map_application_error)?;

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
            .map_err(map_application_error)?;

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
            .map_err(map_application_error)?;

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
            .map_err(map_application_error)?;

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
            .map_err(map_application_error)?;

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
            .map_err(map_application_error)?;

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
            .map_err(map_application_error)?;

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
            .map_err(map_application_error)?;

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
mod tests;
