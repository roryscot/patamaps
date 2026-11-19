#![forbid(unsafe_code)]

/// Draft graph records used by the in-process kernel.
pub use patamaps_contracts as model;

mod admission;
mod build_observations;
pub use build_observations::observation_matches;
mod constraints;
mod control;
mod derivation;
mod diff;
mod graph;
mod impact;
mod laws;
#[cfg(feature = "legacy-compat")]
mod legacy_cli;
#[cfg(feature = "legacy-compat")]
mod legacy_composition;
#[cfg(feature = "legacy-compat")]
mod legacy_constraints;
#[cfg(feature = "legacy-compat")]
mod legacy_correspondence;
#[cfg(feature = "legacy-compat")]
mod legacy_evaluation;
#[cfg(feature = "legacy-compat")]
pub use legacy_evaluation::legacy_evaluation_request;
#[cfg(feature = "legacy-compat")]
mod legacy_graph;
#[cfg(feature = "legacy-compat")]
mod legacy_pack;
#[cfg(feature = "legacy-compat")]
mod legacy_projection;
#[cfg(feature = "legacy-compat")]
pub use legacy_pack::LegacyPortableSchema;
#[cfg(feature = "legacy-compat")]
mod legacy_references;
#[cfg(feature = "legacy-compat")]
mod legacy_registry;
#[cfg(feature = "legacy-compat")]
mod legacy_reporting;
#[cfg(feature = "legacy-compat")]
mod legacy_semantic;
#[cfg(feature = "legacy-compat")]
mod legacy_validation;
#[cfg(feature = "legacy-compat")]
mod legacy_viability;
#[cfg(feature = "legacy-compat")]
pub use legacy_viability::legacy_viability_request;
#[cfg(feature = "legacy-compat")]
mod legacy_workspace;
#[cfg(feature = "legacy-compat")]
pub use legacy_workspace::{
    LegacyWorkspaceError, LegacyWorkspaceRequest, legacy_workspace_request,
};
#[cfg(feature = "legacy-compat")]
mod legacy_uncertainty_risk;
mod preflight;
mod registry;
mod risk;
mod topology;
mod uncertainty;

pub use admission::{
    AdmittedGeneration, EvaluationOptions, GenerationRecord, admit, admit_controlled,
    admit_with_constraints,
};
pub use constraints::{
    ConstraintEvaluationContext, ConstraintEvaluator, ConstraintEvaluatorBinding,
    ConstraintRegistry, ConstraintRegistryError,
};
pub use control::{CancellationToken, WorkControl};
pub use derivation::{
    CheckedDerivations, CompositionOutcome, DerivationFailure, DerivationStatus, UncertaintyInputs,
    check_derivations, check_derivations_with_inputs, derive,
};
pub use diff::{RecordDelta, diff};
pub use graph::identifier as valid_identifier;
pub use graph::object_bounds as check_metadata_bounds;
pub use graph::object_bounds_with_limits as check_metadata_bounds_with_limits;
pub use graph::{
    AuthorityResolution, CheckError, CheckedGraph, Direction, Issue, Severity, TraceVisit, compose,
};
pub use impact::{ImpactReport, ImpactStep, ImpactVisit, impact, impact_admitted};
#[cfg(feature = "legacy-compat")]
pub use legacy_composition::{
    LegacyCompositionError, LegacyCompositionRequest, compose_legacy_documents,
};
#[cfg(feature = "legacy-compat")]
pub use legacy_correspondence::{
    LegacyCorrespondenceError, LegacyCorrespondenceRequest, legacy_correspondence_request,
};
#[cfg(feature = "legacy-compat")]
pub use legacy_graph::{
    LegacyGraphError, LegacyGraphIndex, LegacyGraphObjects, LegacyGraphOperation,
    LegacyGraphRegistry, LegacyGraphRequest, legacy_graph_request,
};
#[cfg(feature = "legacy-compat")]
pub use legacy_pack::{
    ImportedLegacyRelationPack, LegacyPackChange, LegacyPackImportReport, LegacyPackIssue,
    LegacyPackPendingCheck, LegacyPackSourceRecord, LegacyRelationPackError,
    ParsedLegacyRelationPack, import_legacy_relation_pack,
};
#[cfg(feature = "legacy-compat")]
pub use legacy_references::{
    LegacyReferenceError, LegacyReferenceOperation, LegacyReferenceRequest,
    legacy_reference_request,
};
#[cfg(feature = "legacy-compat")]
pub use legacy_registry::{
    LegacyRegistryError, LegacyRegistryOperation, LegacyRegistryRequest, LegacyRegistryState,
    legacy_registry_request,
};
#[cfg(feature = "legacy-compat")]
pub use legacy_reporting::{
    LegacyReportingAction, LegacyReportingError, LegacyReportingRequest, LegacyReportingResponse,
    legacy_reporting_request,
};
#[cfg(feature = "legacy-compat")]
pub use legacy_validation::{
    LegacyValidationIssue, LegacyValidationRegistry, LegacyValidationResult,
    validate_legacy_document, validate_legacy_document_shape,
};
pub use preflight::{check_input_bounds, check_value_bounds};
pub use registry::RelationRegistry;
pub use risk::project_semantics;

#[cfg(feature = "legacy-compat")]
pub use legacy_cli::legacy_cli_request;
