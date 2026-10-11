#![forbid(unsafe_code)]

mod admission;
mod control;
mod derivation;
mod diff;
mod graph;
mod impact;
mod laws;
mod preflight;
mod risk;
mod topology;
mod uncertainty;

pub use admission::{
    AdmittedGeneration, EvaluationOptions, GenerationRecord, admit, admit_controlled,
};
pub use control::{CancellationToken, WorkControl};
pub use derivation::{
    CheckedDerivations, CompositionOutcome, DerivationFailure, DerivationStatus, UncertaintyInputs,
    check_derivations, check_derivations_with_inputs, derive,
};
pub use diff::{RecordDelta, diff};
pub use graph::identifier as valid_identifier;
pub use graph::object_bounds as check_metadata_bounds;
pub use graph::{
    AuthorityResolution, CheckError, CheckedGraph, Direction, Issue, Severity, TraceVisit, compose,
};
pub use impact::{ImpactReport, ImpactStep, ImpactVisit, impact};
pub use preflight::{check_input_bounds, check_value_bounds};
pub use risk::project_semantics;
