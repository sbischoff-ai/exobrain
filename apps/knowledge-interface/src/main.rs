mod adapters;
mod domain;
mod ports;
mod service;

use std::{env, sync::Arc};

use adapters::{Neo4jGraphStore, OpenAiEmbedder, PostgresSchemaRepository, QdrantVectorStore};
use service::KnowledgeApplication;
use tonic::{transport::Server, Request, Response, Status};

pub mod proto {
    tonic::include_proto!("exobrain.knowledge.v1");
}

use domain::{BlockNode, EntityNode, GraphDelta, GraphEdge, SchemaType, TimeWindow};
use proto::knowledge_interface_server::{KnowledgeInterface, KnowledgeInterfaceServer};
use proto::{
    GetSchemaReply, GetSchemaRequest, HealthReply, HealthRequest, IngestGraphDeltaReply,
    IngestGraphDeltaRequest, UpsertSchemaTypeReply, UpsertSchemaTypeRequest,
};

const FILE_DESCRIPTOR_SET: &[u8] = tonic::include_file_descriptor_set!("knowledge_descriptor");

#[derive(Debug, Clone)]
struct AppConfig {
    app_env: String,
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
        let metastore_dsn = env::var("KNOWLEDGE_SCHEMA_DSN")
            .or_else(|_| env::var("METASTORE_DSN"))
            .map_err(|_| "KNOWLEDGE_SCHEMA_DSN or METASTORE_DSN is required")?;

        Ok(Self {
            app_env,
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
        let (node_types, edge_types, block_types) = self
            .app
            .get_schema()
            .await
            .map_err(|e| Status::internal(e.to_string()))?;

        let map_proto = |s: SchemaType| proto::SchemaType {
            id: s.id,
            kind: s.kind,
            name: s.name,
            description: s.description,
            active: s.active,
        };

        Ok(Response::new(GetSchemaReply {
            node_types: node_types.into_iter().map(map_proto).collect(),
            edge_types: edge_types.into_iter().map(map_proto).collect(),
            block_types: block_types.into_iter().map(map_proto).collect(),
        }))
    }

    async fn upsert_schema_type(
        &self,
        request: Request<UpsertSchemaTypeRequest>,
    ) -> Result<Response<UpsertSchemaTypeReply>, Status> {
        let payload = request.into_inner();
        let upserted = self
            .app
            .upsert_schema_type(SchemaType {
                id: payload.id,
                kind: payload.kind,
                name: payload.name,
                description: payload.description,
                active: payload.active,
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
            .map(|entity| EntityNode {
                id: entity.id,
                name: entity.name,
                labels: entity.labels,
                universe_id: entity.universe_id,
                time_window: entity.time_window.map(|tw| TimeWindow {
                    start: non_empty(tw.start),
                    end: non_empty(tw.end),
                    due: non_empty(tw.due),
                }),
            })
            .collect();

        let blocks: Vec<BlockNode> = payload
            .blocks
            .into_iter()
            .map(|block| BlockNode {
                id: block.id,
                text: block.text,
                labels: block.labels,
                root_entity_id: block.root_entity_id,
                confidence: block.confidence,
                status: block.status,
            })
            .collect();

        let edges: Vec<GraphEdge> = payload
            .edges
            .into_iter()
            .map(|edge| GraphEdge {
                from_id: edge.from_id,
                to_id: edge.to_id,
                edge_type: edge.edge_type,
                confidence: edge.confidence,
                status: edge.status,
                context: edge.context,
            })
            .collect();

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

fn non_empty(input: String) -> Option<String> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cfg = AppConfig::from_env()?;
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
            metastore_dsn: "postgresql://example".to_string(),
            memgraph_addr: "bolt://example".to_string(),
            qdrant_addr: "http://example".to_string(),
            openai_api_key: "x".to_string(),
            embedding_model: "text-embedding-3-large".to_string(),
        };

        assert!(!cfg.enable_reflection());
    }
}
