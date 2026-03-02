use std::collections::HashMap;
use std::sync::Arc;

use tonic::{transport::Server, Request, Response, Status};

use crate::domain::{SchemaType, UpsertSchemaTypeCommand, UpsertSchemaTypePropertyInput};
use crate::service::KnowledgeApplication;

use super::errors::map_ingest_error;
use super::mappers::{
    to_domain_block_node, to_domain_entity_node, to_domain_find_entity_candidates_query,
    to_domain_get_entity_context_query, to_domain_graph_edge, to_domain_universe_node,
    to_proto_edge_endpoint_rule, to_proto_entity_candidate, to_proto_get_entity_context_reply,
    to_proto_schema_type, to_proto_type_inheritance, to_proto_type_property,
};
use super::proto::knowledge_interface_server::{KnowledgeInterface, KnowledgeInterfaceServer};
use super::proto::{
    AllowedEdge, ExtractionEntityType, FindEntityCandidatesReply, FindEntityCandidatesRequest,
    GetEntityContextReply, GetEntityContextRequest, GetExtractionSchemaContextReply,
    GetExtractionSchemaContextRequest, GetSchemaReply, GetSchemaRequest, GetUserInitGraphReply,
    GetUserInitGraphRequest, HealthReply, HealthRequest, UpsertGraphDeltaReply,
    UpsertGraphDeltaRequest, UpsertSchemaTypeReply, UpsertSchemaTypeRequest,
};
use super::FILE_DESCRIPTOR_SET;

pub struct KnowledgeGrpcService {
    pub app: Arc<KnowledgeApplication>,
}

#[derive(Debug, Clone)]
struct ExtractionSchemaOptions {
    include_edge_properties: bool,
    include_inactive: bool,
}

fn build_extraction_entity_types(
    schema: crate::domain::FullSchema,
    options: ExtractionSchemaOptions,
) -> Vec<ExtractionEntityType> {
    let _include_edge_properties = options.include_edge_properties;
    let node_types = schema.node_types;
    let edge_types = schema.edge_types;

    let type_name_by_id: HashMap<String, String> = node_types
        .iter()
        .map(|node| (node.schema_type.id.clone(), node.schema_type.name.clone()))
        .collect();

    let parent_by_child: HashMap<String, String> = node_types
        .iter()
        .flat_map(|node| {
            node.parents
                .iter()
                .filter(move |parent| options.include_inactive || parent.active)
                .map(|parent| (node.schema_type.id.clone(), parent.parent_type_id.clone()))
        })
        .collect();

    let edge_meta_by_id: HashMap<String, (String, String)> = edge_types
        .iter()
        .filter(|edge| options.include_inactive || edge.schema_type.active)
        .map(|edge| {
            (
                edge.schema_type.id.clone(),
                (
                    edge.schema_type.name.clone(),
                    edge.schema_type.description.clone(),
                ),
            )
        })
        .collect();

    node_types
        .into_iter()
        .filter(|node| node.schema_type.kind == "node")
        .filter(|node| options.include_inactive || node.schema_type.active)
        .map(|node| {
            let mut inheritance_chain = vec![node.schema_type.id.clone()];
            let mut current = node.schema_type.id.clone();
            while let Some(parent_id) = parent_by_child.get(&current) {
                inheritance_chain.push(parent_id.clone());
                current = parent_id.clone();
            }
            inheritance_chain.reverse();

            let outgoing_edges = edge_types
                .iter()
                .flat_map(|edge| edge.rules.iter())
                .filter(|rule| options.include_inactive || rule.active)
                .filter(|rule| rule.from_node_type_id == node.schema_type.id)
                .filter_map(|rule| {
                    let (edge_name, edge_description) =
                        edge_meta_by_id.get(&rule.edge_type_id)?.clone();
                    Some(AllowedEdge {
                        edge_type_id: rule.edge_type_id.clone(),
                        edge_name,
                        edge_description,
                        other_entity_type_id: rule.to_node_type_id.clone(),
                        other_entity_type_name: type_name_by_id
                            .get(&rule.to_node_type_id)
                            .cloned()
                            .unwrap_or_default(),
                        min_cardinality: None,
                        max_cardinality: None,
                    })
                })
                .collect();

            let incoming_edges = edge_types
                .iter()
                .flat_map(|edge| edge.rules.iter())
                .filter(|rule| options.include_inactive || rule.active)
                .filter(|rule| rule.to_node_type_id == node.schema_type.id)
                .filter_map(|rule| {
                    let (edge_name, edge_description) =
                        edge_meta_by_id.get(&rule.edge_type_id)?.clone();
                    Some(AllowedEdge {
                        edge_type_id: rule.edge_type_id.clone(),
                        edge_name,
                        edge_description,
                        other_entity_type_id: rule.from_node_type_id.clone(),
                        other_entity_type_name: type_name_by_id
                            .get(&rule.from_node_type_id)
                            .cloned()
                            .unwrap_or_default(),
                        min_cardinality: None,
                        max_cardinality: None,
                    })
                })
                .collect();

            ExtractionEntityType {
                type_id: node.schema_type.id,
                name: node.schema_type.name,
                description: node.schema_type.description,
                inheritance_chain,
                outgoing_edges,
                incoming_edges,
            }
        })
        .collect()
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

        let entity_types = build_extraction_entity_types(
            schema,
            ExtractionSchemaOptions {
                include_edge_properties: payload.include_edge_properties.unwrap_or(false),
                include_inactive: payload.include_inactive.unwrap_or(false),
            },
        );

        Ok(Response::new(GetExtractionSchemaContextReply {
            entity_types,
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
    use super::{build_extraction_entity_types, ExtractionSchemaOptions};
    use crate::domain::{
        EdgeEndpointRule, FullSchema, SchemaEdgeTypeHydrated, SchemaNodeTypeHydrated, SchemaType,
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
}
