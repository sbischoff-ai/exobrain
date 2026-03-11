use tonic::Status;
use tracing::warn;

use crate::application::errors::ApplicationError;

pub fn map_application_error(error: ApplicationError) -> Status {
    match error {
        ApplicationError::Validation(message) => Status::invalid_argument(message),
        ApplicationError::FailedPrecondition(message) => Status::failed_precondition(message),
        ApplicationError::Internal(source) => {
            warn!(error = %source, "application request failed");
            Status::internal("internal failure")
        }
    }
}

#[cfg(test)]
mod tests {
    use anyhow::anyhow;
    use tonic::Code;

    use super::map_application_error;
    use crate::application::errors::ApplicationError;

    #[test]
    fn maps_validation_to_invalid_argument() {
        let status = map_application_error(ApplicationError::validation("bad request"));
        assert_eq!(status.code(), Code::InvalidArgument);
        assert_eq!(status.message(), "bad request");
    }

    #[test]
    fn maps_failed_precondition_variant() {
        let status = map_application_error(ApplicationError::failed_precondition("missing state"));
        assert_eq!(status.code(), Code::FailedPrecondition);
        assert_eq!(status.message(), "missing state");
    }

    #[test]
    fn maps_internal_to_sanitized_internal_status() {
        let status = map_application_error(ApplicationError::from(anyhow!("db is down")));
        assert_eq!(status.code(), Code::Internal);
        assert_eq!(status.message(), "internal failure");
    }
}
