pub mod errors;
pub mod grpc;
pub mod mappers;

pub mod proto {
    tonic::include_proto!("exobrain.knowledge.v1");
}

pub const FILE_DESCRIPTOR_SET: &[u8] = tonic::include_file_descriptor_set!("knowledge_descriptor");
