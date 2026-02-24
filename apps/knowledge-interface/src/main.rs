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
    let addr = "0.0.0.0:50051".parse()?;
    let metastore_dsn = env::var("KNOWLEDGE_SCHEMA_DSN")
        .or_else(|_| env::var("METASTORE_DSN"))
        .expect("KNOWLEDGE_SCHEMA_DSN or METASTORE_DSN is required");
    let memgraph_addr = env::var("MEMGRAPH_BOLT_ADDR").expect("MEMGRAPH_BOLT_ADDR is required");
    let qdrant_addr = env::var("QDRANT_ADDR").expect("QDRANT_ADDR is required");
    let openai_api_key = env::var("OPENAI_API_KEY").expect("OPENAI_API_KEY is required");
    let embedding_model =
        env::var("OPENAI_EMBEDDING_MODEL").unwrap_or_else(|_| "text-embedding-3-small".to_string());

    let schema_repo = Arc::new(PostgresSchemaRepository::new(&metastore_dsn).await?);
    let graph_store = Arc::new(Neo4jGraphStore::new(&memgraph_addr).await?);
    let embedder = Arc::new(OpenAiEmbedder::new(openai_api_key, embedding_model));
    let vector_store = Arc::new(QdrantVectorStore::new(&qdrant_addr, "blocks")?);

    let app = Arc::new(KnowledgeApplication::new(
        schema_repo,
        graph_store,
        embedder,
        vector_store,
    ));
    app.ensure_schema().await?;

    Server::builder()
        .add_service(KnowledgeInterfaceServer::new(KnowledgeGrpcService { app }))
        .serve(addr)
        .await?;

    Ok(())
}
