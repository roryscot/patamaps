use patamaps_core::{CheckError, Issue};

#[derive(Debug, thiserror::Error)]
pub enum ActivationError {
    #[error("{0}")]
    Check(#[from] CheckError),
    #[error("{0}")]
    Contract(#[from] patamaps_contracts::ContractError),
    #[error("{0}")]
    Io(#[from] std::io::Error),
    #[error("{code}: {message}")]
    Refusal {
        code: &'static str,
        message: &'static str,
    },
}
impl ActivationError {
    pub fn code(&self) -> &str {
        match self {
            Self::Check(e) => {
                e.0.first()
                    .map_or("ACTIVATION_CHECK_FAILED", |i| i.code.as_str())
            }
            Self::Contract(_) => "ACTIVATION_INVALID_RECORD",
            Self::Io(_) => "ACTIVATION_IO_ERROR",
            Self::Refusal { code, .. } => code,
        }
    }
    pub fn issues(&self) -> Vec<Issue> {
        match self {
            Self::Check(e) => e.0.clone(),
            _ => vec![Issue::error(self.code(), self.to_string(), "activation")],
        }
    }
}
pub(crate) type Result<T> = std::result::Result<T, ActivationError>;
pub(crate) fn fail<T>(code: &'static str, message: &'static str) -> Result<T> {
    Err(ActivationError::Refusal { code, message })
}
