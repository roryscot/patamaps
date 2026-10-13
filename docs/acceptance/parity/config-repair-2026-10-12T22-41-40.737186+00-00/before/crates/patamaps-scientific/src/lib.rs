//! Native, source-preserving scientific ingress. Assertions are not checked truth.
#![forbid(unsafe_code)]
mod crate_export;
mod export;
mod graph;
mod interpret;
mod model;
mod source;
mod syntax;
pub use crate_export::{
    CheckedScientificCrate, CrateOptions, ExternalSource, ScientificCrate, create_crate,
    scientific_engine_id, verify_crate,
};
pub use export::export_tsv;
pub use graph::{ImportOptions, import_graph, predicate_relation, scientific_pack};
pub use interpret::{
    builtin_prefixes, check_document, check_document_compatible, expand_curie, parse_tsv,
    parse_tsv_compatible,
};
pub use model::*;
pub use source::{SssomSourceConfig, parse_sssom_source_config, propagatable_slots};

#[derive(Debug, thiserror::Error)]
#[error("{code}: {message}")]
pub struct Error {
    pub code: &'static str,
    pub message: String,
}
impl Error {
    pub(crate) fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
}
pub type Result<T> = std::result::Result<T, Error>;
pub(crate) fn refuse<T>(code: &'static str, message: &str) -> Result<T> {
    Err(Error::new(code, message))
}
impl From<patamaps_contracts::ContractError> for Error {
    fn from(e: patamaps_contracts::ContractError) -> Self {
        Self::new("SSSOM_CONTRACT", e.to_string())
    }
}
impl From<patamaps_core::CheckError> for Error {
    fn from(e: patamaps_core::CheckError) -> Self {
        Self::new("SSSOM_KERNEL", e.to_string())
    }
}
