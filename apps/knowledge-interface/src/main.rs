mod application;
mod config;
mod domain;
mod infrastructure;
mod ports;
mod presentation;
mod transport;

use std::sync::Arc;

use application::KnowledgeApplication;
use config::AppConfig;
use infrastructure::{
    embedding::{MockEmbedder, OpenAiCompatibleEmbedder},
    memgraph::{MemgraphQdrantGraphRepository, Neo4jGraphStore},
    postgres::PostgresSchemaRepository,
    qdrant::{QdrantTypeVectorStore, QdrantVectorStore},
};
use tracing_subscriber::EnvFilter;
use transport::grpc::run_server;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cfg = AppConfig::from_env()?;
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::new(cfg.log_level.clone()))
        .init();

    let schema_repo = Arc::new(PostgresSchemaRepository::new(&cfg.metastore_dsn).await?);
    let graph_store = Neo4jGraphStore::new(&cfg.memgraph_addr, &cfg.memgraph_database).await?;
    let vector_store = QdrantVectorStore::new(&cfg.qdrant_addr, "blocks")?;
    let graph_repository = Arc::new(MemgraphQdrantGraphRepository::new(
        graph_store,
        vector_store,
    ));
    let type_vector_repository = Arc::new(QdrantTypeVectorStore::new(&cfg.qdrant_addr)?);

    let embedder: Arc<dyn ports::Embedder> = if cfg.use_mock_embedder {
        Arc::new(MockEmbedder)
    } else {
        Arc::new(OpenAiCompatibleEmbedder::new(
            cfg.model_provider_base_url.clone(),
            cfg.embedding_model_alias.clone(),
        ))
    };

    let app = Arc::new(
        KnowledgeApplication::new(schema_repo, graph_repository, embedder)
            .with_type_vector_repository(type_vector_repository),
    );

    app.ensure_common_root_graph().await?;
    run_server(app, cfg.enable_reflection()).await
}
