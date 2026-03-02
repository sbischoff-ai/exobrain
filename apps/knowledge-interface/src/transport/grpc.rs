use std::sync::Arc;

use tonic::{transport::Server, Request, Response, Status};

use crate::domain::{SchemaType, UpsertSchemaTypeCommand, UpsertSchemaTypePropertyInput};
use crate::service::KnowledgeApplication;

use super::errors::map_ingest_error;
use super::mappers::{
    to_domain_block_node, to_domain_entity_node, to_domain_find_entity_candidates_query,
    to_domain_graph_edge, to_domain_universe_node, to_proto_edge_endpoint_rule,
    to_proto_entity_candidate, to_proto_schema_type, to_proto_type_inheritance,
    to_proto_type_property,
};
use super::proto::knowledge_interface_server::{KnowledgeInterface, KnowledgeInterfaceServer};
use super::proto::{
    FindEntityCandidatesReply, FindEntityCandidatesRequest, GetSchemaReply, GetSchemaRequest,
    HealthReply, HealthRequest, InitializeUserGraphReply, InitializeUserGraphRequest,
    UpsertGraphDeltaReply, UpsertGraphDeltaRequest, UpsertSchemaTypeReply, UpsertSchemaTypeRequest,
};
use super::FILE_DESCRIPTOR_SET;

pub struct KnowledgeGrpcService {
    pub app: Arc<KnowledgeApplication>,
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
                    kind: payload.kind,
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

    async fn initialize_user_graph(
        &self,
        request: Request<InitializeUserGraphRequest>,
    ) -> Result<Response<InitializeUserGraphReply>, Status> {
        let payload = request.into_inner();
        let delta = self
            .app
            .initialize_user_graph(&payload.user_id, &payload.user_name)
            .await
            .map_err(|e| Status::invalid_argument(e.to_string()))?;

        Ok(Response::new(InitializeUserGraphReply {
            universe_id: "9d7f0fa5-78c1-4805-9efb-3f8f16090d7f".to_string(),
            entities_upserted: delta.entities.len() as u32,
            blocks_upserted: delta.blocks.len() as u32,
            edges_upserted: delta.edges.len() as u32,
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
