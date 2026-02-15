use tonic::{transport::Server, Request, Response, Status};

pub mod proto {
    tonic::include_proto!("exobrain.knowledge.v1");
}

use proto::knowledge_interface_server::{KnowledgeInterface, KnowledgeInterfaceServer};
use proto::{HealthReply, HealthRequest};

#[derive(Default)]
struct KnowledgeService;

#[tonic::async_trait]
impl KnowledgeInterface for KnowledgeService {
    async fn health(
        &self,
        _request: Request<HealthRequest>,
    ) -> Result<Response<HealthReply>, Status> {
        Ok(Response::new(HealthReply {
            status: "ok".to_string(),
        }))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = "0.0.0.0:50051".parse()?;
    let service = KnowledgeService::default();

    Server::builder()
        .add_service(KnowledgeInterfaceServer::new(service))
        .serve(addr)
        .await?;

    Ok(())
}
