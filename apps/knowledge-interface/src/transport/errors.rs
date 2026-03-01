use anyhow::Error;
use tonic::Status;
use tracing::warn;

pub fn map_ingest_error(error: Error) -> Status {
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
