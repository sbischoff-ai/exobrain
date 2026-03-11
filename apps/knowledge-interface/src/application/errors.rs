use thiserror::Error;

#[derive(Debug, Error)]
pub enum ApplicationError {
    #[error("{0}")]
    Validation(String),
    #[error("{0}")]
    FailedPrecondition(String),
    #[error(transparent)]
    Internal(#[from] anyhow::Error),
}

pub type ApplicationResult<T> = Result<T, ApplicationError>;

impl ApplicationError {
    pub fn validation(message: impl Into<String>) -> Self {
        Self::Validation(message.into())
    }

    pub fn failed_precondition(message: impl Into<String>) -> Self {
        Self::FailedPrecondition(message.into())
    }
}
