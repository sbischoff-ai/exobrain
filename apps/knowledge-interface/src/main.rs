mod adapters;
mod domain;
mod ports;
mod service;

use std::{env, sync::Arc};

use adapters::{Neo4jGraphStore, OpenAiEmbedder, PostgresSchemaRepository, QdrantVectorStore};
use domain::{
    BlockNode, EntityNode, GraphDelta, GraphEdge, PropertyScalar, PropertyValue, SchemaType,
    UpsertSchemaTypeCommand, UpsertSchemaTypePropertyInput,
};
use service::KnowledgeApplication;
use tonic::{transport::Server, Request, Response, Status};
use tracing_subscriber::EnvFilter;

pub mod proto {
    tonic::include_proto!("exobrain.knowledge.v1");
}

use proto::knowledge_interface_server::{KnowledgeInterface, KnowledgeInterfaceServer};
use proto::{
    GetSchemaReply, GetSchemaRequest, HealthReply, HealthRequest, IngestGraphDeltaReply,
    IngestGraphDeltaRequest, UpsertSchemaTypeReply, UpsertSchemaTypeRequest,
};

const FILE_DESCRIPTOR_SET: &[u8] = tonic::include_file_descriptor_set!("knowledge_descriptor");

#[derive(Debug, Clone)]
struct AppConfig {
    app_env: String,
    log_level: String,
    metastore_dsn: String,
    memgraph_addr: String,
    qdrant_addr: String,
    openai_api_key: String,
    embedding_model: String,
}

impl AppConfig {
    fn from_env() -> Result<Self, Box<dyn std::error::Error>> {
        let _ = dotenvy::from_path_override(".env");
        let _ = dotenvy::dotenv();

        let app_env = env::var("APP_ENV").unwrap_or_else(|_| "local".to_string());
        let default_log_level = match app_env.as_str() {
            "local" => "DEBUG",
            _ => "INFO",
        };
        let log_level = env::var("LOG_LEVEL").unwrap_or_else(|_| default_log_level.to_string());
        let metastore_dsn = env::var("KNOWLEDGE_SCHEMA_DSN")
            .or_else(|_| env::var("METASTORE_DSN"))
            .map_err(|_| "KNOWLEDGE_SCHEMA_DSN or METASTORE_DSN is required")?;

        Ok(Self {
            app_env,
            log_level,
            metastore_dsn,
            memgraph_addr: env::var("MEMGRAPH_BOLT_ADDR")?,
            qdrant_addr: env::var("QDRANT_ADDR")?,
            openai_api_key: env::var("OPENAI_API_KEY")?,
            embedding_model: env::var("OPENAI_EMBEDDING_MODEL")
                .unwrap_or_else(|_| "text-embedding-3-large".to_string()),
        })
    }

    fn enable_reflection(&self) -> bool {
        self.app_env == "local"
    }
}

struct KnowledgeGrpcService {
    app: Arc<KnowledgeApplication>,
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

        let map_type = |s: SchemaType| proto::SchemaType {
            id: s.id,
            kind: s.kind,
            name: s.name,
            description: s.description,
            active: s.active,
        };

        Ok(Response::new(GetSchemaReply {
            node_types: schema
                .node_types
                .into_iter()
                .map(|node| proto::SchemaNodeType {
                    r#type: Some(map_type(node.schema_type)),
                    properties: node
                        .properties
                        .into_iter()
                        .map(|p| proto::TypeProperty {
                            owner_type_id: p.owner_type_id,
                            prop_name: p.prop_name,
                            value_type: p.value_type,
                            required: p.required,
                            readable: p.readable,
                            writable: p.writable,
                            active: p.active,
                            description: p.description,
                        })
                        .collect(),
                    parents: node
                        .parents
                        .into_iter()
                        .map(|i| proto::TypeInheritance {
                            child_type_id: i.child_type_id,
                            parent_type_id: i.parent_type_id,
                            description: i.description,
                            active: i.active,
                        })
                        .collect(),
                })
                .collect(),
            edge_types: schema
                .edge_types
                .into_iter()
                .map(|edge| proto::SchemaEdgeType {
                    r#type: Some(map_type(edge.schema_type)),
                    properties: edge
                        .properties
                        .into_iter()
                        .map(|p| proto::TypeProperty {
                            owner_type_id: p.owner_type_id,
                            prop_name: p.prop_name,
                            value_type: p.value_type,
                            required: p.required,
                            readable: p.readable,
                            writable: p.writable,
                            active: p.active,
                            description: p.description,
                        })
                        .collect(),
                    rules: edge
                        .rules
                        .into_iter()
                        .map(|r| proto::EdgeEndpointRule {
                            edge_type_id: r.edge_type_id,
                            from_node_type_id: r.from_node_type_id,
                            to_node_type_id: r.to_node_type_id,
                            active: r.active,
                            description: r.description,
                        })
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
            schema_type: Some(proto::SchemaType {
                id: upserted.id,
                kind: upserted.kind,
                name: upserted.name,
                description: upserted.description,
                active: upserted.active,
            }),
        }))
    }

    async fn ingest_graph_delta(
        &self,
        request: Request<IngestGraphDeltaRequest>,
    ) -> Result<Response<IngestGraphDeltaReply>, Status> {
        let payload = request.into_inner();

        let entities: Vec<EntityNode> = payload
            .entities
            .into_iter()
            .map(|entity| {
                Ok(EntityNode {
                    id: entity.id,
                    labels: entity.labels,
                    universe_id: entity.universe_id,
                    properties: entity
                        .properties
                        .into_iter()
                        .map(map_property_value)
                        .collect::<Result<Vec<_>, _>>()?,
                })
            })
            .collect::<Result<Vec<_>, Status>>()?;

        let blocks: Vec<BlockNode> = payload
            .blocks
            .into_iter()
            .map(|block| {
                Ok(BlockNode {
                    id: block.id,
                    labels: block.labels,
                    root_entity_id: block.root_entity_id,
                    properties: block
                        .properties
                        .into_iter()
                        .map(map_property_value)
                        .collect::<Result<Vec<_>, _>>()?,
                })
            })
            .collect::<Result<Vec<_>, Status>>()?;

        let edges: Vec<GraphEdge> = payload
            .edges
            .into_iter()
            .map(|edge| {
                Ok(GraphEdge {
                    from_id: edge.from_id,
                    to_id: edge.to_id,
                    edge_type: edge.edge_type,
                    properties: edge
                        .properties
                        .into_iter()
                        .map(map_property_value)
                        .collect::<Result<Vec<_>, _>>()?,
                })
            })
            .collect::<Result<Vec<_>, Status>>()?;

        self.app
            .ingest_graph_delta(GraphDelta {
                universe_id: payload.universe_id,
                entities: entities.clone(),
                blocks: blocks.clone(),
                edges: edges.clone(),
            })
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        Ok(Response::new(IngestGraphDeltaReply {
            entities_upserted: entities.len() as u32,
            blocks_upserted: blocks.len() as u32,
            edges_upserted: edges.len() as u32,
        }))
    }
}

fn map_property_value(value: proto::PropertyValue) -> Result<PropertyValue, Status> {
    let scalar = match value
        .value
        .ok_or_else(|| Status::invalid_argument("property value is required"))?
    {
        proto::property_value::Value::StringValue(v) => PropertyScalar::String(v),
        proto::property_value::Value::FloatValue(v) => PropertyScalar::Float(v),
        proto::property_value::Value::IntValue(v) => PropertyScalar::Int(v),
        proto::property_value::Value::BoolValue(v) => PropertyScalar::Bool(v),
        proto::property_value::Value::DatetimeValue(v) => PropertyScalar::Datetime(v),
        proto::property_value::Value::JsonValue(v) => PropertyScalar::Json(v),
    };

    Ok(PropertyValue {
        key: value.key,
        value: scalar,
    })
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cfg = AppConfig::from_env()?;
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::new(cfg.log_level.clone()))
        .init();

    let addr = "0.0.0.0:50051".parse()?;

    let schema_repo = Arc::new(PostgresSchemaRepository::new(&cfg.metastore_dsn).await?);
    let graph_store = Arc::new(Neo4jGraphStore::new(&cfg.memgraph_addr).await?);
    let embedder = Arc::new(OpenAiEmbedder::new(
        cfg.openai_api_key.clone(),
        cfg.embedding_model.clone(),
    ));
    let vector_store = Arc::new(QdrantVectorStore::new(&cfg.qdrant_addr, "blocks")?);

    let app = Arc::new(KnowledgeApplication::new(
        schema_repo,
        graph_store,
        embedder,
        vector_store,
    ));

    let grpc = KnowledgeInterfaceServer::new(KnowledgeGrpcService { app });

    if cfg.enable_reflection() {
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
    use super::AppConfig;

    #[test]
    fn reflection_enabled_for_local() {
        let cfg = AppConfig {
            app_env: "local".to_string(),
            log_level: "DEBUG".to_string(),
            metastore_dsn: "postgresql://example".to_string(),
            memgraph_addr: "bolt://example".to_string(),
            qdrant_addr: "http://example".to_string(),
            openai_api_key: "x".to_string(),
            embedding_model: "text-embedding-3-large".to_string(),
        };

        assert!(cfg.enable_reflection());
    }

    #[test]
    fn reflection_disabled_for_non_local() {
        let cfg = AppConfig {
            app_env: "cluster".to_string(),
            log_level: "INFO".to_string(),
            metastore_dsn: "postgresql://example".to_string(),
            memgraph_addr: "bolt://example".to_string(),
            qdrant_addr: "http://example".to_string(),
            openai_api_key: "x".to_string(),
            embedding_model: "text-embedding-3-large".to_string(),
        };

        assert!(!cfg.enable_reflection());
    }
}
