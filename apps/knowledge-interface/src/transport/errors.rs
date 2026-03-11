use tonic::Status;
use tracing::warn;

use crate::application::errors::ApplicationError;

pub fn map_application_error(error: ApplicationError) -> Status {
    warn!(error = %error, "application request failed");

    match error {
        ApplicationError::Validation(message) => Status::invalid_argument(message),
        ApplicationError::FailedPrecondition(message) => Status::failed_precondition(message),
        ApplicationError::Internal(error) => Status::internal(error.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use tonic::Code;

    use super::map_application_error;
    use crate::application::errors::ApplicationError;

    #[test]
    fn maps_validation_error_to_invalid_argument() {
        let status = map_application_error(ApplicationError::validation("bad input"));
        assert_eq!(status.code(), Code::InvalidArgument);
    }

    #[test]
    fn maps_precondition_error_to_failed_precondition() {
        let status = map_application_error(ApplicationError::failed_precondition("state conflict"));
        assert_eq!(status.code(), Code::FailedPrecondition);
    }

    #[test]
    fn maps_internal_error_to_internal() {
        let status = map_application_error(ApplicationError::from(anyhow::anyhow!("boom")));
        assert_eq!(status.code(), Code::Internal);
    }
}
