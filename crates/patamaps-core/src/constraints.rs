use crate::{CheckError, CheckedGraph, EvaluationOptions, Issue, WorkControl};
use patamaps_contracts::{Constraint, ContentBinding, Evidence, JsonObject, PolicyDocument};
use serde::Serialize;
use std::{collections::BTreeMap, collections::HashSet, panic::AssertUnwindSafe};

const MAX_EVALUATORS: usize = 128;
const MAX_FINDINGS: usize = 128;

pub(crate) fn builtin(kind: &str) -> bool {
    matches!(
        kind,
        "core:requires-mapping"
            | "core:forbids-mapping"
            | "core:unique-target"
            | "core:requires-authority"
            | "core:requires-evidence"
    ) || crate::topology::supported(kind)
}

/// Attribution supplied by the host, bound into the generation's address.
/// The host is responsible for associating these bytes with the evaluator code.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConstraintEvaluatorBinding {
    pub kind: String,
    pub evaluator: ContentBinding,
}

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum ConstraintRegistryError {
    #[error("constraint kind must be a valid identifier")]
    InvalidKind,
    #[error("built-in constraint evaluators cannot be replaced")]
    BuiltinKind,
    #[error("constraint evaluator kind is already registered")]
    DuplicateKind,
    #[error("evaluator needs a valid identity and canonical SHA-256 digest")]
    InvalidBinding,
    #[error("custom constraint registry exceeds its evaluator limit")]
    ResourceLimit,
}

/// Borrowed immutable admission inputs. No checked-state constructor or writer
/// is exposed to an evaluator.
pub struct ConstraintEvaluationContext<'a> {
    pub(crate) graph: &'a CheckedGraph,
    pub(crate) policy: &'a PolicyDocument,
    pub(crate) options: &'a EvaluationOptions,
    pub(crate) active: &'a HashSet<String>,
    pub(crate) control: &'a WorkControl,
}

impl ConstraintEvaluationContext<'_> {
    pub fn graph(&self) -> &CheckedGraph {
        self.graph
    }
    pub fn policy(&self) -> &PolicyDocument {
        self.policy
    }
    pub fn context(&self) -> &JsonObject {
        &self.options.context
    }
    pub fn evaluated_at(&self) -> &str {
        &self.options.evaluated_at
    }
    pub fn evidence(&self) -> &[Evidence] {
        &self.policy.evidence
    }
    pub fn active(&self, mapping: &str) -> bool {
        self.active.contains(mapping)
    }
    /// Cooperatively check cancellation, elapsed time and work units.
    pub fn poll(&self) -> Result<(), CheckError> {
        self.control.poll()
    }
}

/// Trusted in-process host code. Poll cooperatively for lengthy work.
/// Findings must use `"<constraint-kind>:<code>"`, known subjects and no waiver.
pub trait ConstraintEvaluator {
    fn evaluate(
        &self,
        constraint: &Constraint,
        context: &ConstraintEvaluationContext<'_>,
    ) -> Result<Vec<Issue>, CheckError>;
}

impl<F> ConstraintEvaluator for F
where
    F: Fn(&Constraint, &ConstraintEvaluationContext<'_>) -> Result<Vec<Issue>, CheckError>,
{
    fn evaluate(
        &self,
        constraint: &Constraint,
        context: &ConstraintEvaluationContext<'_>,
    ) -> Result<Vec<Issue>, CheckError> {
        self(constraint, context)
    }
}

struct Registered<'a> {
    binding: ConstraintEvaluatorBinding,
    evaluator: Box<dyn ConstraintEvaluator + 'a>,
}

/// Explicit native policy extensions. Registration cannot replace built-ins.
/// Executable callbacks are never restored from serialized generation records.
#[derive(Default)]
pub struct ConstraintRegistry<'a> {
    entries: BTreeMap<String, Registered<'a>>,
}

impl std::fmt::Debug for ConstraintRegistry<'_> {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_list()
            .entries(self.entries.values().map(|v| &v.binding))
            .finish()
    }
}

impl<'a> ConstraintRegistry<'a> {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn register(
        &mut self,
        kind: impl Into<String>,
        evaluator: ContentBinding,
        implementation: impl ConstraintEvaluator + 'a,
    ) -> Result<(), ConstraintRegistryError> {
        let kind = kind.into();
        if !crate::valid_identifier(&kind) || kind.len() > 128 {
            return Err(ConstraintRegistryError::InvalidKind);
        }
        if builtin(&kind) {
            return Err(ConstraintRegistryError::BuiltinKind);
        }
        if self.entries.contains_key(&kind) {
            return Err(ConstraintRegistryError::DuplicateKind);
        }
        let valid_digest = evaluator.digest.strip_prefix("sha256:").is_some_and(|s| {
            s.len() == 64
                && s.bytes()
                    .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        });
        if !crate::valid_identifier(&evaluator.id) || evaluator.id.len() > 4096 || !valid_digest {
            return Err(ConstraintRegistryError::InvalidBinding);
        }
        if self.entries.len() >= MAX_EVALUATORS {
            return Err(ConstraintRegistryError::ResourceLimit);
        }
        self.entries.insert(
            kind.clone(),
            Registered {
                binding: ConstraintEvaluatorBinding { kind, evaluator },
                evaluator: Box::new(implementation),
            },
        );
        Ok(())
    }
    pub fn binding(&self, kind: &str) -> Option<&ConstraintEvaluatorBinding> {
        self.entries.get(kind).map(|v| &v.binding)
    }
    pub(crate) fn evaluate(
        &self,
        constraint: &Constraint,
        context: &ConstraintEvaluationContext<'_>,
    ) -> Result<Vec<Issue>, CheckError> {
        let refused = |code, message| CheckError(vec![Issue::error(code, message, &constraint.id)]);
        let registered = self.entries.get(&constraint.kind).ok_or_else(|| {
            refused(
                "UNKNOWN_CONSTRAINT_KIND",
                "No native evaluator is installed for this constraint kind",
            )
        })?;
        context.poll()?;
        let outcome = std::panic::catch_unwind(AssertUnwindSafe(|| {
            registered.evaluator.evaluate(constraint, context)
        }));
        context.poll()?;
        let findings = match outcome {
            Ok(Ok(findings)) => findings,
            Ok(Err(_)) => {
                return Err(refused(
                    "CUSTOM_CONSTRAINT_EVALUATION_FAILED",
                    "Native constraint evaluator returned a failure",
                ));
            }
            Err(_) => {
                return Err(refused(
                    "CUSTOM_CONSTRAINT_EVALUATION_PANICKED",
                    "Native constraint evaluator panicked before admission",
                ));
            }
        };
        if findings.len() > MAX_FINDINGS {
            return Err(refused(
                "CUSTOM_CONSTRAINT_FINDING_LIMIT",
                "Native constraint evaluator exceeded its finding limit",
            ));
        }
        let prefix = format!("{}:", constraint.kind);
        for finding in &findings {
            context.poll()?;
            let valid_code = finding.code.strip_prefix(&prefix).is_some_and(|code| {
                !code.is_empty()
                    && code.len() <= 128
                    && code.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_')
            });
            let valid_subject = finding.subject_id.as_ref().is_some_and(|subject| {
                subject == &constraint.id
                    || context.graph.known(subject)
                    || context.evidence().iter().any(|e| &e.id == subject)
            });
            if !valid_code
                || !valid_subject
                || finding.message.len() > 8192
                || finding.waived_by.is_some()
            {
                return Err(refused(
                    "CUSTOM_CONSTRAINT_INVALID_FINDING",
                    "Custom findings need bounded namespaced codes/text, known origins and no waiver",
                ));
            }
        }
        Ok(findings)
    }
}
