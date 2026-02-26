mod adapters;
mod domain;
mod ports;
mod service;

use std::{env, sync::Arc};

use adapters::{
    MemgraphQdrantGraphRepository, MockEmbedder, Neo4jGraphStore, OpenAiEmbedder,
    PostgresSchemaRepository, QdrantVectorStore,
};
use domain::{
    BlockNode, EntityNode, GraphDelta, GraphEdge, PropertyScalar, PropertyValue, SchemaType,
    UniverseNode, UpsertSchemaTypeCommand, UpsertSchemaTypePropertyInput, Visibility,
};
use service::KnowledgeApplication;
use tonic::{transport::Server, Request, Response, Status};
use tracing::warn;
use tracing_subscriber::EnvFilter;

pub mod proto {
    tonic::include_proto!("exobrain.knowledge.v1");
}

use proto::knowledge_interface_server::{KnowledgeInterface, KnowledgeInterfaceServer};
use proto::{
    GetSchemaReply, GetSchemaRequest, HealthReply, HealthRequest, InitializeUserGraphReply,
    InitializeUserGraphRequest, UpsertGraphDeltaReply, UpsertGraphDeltaRequest,
    UpsertSchemaTypeReply, UpsertSchemaTypeRequest,
};

const FILE_DESCRIPTOR_SET: &[u8] = tonic::include_file_descriptor_set!("knowledge_descriptor");

#[derive(Debug, Clone)]
struct AppConfig {
    app_env: String,
    log_level: String,
    metastore_dsn: String,
    memgraph_addr: String,
    memgraph_database: String,
    qdrant_addr: String,
    openai_api_key: Option<String>,
    embedding_model: String,
    use_mock_embedder: bool,
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
            memgraph_database: env::var("MEMGRAPH_DB").unwrap_or_else(|_| "memgraph".to_string()),
            qdrant_addr: env::var("QDRANT_ADDR")?,
            openai_api_key: env::var("OPENAI_API_KEY").ok(),
            embedding_model: env::var("OPENAI_EMBEDDING_MODEL")
                .unwrap_or_else(|_| "text-embedding-3-large".to_string()),
            use_mock_embedder: env::var("EMBEDDING_USE_MOCK")
                .map(|v| v.eq_ignore_ascii_case("true") || v == "1")
                .unwrap_or(false),
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

    async fn upsert_graph_delta(
        &self,
        request: Request<UpsertGraphDeltaRequest>,
    ) -> Result<Response<UpsertGraphDeltaReply>, Status> {
        let payload = request.into_inner();

        let universes: Vec<UniverseNode> = payload
            .universes
            .into_iter()
            .map(|universe| {
                Ok(UniverseNode {
                    id: universe.id,
                    name: universe.name,
                    user_id: universe.user_id,
                    visibility: map_visibility(universe.visibility)?,
                })
            })
            .collect::<Result<Vec<_>, Status>>()?;

        let entities: Vec<EntityNode> = payload
            .entities
            .into_iter()
            .map(|entity| {
                Ok(EntityNode {
                    id: entity.id,
                    type_id: entity.type_id,
                    universe_id: entity.universe_id,
                    user_id: entity.user_id,
                    visibility: map_visibility(entity.visibility)?,
                    properties: entity
                        .properties
                        .into_iter()
                        .map(map_property_value)
                        .collect::<Result<Vec<_>, _>>()?,
                    resolved_labels: vec![],
                })
            })
            .collect::<Result<Vec<_>, Status>>()?;

        let blocks: Vec<BlockNode> = payload
            .blocks
            .into_iter()
            .map(|block| {
                Ok(BlockNode {
                    id: block.id,
                    type_id: block.type_id,
                    user_id: block.user_id,
                    visibility: map_visibility(block.visibility)?,
                    properties: block
                        .properties
                        .into_iter()
                        .map(map_property_value)
                        .collect::<Result<Vec<_>, _>>()?,
                    resolved_labels: vec![],
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
                    user_id: edge.user_id,
                    visibility: map_visibility(edge.visibility)?,
                    properties: edge
                        .properties
                        .into_iter()
                        .map(map_property_value)
                        .collect::<Result<Vec<_>, _>>()?,
                })
            })
            .collect::<Result<Vec<_>, Status>>()?;

        self.app
            .upsert_graph_delta(GraphDelta {
                user_id: payload.user_id,
                visibility: map_visibility(payload.visibility)?,
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

fn map_visibility(value: i32) -> Result<Visibility, Status> {
    let visibility = proto::Visibility::try_from(value)
        .map_err(|_| Status::invalid_argument("visibility is invalid"))?;

    match visibility {
        proto::Visibility::Private => Ok(Visibility::Private),
        proto::Visibility::Shared => Ok(Visibility::Shared),
        proto::Visibility::Unspecified => Err(Status::invalid_argument("visibility is required")),
    }
}

fn map_ingest_error(error: anyhow::Error) -> Status {
    let message = error.to_string();
    warn!(error = %message, "upsert graph delta failed");

    if message.contains("validation failed")
        || message.contains("is required")
        || message.contains("must")
        || message.contains("unknown schema type")
        || message.contains("failed to upsert edge")
    {
        return Status::invalid_argument(message);
    }

    Status::internal(message)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cfg = AppConfig::from_env()?;
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::new(cfg.log_level.clone()))
        .init();

    let addr = "0.0.0.0:50051".parse()?;

    let schema_repo = Arc::new(PostgresSchemaRepository::new(&cfg.metastore_dsn).await?);
    let graph_store = Neo4jGraphStore::new(&cfg.memgraph_addr, &cfg.memgraph_database).await?;
    let vector_store = QdrantVectorStore::new(&cfg.qdrant_addr, "blocks")?;
    let graph_repository = Arc::new(MemgraphQdrantGraphRepository::new(
        graph_store,
        vector_store,
    ));

    let embedder: Arc<dyn ports::Embedder> =
        if cfg.use_mock_embedder || cfg.openai_api_key.is_none() {
            Arc::new(MockEmbedder)
        } else {
            Arc::new(OpenAiEmbedder::new(
                cfg.openai_api_key.clone().expect("checked api key"),
                cfg.embedding_model.clone(),
            ))
        };

    let app = Arc::new(KnowledgeApplication::new(
        schema_repo,
        graph_repository,
        embedder,
    ));

    app.ensure_common_root_graph().await?;

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
            memgraph_database: "memgraph".to_string(),
            qdrant_addr: "http://example".to_string(),
            openai_api_key: Some("x".to_string()),
            embedding_model: "text-embedding-3-large".to_string(),
            use_mock_embedder: false,
        };

        assert!(cfg.enable_reflection());
    }

    #[test]
    fn defaults_memgraph_database_to_memgraph() {
        std::env::set_var("APP_ENV", "local");
        std::env::set_var("KNOWLEDGE_SCHEMA_DSN", "postgresql://example");
        std::env::set_var("MEMGRAPH_BOLT_ADDR", "bolt://example");
        std::env::remove_var("MEMGRAPH_DB");
        std::env::set_var("QDRANT_ADDR", "http://example");
        std::env::set_var("OPENAI_API_KEY", "x");

        let cfg = AppConfig::from_env().expect("config should load");

        assert_eq!(cfg.memgraph_database, "memgraph");
    }

    #[test]
    fn reflection_disabled_for_non_local() {
        let cfg = AppConfig {
            app_env: "cluster".to_string(),
            log_level: "INFO".to_string(),
            metastore_dsn: "postgresql://example".to_string(),
            memgraph_addr: "bolt://example".to_string(),
            memgraph_database: "memgraph".to_string(),
            qdrant_addr: "http://example".to_string(),
            openai_api_key: Some("x".to_string()),
            embedding_model: "text-embedding-3-large".to_string(),
            use_mock_embedder: false,
        };

        assert!(!cfg.enable_reflection());
    }
}
