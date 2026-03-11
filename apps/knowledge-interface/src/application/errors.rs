use anyhow::Error as AnyhowError;
use thiserror::Error;

pub type AppResult<T> = Result<T, ApplicationError>;

#[derive(Debug, Error)]
pub enum ApplicationError {
    #[error("{0}")]
    Validation(String),
    #[error("{0}")]
    FailedPrecondition(String),
    #[error("internal failure")]
    Internal(#[source] AnyhowError),
}

impl ApplicationError {
    pub fn validation(message: impl Into<String>) -> Self {
        Self::Validation(message.into())
    }

    pub fn failed_precondition(message: impl Into<String>) -> Self {
        Self::FailedPrecondition(message.into())
    }
}

impl From<AnyhowError> for ApplicationError {
    fn from(value: AnyhowError) -> Self {
        Self::Internal(value)
    }
}
