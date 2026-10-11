//! Protected Linux persistence. Requests contain data, never host configuration.
#![forbid(unsafe_code)]
mod error;
mod model;
#[cfg(unix)]
mod storage;
mod transaction;
pub use error::ActivationError;
pub use model::*;
pub use transaction::{ActivationOutcome, ProtectedHost, ProtectedState, check_installed_runtime};
