#![forbid(unsafe_code)]

mod admission;
mod constraints;
mod control;
mod derivation;
mod diff;
mod graph;
mod impact;
mod laws;
mod legacy_cli;
mod legacy_composition;
mod legacy_constraints;
mod legacy_correspondence;
mod legacy_evaluation;
pub use legacy_evaluation::legacy_evaluation_request;
mod legacy_graph;
mod legacy_pack;
pub use legacy_pack::LegacyPortableSchema;
mod legacy_references;
mod legacy_registry;
mod legacy_reporting;
mod legacy_semantic;
mod legacy_validation;
mod legacy_viability;
pub use legacy_viability::legacy_viability_request;
mod legacy_workspace;
pub use legacy_workspace::{
    LegacyWorkspaceError, LegacyWorkspaceRequest, legacy_workspace_request,
};
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
pub use impact::{ImpactReport, ImpactStep, ImpactVisit, impact};
pub use legacy_composition::{
    LegacyCompositionError, LegacyCompositionRequest, compose_legacy_documents,
};
pub use legacy_correspondence::{
    LegacyCorrespondenceError, LegacyCorrespondenceRequest, legacy_correspondence_request,
};
pub use legacy_graph::{
    LegacyGraphError, LegacyGraphIndex, LegacyGraphObjects, LegacyGraphOperation,
    LegacyGraphRegistry, LegacyGraphRequest, legacy_graph_request,
};
pub use legacy_pack::{
    ImportedLegacyRelationPack, LegacyPackChange, LegacyPackImportReport, LegacyPackIssue,
    LegacyPackPendingCheck, LegacyPackSourceRecord, LegacyRelationPackError,
    ParsedLegacyRelationPack, import_legacy_relation_pack,
};
pub use legacy_references::{
    LegacyReferenceError, LegacyReferenceOperation, LegacyReferenceRequest,
    legacy_reference_request,
};
pub use legacy_registry::{
    LegacyRegistryError, LegacyRegistryOperation, LegacyRegistryRequest, LegacyRegistryState,
    legacy_registry_request,
};
pub use legacy_reporting::{
    LegacyReportingAction, LegacyReportingError, LegacyReportingRequest, LegacyReportingResponse,
    legacy_reporting_request,
};
pub use legacy_validation::{
    LegacyValidationIssue, LegacyValidationRegistry, LegacyValidationResult,
    validate_legacy_document, validate_legacy_document_shape,
};
pub use preflight::{check_input_bounds, check_value_bounds};
pub use registry::RelationRegistry;
pub use risk::project_semantics;

pub use legacy_cli::legacy_cli_request;
