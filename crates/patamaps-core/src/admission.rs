use crate::graph::{
    AuthorityResolution, CheckError, CheckedGraph, Issue, Severity, finish, identifier,
};
use patamaps_contracts::*;
use serde::Serialize;
use serde_json::Value;
use std::collections::{BTreeSet, HashMap, HashSet};
use time::{OffsetDateTime, format_description::well_known::Rfc3339};

pub(crate) fn timestamp(value: &str) -> Result<OffsetDateTime, time::error::Parse> {
    OffsetDateTime::parse(value, &Rfc3339)
}

#[derive(Debug, Clone)]
pub struct EvaluationOptions {
    pub context: JsonObject,
    pub evaluated_at: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InactiveMapping {
    pub id: String,
    pub reason: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GenerationRecord {
    pub schema_version: ProtocolVersion,
    pub document_type: &'static str,
    pub profile: &'static str,
    pub id: String,
    pub digest: String,
    pub evaluated_at: String,
    pub graph: GraphBinding,
    pub policy: GraphBinding,
    pub packs: Vec<PackReference>,
    pub context: JsonObject,
    pub active_mappings: Vec<String>,
    pub inactive_mappings: Vec<InactiveMapping>,
    pub evidence: Vec<String>,
    pub waivers_applied: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub semantics: Option<SemanticGeneration>,
}

/// This type borrows the immutable graph and policy that established admission.
/// Serialized records are evidence; the only constructor is `admit`.
///
/// ```compile_fail
/// use patamaps_core::AdmittedGeneration;
/// let forged: AdmittedGeneration = serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug)]
pub struct AdmittedGeneration<'a> {
    graph: &'a CheckedGraph,
    policy: &'a PolicyDocument,
    record: GenerationRecord,
    active: HashSet<String>,
    issues: Vec<Issue>,
}

impl<'a> AdmittedGeneration<'a> {
    pub fn graph(&self) -> &'a CheckedGraph {
        self.graph
    }
    pub fn policy(&self) -> &'a PolicyDocument {
        self.policy
    }
    pub fn record(&self) -> &GenerationRecord {
        &self.record
    }
    pub fn active(&self, id: &str) -> bool {
        self.active.contains(id)
    }
    pub fn issues(&self) -> &[Issue] {
        &self.issues
    }
}

fn primitive(value: &Value) -> bool {
    !value.is_array() && !value.is_object()
}

pub(crate) fn context_valid(context: &JsonObject) -> bool {
    context.iter().all(|(k, v)| {
        !k.is_empty() && (primitive(v) || v.as_array().is_some_and(|a| a.iter().all(primitive)))
    })
}

fn equivalent(a: &Value, b: &Value) -> bool {
    if a.is_number() && b.is_number() {
        a.as_f64() == b.as_f64()
    } else {
        a == b
    }
}

pub(crate) fn expr_valid(expr: &ContextExpression, depth: usize) -> bool {
    if depth > MAX_JSON_DEPTH {
        return false;
    }
    match expr {
        ContextExpression::All { all } => {
            !all.is_empty() && all.iter().all(|e| expr_valid(e, depth + 1))
        }
        ContextExpression::Any { any } => {
            !any.is_empty() && any.iter().all(|e| expr_valid(e, depth + 1))
        }
        ContextExpression::Not { not } => expr_valid(not, depth + 1),
        ContextExpression::Comparison { key, value, .. } => !key.is_empty() && primitive(value),
        ContextExpression::Membership { key, values, .. } => {
            !key.is_empty()
                && !values.is_empty()
                && values.iter().all(primitive)
                && values
                    .iter()
                    .collect::<Vec<_>>()
                    .iter()
                    .enumerate()
                    .all(|(i, v)| !values[..i].iter().any(|p| equivalent(p, v)))
        }
        ContextExpression::Exists { key, .. } => !key.is_empty(),
    }
}

pub(crate) fn required<'a>(expr: &'a ContextExpression, keys: &mut BTreeSet<&'a str>) {
    visit_required(expr, &mut |key| {
        keys.insert(key);
    });
}

pub(crate) fn visit_required<'a>(expr: &'a ContextExpression, visit: &mut impl FnMut(&'a str)) {
    match expr {
        ContextExpression::All { all } => all.iter().for_each(|e| visit_required(e, visit)),
        ContextExpression::Any { any } => any.iter().for_each(|e| visit_required(e, visit)),
        ContextExpression::Not { not } => visit_required(not, visit),
        ContextExpression::Comparison { key, .. } | ContextExpression::Membership { key, .. } => {
            visit(key);
        }
        ContextExpression::Exists { .. } => {}
    }
}

pub(crate) fn matches_context(expr: &ContextExpression, context: &JsonObject) -> bool {
    matches_context_with(expr, context, &equivalent)
}

pub(crate) fn matches_context_with(
    expr: &ContextExpression,
    context: &JsonObject,
    equal: &impl Fn(&Value, &Value) -> bool,
) -> bool {
    match expr {
        ContextExpression::All { all } => {
            all.iter().all(|e| matches_context_with(e, context, equal))
        }
        ContextExpression::Any { any } => {
            any.iter().any(|e| matches_context_with(e, context, equal))
        }
        ContextExpression::Not { not } => !matches_context_with(not, context, equal),
        ContextExpression::Exists { key, value, .. } => {
            context.contains_key(key) == value.unwrap_or(true)
        }
        ContextExpression::Comparison {
            key,
            operator,
            value,
        } => context.get(key).is_some_and(|a| {
            a.as_array().map_or_else(
                || equal(a, value),
                |values| values.iter().any(|v| equal(v, value)),
            ) == (*operator == ComparisonOperator::Equals)
        }),
        ContextExpression::Membership {
            key,
            operator,
            values,
        } => context.get(key).is_some_and(|a| {
            let found = match a.as_array() {
                Some(a) => a.iter().any(|n| values.iter().any(|v| equal(v, n))),
                None => values.iter().any(|v| equal(v, a)),
            };
            found == (*operator == MembershipOperator::In)
        }),
    }
}

pub(crate) fn selector_matches(
    graph: &CheckedGraph,
    mapping: &Mapping,
    s: &MappingSelector,
) -> bool {
    selector_matches_with(
        s,
        &mapping.id,
        &mapping.relation,
        |v| {
            mapping
                .sources
                .iter()
                .any(|id| graph.entity(id).is_some_and(|e| v.contains(&e.kind)))
        },
        |v| {
            mapping
                .targets
                .iter()
                .any(|id| graph.entity(id).is_some_and(|e| v.contains(&e.kind)))
        },
        |v| v.contains(&mapping.provenance.status),
    )
}

pub(crate) fn selector_matches_with(
    s: &MappingSelector,
    id: &str,
    relation: &str,
    source_kinds: impl FnOnce(&[String]) -> bool,
    target_kinds: impl FnOnce(&[String]) -> bool,
    provenance_statuses: impl FnOnce(&[ProvenanceStatus]) -> bool,
) -> bool {
    s.ids.as_ref().is_none_or(|v| v.iter().any(|v| v == id))
        && s.relations
            .as_ref()
            .is_none_or(|v| v.iter().any(|v| v == relation))
        && s.source_kinds.as_deref().is_none_or(source_kinds)
        && s.target_kinds.as_deref().is_none_or(target_kinds)
        && s.provenance_statuses
            .as_deref()
            .is_none_or(provenance_statuses)
}

fn constraint_issues(
    c: &Constraint,
    graph: &CheckedGraph,
    policy: &PolicyDocument,
    active: &HashSet<String>,
) -> Vec<Issue> {
    let empty = JsonObject::new();
    let params = c.parameters.as_ref().unwrap_or(&empty);
    let allowed: &[&str] = match c.kind.as_str() {
        "core:requires-mapping" | "core:forbids-mapping" | "core:unique-target" => {
            &["relation", "target", "direction"]
        }
        "core:requires-authority" => &["fact"],
        "core:requires-evidence" => &["minimumConfidence", "kinds"],
        _ => {
            return vec![Issue::error(
                "UNKNOWN_CONSTRAINT_KIND",
                "No evaluator is installed for this constraint kind",
                &c.id,
            )];
        }
    };
    if params.keys().any(|k| !allowed.contains(&k.as_str())) {
        return vec![Issue::error(
            "INVALID_CONSTRAINT_PARAMETERS",
            "Constraint has unsupported parameters",
            &c.id,
        )];
    }
    let mut issues = Vec::new();
    if c.kind == "core:requires-authority" {
        let Some(fact) = params
            .get("fact")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
        else {
            return vec![Issue::error(
                "INVALID_CONSTRAINT_PARAMETERS",
                "Authority constraint needs a fact",
                &c.id,
            )];
        };
        for subject in &c.subjects {
            if !matches!(
                graph.resolve_authority(subject, fact),
                AuthorityResolution::Resolved { .. }
            ) {
                issues.push(Issue::error(
                    "REQUIRED_AUTHORITY_UNRESOLVED",
                    format!("No resolved authority for {fact}"),
                    subject,
                ));
            }
        }
        return issues;
    }
    if c.kind == "core:requires-evidence" {
        let minimum = params
            .get("minimumConfidence")
            .map_or(Some(0.0), Value::as_f64);
        let kinds = params.get("kinds").map(Value::as_array);
        if minimum.is_none_or(|m| !(0.0..=1.0).contains(&m))
            || kinds.is_some_and(|v| {
                v.is_none_or(|a| {
                    a.is_empty() || a.iter().any(|s| s.as_str().is_none_or(str::is_empty))
                })
            })
        {
            return vec![Issue::error(
                "INVALID_CONSTRAINT_PARAMETERS",
                "Invalid evidence confidence/kind requirement",
                &c.id,
            )];
        }
        for subject in &c.subjects {
            if graph.mapping(subject).is_some() && !active.contains(subject) {
                continue;
            }
            let support = policy.evidence.iter().any(|e| {
                e.result == EvidenceResult::Supports
                    && e.subjects.contains(subject)
                    && e.confidence.unwrap_or(0.0) >= minimum.unwrap_or(0.0)
                    && kinds
                        .flatten()
                        .is_none_or(|ks| ks.iter().any(|k| k.as_str() == Some(&e.kind)))
            });
            if !support {
                issues.push(Issue::error(
                    "REQUIRED_EVIDENCE_MISSING",
                    format!("No support meeting {}", c.id),
                    subject,
                ));
            }
        }
        return issues;
    }
    for key in ["relation", "target", "direction"] {
        if params
            .get(key)
            .is_some_and(|v| v.as_str().is_none_or(str::is_empty))
        {
            return vec![Issue::error(
                "INVALID_CONSTRAINT_PARAMETERS",
                "Mapping constraint parameters must be nonempty strings",
                &c.id,
            )];
        }
    }
    let direction = params
        .get("direction")
        .and_then(Value::as_str)
        .unwrap_or("source");
    if !["source", "target", "either"].contains(&direction) {
        return vec![Issue::error(
            "INVALID_CONSTRAINT_PARAMETERS",
            "Invalid mapping constraint direction",
            &c.id,
        )];
    }
    let relation = params.get("relation").and_then(Value::as_str);
    let target = params.get("target").and_then(Value::as_str);
    if relation.is_some_and(|r| graph.relation(r).is_none())
        || target.is_some_and(|t| !identifier(t))
    {
        return vec![Issue::error(
            "INVALID_CONSTRAINT_PARAMETERS",
            "Unknown relation or invalid target identity",
            &c.id,
        )];
    }
    for subject in &c.subjects {
        let found: Vec<_> = graph
            .incident(subject)
            .filter(|m| {
                active.contains(&m.id)
                    && relation.is_none_or(|r| r == m.relation)
                    && target.is_none_or(|t| m.targets.iter().any(|id| id == t))
                    && match direction {
                        "target" => m.targets.contains(subject),
                        "source" => m.sources.contains(subject),
                        _ => true,
                    }
            })
            .collect();
        match c.kind.as_str() {
            "core:requires-mapping" if found.is_empty() => issues.push(Issue::error(
                "REQUIRED_MAPPING_MISSING",
                format!("No active mapping meeting {}", c.id),
                subject,
            )),
            "core:forbids-mapping" if !found.is_empty() => issues.push(Issue::error(
                "FORBIDDEN_MAPPING_ACTIVE",
                format!("Forbidden mapping under {}", c.id),
                subject,
            )),
            "core:unique-target" => {
                let targets: BTreeSet<_> = found
                    .iter()
                    .flat_map(|m| {
                        if direction == "target"
                            || (direction == "either" && !m.sources.contains(subject))
                        {
                            &m.sources
                        } else {
                            &m.targets
                        }
                    })
                    .collect();
                if targets.len() > 1 {
                    issues.push(Issue::error(
                        "NON_UNIQUE_MAPPING_TARGET",
                        format!("Multiple targets under {}", c.id),
                        subject,
                    ));
                }
            }
            _ => {}
        }
    }
    issues
}

pub fn admit<'a>(
    graph: &'a CheckedGraph,
    policy: &'a PolicyDocument,
    options: EvaluationOptions,
) -> Result<AdmittedGeneration<'a>, CheckError> {
    admit_internal(graph, policy, options, None)
}
pub fn admit_controlled<'a>(
    graph: &'a CheckedGraph,
    policy: &'a PolicyDocument,
    options: EvaluationOptions,
    control: &crate::WorkControl,
) -> Result<AdmittedGeneration<'a>, CheckError> {
    admit_internal(graph, policy, options, Some(control))
}
fn admit_internal<'a>(
    graph: &'a CheckedGraph,
    policy: &'a PolicyDocument,
    options: EvaluationOptions,
    control: Option<&crate::WorkControl>,
) -> Result<AdmittedGeneration<'a>, CheckError> {
    crate::control::poll(control)?;
    crate::graph::object_bounds(
        policy
            .metadata
            .iter()
            .map(|v| (v, 2))
            .chain(
                policy
                    .evidence
                    .iter()
                    .filter_map(|e| e.attributes.as_ref())
                    .map(|v| (v, 4)),
            )
            .chain(
                policy
                    .constraints
                    .iter()
                    .filter_map(|c| c.parameters.as_ref())
                    .map(|v| (v, 4)),
            ),
        &policy.id,
        "POLICY_RESOURCE_LIMIT",
    )?;
    let mut issues = graph.issues().to_vec();
    let doc = graph.document();
    let evaluated = timestamp(&options.evaluated_at);
    if evaluated.is_err() {
        issues.push(Issue::error(
            "INVALID_EVALUATION_TIME",
            "An explicit valid RFC3339 timestamp is required",
            &policy.id,
        ));
    }
    if !context_valid(&options.context) {
        issues.push(Issue::error(
            "INVALID_CONTEXT",
            "Context values must be primitives or primitive arrays",
            &policy.id,
        ));
    }
    if !identifier(&policy.id) {
        issues.push(Issue::error(
            "INVALID_POLICY_ID",
            "Invalid policy identity",
            &policy.id,
        ));
    }
    if graph.packs().iter().any(|p| p.laws.is_some()) && policy.semantics.is_none() {
        issues.push(Issue::error(
            "EXECUTABLE_POLICY_REQUIRED",
            "Executable packs require an explicit semantic policy",
            &policy.id,
        ));
    }
    if policy.graph.id != doc.id {
        issues.push(Issue::error(
            "GRAPH_BINDING_MISMATCH",
            "Policy names a different graph",
            &policy.id,
        ));
    }
    if policy.graph.revision.is_none() && policy.graph.digest.is_none() {
        issues.push(Issue::error(
            "INVALID_GRAPH_BINDING",
            "Policy must bind an exact graph revision or digest",
            &policy.id,
        ));
    }
    if policy
        .graph
        .revision
        .as_ref()
        .is_some_and(|r| doc.revision.as_ref() != Some(r))
    {
        issues.push(Issue::error(
            "GRAPH_REVISION_MISMATCH",
            "Policy revision is stale",
            &policy.id,
        ));
    }
    if policy
        .graph
        .digest
        .as_ref()
        .is_some_and(|d| d != graph.digest())
    {
        issues.push(Issue::error(
            "GRAPH_DIGEST_MISMATCH",
            "Policy graph digest is stale",
            &policy.id,
        ));
    }
    if policy.mappings.len() > 100_000
        || policy.constraints.len() > 10_000
        || policy.evidence.len() > 100_000
        || policy.waivers.as_ref().is_some_and(|v| v.len() > 1_000)
    {
        return Err(CheckError(vec![Issue::error(
            "POLICY_RESOURCE_LIMIT",
            "Policy exceeds the draft profile limits",
            &policy.id,
        )]));
    }
    let mut declarations: HashMap<&str, Vec<&Declaration>> = HashMap::new();
    let mut direct = HashMap::<&str, Vec<&Declaration>>::new();
    let mut selectors = Vec::new();
    for d in &policy.mappings {
        crate::control::poll(control)?;
        if let Some(a) = &d.applicability {
            if a.when.is_none() && a.unless.is_none() {
                issues.push(Issue::error(
                    "INVALID_APPLICABILITY",
                    "Applicability needs when or unless",
                    &policy.id,
                ));
            }
            if [&a.when, &a.unless]
                .into_iter()
                .flatten()
                .any(|e| !expr_valid(e, 0))
            {
                issues.push(Issue::error(
                    "INVALID_CONTEXT_EXPRESSION",
                    "Context expression is invalid or too deeply nested",
                    &policy.id,
                ));
            }
        }
        match (&d.mapping, &d.select) {
            (Some(id), None) => {
                if graph.mapping(id).is_none() {
                    issues.push(Issue::error(
                        "UNKNOWN_MAPPING_DECLARATION",
                        "Declared mapping does not exist",
                        id,
                    ));
                }
                direct.entry(id).or_default().push(d);
            }
            (None, Some(s)) => {
                if s.ids.is_none()
                    && s.relations.is_none()
                    && s.source_kinds.is_none()
                    && s.target_kinds.is_none()
                    && s.provenance_statuses.is_none()
                {
                    issues.push(Issue::error(
                        "INVALID_MAPPING_SELECTOR",
                        "An empty selector is not a wildcard",
                        &policy.id,
                    ));
                }
                if [&s.ids, &s.relations, &s.source_kinds, &s.target_kinds]
                    .into_iter()
                    .flatten()
                    .any(|v| {
                        v.is_empty()
                            || v.iter().any(String::is_empty)
                            || v.iter().collect::<HashSet<_>>().len() != v.len()
                    })
                    || s.provenance_statuses.as_ref().is_some_and(|v| {
                        v.is_empty() || v.iter().enumerate().any(|(i, s)| v[..i].contains(s))
                    })
                {
                    issues.push(Issue::error(
                        "INVALID_MAPPING_SELECTOR",
                        "Present selector lists must be nonempty",
                        &policy.id,
                    ));
                }
                for id in s.ids.iter().flatten() {
                    if graph.mapping(id).is_none() {
                        issues.push(Issue::error(
                            "UNKNOWN_MAPPING_SELECTOR_ID",
                            "Selected mapping does not exist",
                            id,
                        ));
                    }
                }
                selectors.push((d, s, 0usize));
            }
            _ => issues.push(Issue::error(
                "INVALID_MAPPING_DECLARATION",
                "Exactly one mapping or selector is required",
                &policy.id,
            )),
        }
    }
    // Invalid declarations cannot participate in selection as wildcard matches.
    finish(issues.clone())?;
    let proof_result = policy
        .semantics
        .as_ref()
        .map(|s| {
            crate::check_derivations_with_inputs(
                graph,
                &s.derivations,
                &options.context,
                s.derivation_limits,
                crate::UncertaintyInputs {
                    assessments: &s.assessments,
                    evidence: &policy.evidence,
                },
            )
        })
        .transpose();
    let checked_derivations = match proof_result {
        Ok(v) => v,
        Err(e) => {
            issues.extend(e.issues);
            None
        }
    };
    let uncertainty_result = policy
        .semantics
        .as_ref()
        .map(|s| {
            crate::uncertainty::CheckedUncertainty::new(
                graph,
                &s.assessments,
                &policy.evidence,
                &s.derivations,
                None,
            )
        })
        .transpose();
    let mut uncertainty_inputs = match uncertainty_result {
        Ok(v) => v,
        Err(e) => {
            issues.extend(e.0);
            None
        }
    };
    let handled_evidence = uncertainty_inputs
        .as_ref()
        .map(|u| u.handled_evidence())
        .unwrap_or_default();
    let uncertainty = uncertainty_inputs
        .as_mut()
        .zip(checked_derivations.as_ref())
        .map(|(u, c)| u.graph_summaries(graph, c.records()))
        .transpose()?
        .unwrap_or_default();
    // Bound selector expansion before evaluating; refusal is a declared limit.
    if selectors.len().saturating_mul(doc.mappings.len()) > 2_000_000 {
        return Err(CheckError(vec![Issue::error(
            "SELECTOR_WORK_LIMIT",
            "Selector expansion exceeds two million comparisons",
            &policy.id,
        )]));
    }
    let mut active = HashSet::new();
    let mut inactive = Vec::new();
    for m in &doc.mappings {
        crate::control::poll(control)?;
        let mut matched = direct.get(m.id.as_str()).cloned().unwrap_or_default();
        for (d, s, count) in &mut selectors {
            crate::control::poll(control)?;
            if selector_matches(graph, m, s) {
                matched.push(d);
                *count += 1;
            }
        }
        if matched.len() != 1 {
            issues.push(Issue::error(
                if matched.is_empty() {
                    "MAPPING_POLICY_MISSING"
                } else {
                    "DUPLICATE_MAPPING_POLICY"
                },
                "Every mapping needs exactly one declaration",
                &m.id,
            ));
            declarations.insert(&m.id, matched);
            continue;
        }
        let d = matched[0];
        if graph
            .relation(&m.relation)
            .is_some_and(|r| r.impact_direction.is_none())
        {
            issues.push(Issue::error(
                "UNDECLARED_IMPACT_DIRECTION",
                "Relation requires an explicit impact direction",
                &m.id,
            ));
        }
        if m.lossiness == Lossiness::Unknown {
            issues.push(Issue::error(
                "UNDECLARED_LOSSINESS",
                "Admitted mappings need declared lossiness",
                &m.id,
            ));
        }
        if m.attributes
            .as_ref()
            .is_some_and(|a| a.contains_key("metamap:derivation"))
            && policy.semantics.is_none()
        {
            issues.push(Issue::error(
                "EXECUTABLE_POLICY_REQUIRED",
                "Proof references require an explicit semantic policy with checked derivations",
                &m.id,
            ));
        }
        if d.determinism == Determinism::Deterministic
            && m.transform
                .as_ref()
                .is_some_and(|t| t.deterministic != Some(true))
        {
            issues.push(Issue::error(
                "UNVERIFIED_DETERMINISM",
                "Transform does not declare deterministic behavior",
                &m.id,
            ));
        }
        if d.reversibility == Reversibility::Reversible {
            if m.lossiness != Lossiness::Lossless {
                issues.push(Issue::error(
                    "REVERSIBLE_MAPPING_IS_LOSSY",
                    "A reversible mapping must be lossless",
                    &m.id,
                ));
            }
            if m.transform
                .as_ref()
                .is_some_and(|t| t.reversible != Some(true))
            {
                issues.push(Issue::error(
                    "UNVERIFIED_REVERSIBILITY",
                    "Transform does not declare reversible behavior",
                    &m.id,
                ));
            }
        }
        let mut reason = None;
        if let Some(a) = &d.applicability {
            if a.when.is_none() && a.unless.is_none() {
                issues.push(Issue::error(
                    "INVALID_APPLICABILITY",
                    "Applicability must declare when or unless",
                    &m.id,
                ));
            }
            for e in [&a.when, &a.unless].into_iter().flatten() {
                if !expr_valid(e, 0) {
                    issues.push(Issue::error(
                        "INVALID_CONTEXT_EXPRESSION",
                        "Context expressions need primitive values and nonempty keys",
                        &m.id,
                    ));
                }
                let mut keys = BTreeSet::new();
                required(e, &mut keys);
                for key in keys {
                    if !options.context.contains_key(key) {
                        issues.push(Issue::error(
                            "CONTEXT_KEY_MISSING",
                            format!("Required context key {key} is absent"),
                            &m.id,
                        ));
                    }
                }
            }
            if a.when
                .as_ref()
                .is_some_and(|e| !matches_context(e, &options.context))
            {
                reason = Some("when-not-satisfied");
            } else if a
                .unless
                .as_ref()
                .is_some_and(|e| matches_context(e, &options.context))
            {
                reason = Some("inhibited");
            }
        }
        if let Some(reason) = reason {
            inactive.push(InactiveMapping {
                id: m.id.clone(),
                reason: reason.into(),
            });
        } else {
            active.insert(m.id.clone());
        }
        declarations.insert(&m.id, matched);
    }
    for (_, _, count) in &selectors {
        if *count == 0 {
            issues.push(Issue::error(
                "EMPTY_MAPPING_SELECTOR",
                "Selector matches no graph mappings",
                &policy.id,
            ));
        }
    }
    let mut record_ids = HashSet::new();
    for (id, subjects) in policy
        .constraints
        .iter()
        .map(|c| (&c.id, &c.subjects))
        .chain(policy.evidence.iter().map(|e| (&e.id, &e.subjects)))
    {
        if !identifier(id)
            || !record_ids.insert(id)
            || subjects.is_empty()
            || subjects.iter().collect::<HashSet<_>>().len() != subjects.len()
        {
            issues.push(Issue::error(
                "INVALID_POLICY_RECORD",
                "Policy records need unique identities and nonempty unique subjects",
                id,
            ));
        }
        for s in subjects {
            if !graph.known(s) {
                issues.push(Issue::error(
                    "UNKNOWN_POLICY_SUBJECT",
                    format!("Unknown subject {s}"),
                    id,
                ));
            }
        }
    }
    for e in &policy.evidence {
        crate::control::poll(control)?;
        if e.kind.is_empty()
            || e.producer.is_empty()
            || e.observed_at
                .as_ref()
                .is_some_and(|s| timestamp(s).is_err())
            || e.confidence
                .is_some_and(|c| !c.is_finite() || !(0.0..=1.0).contains(&c))
        {
            issues.push(Issue::error(
                "INVALID_EVIDENCE",
                "Invalid evidence metadata",
                &e.id,
            ));
        }
        if e.result == EvidenceResult::Contradicts && !handled_evidence.contains(&e.id) {
            for subject in &e.subjects {
                if graph.mapping(subject).is_none() || active.contains(subject) {
                    issues.push(Issue::error(
                        "CONTRADICTING_EVIDENCE",
                        format!("{} contradicts an active subject", e.id),
                        subject,
                    ));
                }
            }
        }
    }
    let mut topology_work = crate::topology::Work::new(control);
    for c in &policy.constraints {
        crate::control::poll(control)?;
        if crate::topology::supported(&c.kind) {
            issues.extend(crate::topology::evaluate(
                c,
                graph,
                &active,
                &mut topology_work,
            )?);
        } else {
            issues.extend(constraint_issues(c, graph, policy, &active));
        }
    }
    // Ordinary waivers cannot mask structural, protocol, or authentication errors.
    const WAIVABLE: &[&str] = &[
        "REQUIRED_EVIDENCE_MISSING",
        "CONTRADICTING_EVIDENCE",
        "REQUIRED_MAPPING_MISSING",
        "FORBIDDEN_MAPPING_ACTIVE",
        "NON_UNIQUE_MAPPING_TARGET",
        "REQUIRED_AUTHORITY_UNRESOLVED",
    ];
    let mut waiver_ids = HashSet::new();
    let mut applied = BTreeSet::new();
    for w in policy.waivers.iter().flatten() {
        crate::control::poll(control)?;
        if !identifier(&w.id)
            || !waiver_ids.insert(&w.id)
            || w.codes.is_empty()
            || w.subjects.is_empty()
            || w.subjects.iter().collect::<HashSet<_>>().len() != w.subjects.len()
            || w.codes.iter().collect::<HashSet<_>>().len() != w.codes.len()
            || w.reason.is_empty()
            || w.asserted_by.is_empty()
            || w.codes.iter().any(|c| !WAIVABLE.contains(&c.as_str()))
            || w.subjects
                .iter()
                .any(|s| !graph.known(s) && !record_ids.contains(s))
        {
            issues.push(Issue::error(
                "INVALID_WAIVER",
                "Waiver has invalid or protected scope",
                &w.id,
            ));
            continue;
        }
        let expires = timestamp(&w.expires_at);
        if expires.is_err()
            || evaluated
                .as_ref()
                .is_ok_and(|now| expires.as_ref().is_ok_and(|e| e <= now))
        {
            issues.push(Issue::error(
                "EXPIRED_WAIVER",
                "Waiver is expired or has invalid expiry",
                &w.id,
            ));
            continue;
        }
        for issue in &mut issues {
            if issue.severity == Severity::Error
                && w.codes.contains(&issue.code)
                && issue
                    .subject_id
                    .as_ref()
                    .is_some_and(|s| w.subjects.contains(s))
            {
                issue.severity = Severity::Warning;
                issue.waived_by = Some(w.id.clone());
                applied.insert(w.id.clone());
            }
        }
    }
    // Inference findings are added after ordinary waivers: no waiver can erase
    // an inactive premise, strengthen its declaration or suppress disjointness.
    if let Some(checked) = &checked_derivations {
        for proof in checked.records() {
            if active.contains(&proof.result.id) {
                let result = declarations
                    .get(proof.result.id.as_str())
                    .and_then(|v| v.first())
                    .copied();
                for premise in &proof.premises {
                    if !active.contains(&premise.mapping) {
                        issues.push(Issue::error(
                            "INACTIVE_DERIVATION_PREMISE",
                            "Active inference requires active premises",
                            &proof.result.id,
                        ));
                    }
                    if let (Some(source), Some(result)) = (
                        declarations
                            .get(premise.mapping.as_str())
                            .and_then(|v| v.first())
                            .copied(),
                        result,
                    ) {
                        if source.coverage == Coverage::Partial
                            && result.coverage == Coverage::Total
                            || source.determinism == Determinism::Nondeterministic
                                && result.determinism == Determinism::Deterministic
                            || source.reversibility == Reversibility::Irreversible
                                && result.reversibility == Reversibility::Reversible
                        {
                            issues.push(Issue::error(
                                "DERIVATION_SEMANTICS_STRENGTHENED",
                                "Derived declaration cannot erase premise limitations",
                                &proof.result.id,
                            ));
                        }
                        if graph
                            .law(&proof.rule.id)
                            .is_some_and(|(_, law)| law.operation == LawOperation::Reverse)
                            && source.reversibility != Reversibility::Reversible
                        {
                            issues.push(Issue::error(
                                "IRREVERSIBLE_DERIVATION_PREMISE",
                                "Reverse law requires a reversible declared premise",
                                &proof.result.id,
                            ));
                        }
                    }
                }
            }
        }
    }
    issues.extend(crate::derivation::disjointness_issues(graph, &active));
    if let Some(s) = &policy.semantics {
        let mut identities = HashSet::new();
        for id in std::iter::once(&policy.id)
            .chain(policy.constraints.iter().map(|r| &r.id))
            .chain(policy.evidence.iter().map(|r| &r.id))
            .chain(policy.waivers.iter().flatten().map(|r| &r.id))
            .chain(s.derivations.iter().map(|r| &r.id))
            .chain(s.assessments.iter().map(|r| &r.id))
            .chain(s.uncertainty_requirements.iter().map(|r| &r.id))
            .chain(s.risk_budgets.iter().map(|r| &r.id))
        {
            if !identities.insert(id) {
                issues.push(Issue::error(
                    "DUPLICATE_SEMANTIC_POLICY_ID",
                    "Semantic policy records must have unique identities",
                    id,
                ));
            }
        }
        issues.extend(crate::risk::budget_issues(graph, &s.risk_budgets));
        if let Some(u) = uncertainty_inputs
            .as_ref()
            .filter(|_| checked_derivations.is_some())
        {
            issues.extend(crate::uncertainty::requirement_issues(
                graph,
                &active,
                &uncertainty,
                &s.uncertainty_requirements,
                u,
            ));
        }
    }
    let issues = finish(issues)?;
    parse_value(&canonical_bytes(policy)?)?;
    let packs: Vec<_> = graph
        .packs()
        .iter()
        .map(|p| {
            Ok(PackReference {
                id: p.id.clone(),
                version: p.version.clone(),
                uri: None,
                digest: Some(canonical_digest(p)?),
            })
        })
        .collect::<Result<_, ContractError>>()?;
    let mut active_mappings: Vec<_> = active.iter().cloned().collect();
    active_mappings.sort();
    inactive.sort_by(|a, b| a.id.cmp(&b.id));
    let mut record = GenerationRecord {
        schema_version: ProtocolVersion::Draft1,
        document_type: "generation",
        profile: evaluation_profile(graph.packs(), policy),
        id: String::new(),
        digest: String::new(),
        evaluated_at: options.evaluated_at,
        graph: GraphBinding {
            id: doc.id.clone(),
            revision: doc.revision.clone(),
            digest: Some(graph.digest().into()),
        },
        policy: GraphBinding {
            id: policy.id.clone(),
            revision: None,
            digest: Some(canonical_digest(policy)?),
        },
        packs,
        context: parse(&canonical_bytes(&options.context)?)?,
        active_mappings,
        inactive_mappings: inactive,
        evidence: policy
            .evidence
            .iter()
            .filter(|e| {
                e.result == EvidenceResult::Supports
                    && e.subjects
                        .iter()
                        .any(|s| graph.mapping(s).is_none() || active.contains(s))
            })
            .map(|e| e.id.clone())
            .collect(),
        waivers_applied: applied.into_iter().collect(),
        semantics: checked_derivations
            .as_ref()
            .zip(policy.semantics.as_ref())
            .map(|(checked, s)| {
                let by_result: HashMap<_, _> = checked
                    .records()
                    .iter()
                    .map(|p| (p.result.id.as_str(), p))
                    .collect();
                let mut dependencies: Vec<_> = doc
                    .mappings
                    .iter()
                    .filter(|m| active.contains(&m.id))
                    .map(|m| {
                        let proof = by_result.get(m.id.as_str());
                        MappingDependency {
                            mapping: m.id.clone(),
                            premises: proof
                                .map(|p| {
                                    p.premises
                                        .iter()
                                        .map(|p| p.mapping.clone())
                                        .collect::<BTreeSet<_>>()
                                        .into_iter()
                                        .collect()
                                })
                                .unwrap_or_default(),
                            derivation: proof.map(|p| ContentBinding {
                                id: p.id.clone(),
                                digest: p.digest.clone(),
                            }),
                        }
                    })
                    .collect();
                dependencies.sort_by(|a, b| a.mapping.cmp(&b.mapping));
                SemanticGeneration {
                    interpretation: Interpretation::DeclaredLawApplication,
                    derivations: checked.records().to_vec(),
                    derivation_limits: s.derivation_limits,
                    dependencies,
                    uncertainty: uncertainty.clone(),
                    risk_evaluation: if s.risk_budgets.is_empty() {
                        "not-evaluated"
                    } else {
                        "available-for-projection"
                    },
                }
            }),
    };
    record.packs.sort_by(|a, b| a.id.cmp(&b.id));
    record.evidence.sort();
    let mut content = serde_json::to_value(&record).map_err(ContractError::from)?;
    let obj = content
        .as_object_mut()
        .expect("generation serializes to an object");
    obj.remove("id");
    obj.remove("digest");
    record.digest = canonical_digest(&content)?;
    record.id = format!("urn:patamaps:generation:{}", &record.digest[7..]);
    parse_value(&canonical_bytes(&record)?)?;
    Ok(AdmittedGeneration {
        graph,
        policy,
        record,
        active,
        issues,
    })
}
