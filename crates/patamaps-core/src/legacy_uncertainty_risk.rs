//! Original recorded uncertainty and consumer accounting. These read-only
//! observations do not manufacture checked proofs or admitted generations.
use crate::legacy_semantic::RESOURCES;
use crate::legacy_viability::{items, project, s, strings};
use crate::legacy_workspace::{error, get, native, obj, scalar};
use crate::{LegacyPortableSchema, LegacyWorkspaceError};
use patamaps_contracts::{LegacyOrderedJson as J, LegacyReadOnlyJson as Data, canonical_digest};
use serde_json::json;
use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

pub(crate) const DIMENSIONS: [&str; 6] = [
    "identity",
    "context",
    "provenance",
    "completeness",
    "causal-relevance",
    "conflicting-authority",
];
fn issue(code: &str, message: &str, subject: Option<&str>) -> J {
    let mut fields = vec![("code", scalar(code)), ("message", scalar(message))];
    if let Some(id) = subject.filter(|id| !id.is_empty()) {
        fields.push(("subjectId", scalar(id)));
    }
    obj(fields)
}
fn risk_issue(code: &str, message: &str, subject: Option<&str>) -> J {
    let mut fields = vec![("code", scalar(code)), ("message", scalar(message))];
    if let Some(id) = subject {
        fields.push(("subjectId", scalar(id)));
    }
    obj(fields)
}
fn input_schema() -> &'static LegacyPortableSchema {
    static SCHEMA: OnceLock<LegacyPortableSchema> = OnceLock::new();
    SCHEMA.get_or_init(|| LegacyPortableSchema::with_resources(r#"{
      "type":"object","additionalProperties":false,"required":["assessments","evidence"],
      "properties":{
        "assessments":{"type":"array","items":{"$ref":"https://raw.githubusercontent.com/roryscot/metamap/main/schemas/metamap-viability-v2.schema.json#/$defs/assessment"}},
        "evidence":{"type":"array","items":{"$ref":"https://raw.githubusercontent.com/roryscot/metamap/v0.2.0/schemas/metamap-viability.schema.json#/$defs/evidence"}}
      }
    }"#, &RESOURCES))
}
pub(crate) fn input_shape(inputs: &J, canonical_error: Option<&str>) -> Vec<J> {
    if let Some(message) = canonical_error {
        return vec![issue("INVALID_UNCERTAINTY_INPUT", message, None)];
    }
    input_schema()
        .legacy_issues(inputs, &HashSet::new())
        .into_iter()
        .map(|finding| {
            obj(vec![
                ("code", scalar("INVALID_UNCERTAINTY_INPUT")),
                ("message", scalar(&finding.message)),
                (
                    "path",
                    scalar(if finding.path.is_empty() {
                        "$"
                    } else {
                        &finding.path
                    }),
                ),
            ])
        })
        .collect()
}
fn revision<'a>(record: &'a J, graph: &'a J) -> Option<&'a J> {
    record
        .get("provenance")
        .and_then(|p| p.get("sourceRevision"))
        .filter(|v| !matches!(v, J::Null))
        .or_else(|| graph.get("revision"))
}
fn display(v: &J) -> String {
    match v {
        J::String(s) => s.clone(),
        J::Null => "null".into(),
        J::Bool(v) => v.to_string(),
        J::Number(v) if v.is_nan() => "NaN".into(),
        J::Number(v) if v.is_infinite() => if v.is_sign_negative() {
            "-Infinity"
        } else {
            "Infinity"
        }
        .into(),
        J::Number(v) => {
            if *v == 0.0 {
                "0".into()
            } else {
                v.to_string()
            }
        }
        J::Array(v) => v.iter().map(display).collect::<Vec<_>>().join(","),
        _ => "[object Object]".into(),
    }
}
pub(crate) fn validate_inputs(
    graph: &J,
    inputs: &J,
    prospective: Option<&str>,
    proof_ids: &[String],
) -> Vec<J> {
    let mut subjects = HashMap::new();
    for field in ["entities", "mappings", "authorities"] {
        let Some(value) = graph.get(field) else {
            return vec![issue(
                "INVALID_UNCERTAINTY_INPUT",
                "Cannot read properties of undefined (reading 'map')",
                None,
            )];
        };
        let Some(records) = value.array() else {
            return vec![issue(
                "INVALID_UNCERTAINTY_INPUT",
                &format!("graph.{field}.map is not a function"),
                None,
            )];
        };
        for record in records {
            subjects.insert(s(record, "id"), revision(record, graph));
        }
    }
    if let Some(id) = prospective.filter(|id| !id.is_empty()) {
        subjects.insert(id, graph.get("revision"));
    }
    let mut identities = subjects.keys().copied().collect::<HashSet<_>>();
    identities.extend(proof_ids.iter().map(String::as_str));
    let mut issues = Vec::new();
    for id in proof_ids {
        if subjects.contains_key(id.as_str()) {
            issues.push(issue(
                "DUPLICATE_DERIVATION_ID",
                "Proof identity must be distinct from graph subject identities",
                Some(id),
            ));
        }
    }
    for record in items(inputs, "assessments")
        .iter()
        .chain(items(inputs, "evidence"))
    {
        let id = s(record, "id");
        if !identities.insert(id) {
            issues.push(issue("DUPLICATE_UNCERTAINTY_ID","Assessment and evidence identities must be unique and distinct from graph/proof identities",Some(id)));
        }
    }
    let evidence = items(inputs, "evidence")
        .iter()
        .map(|e| (s(e, "id"), e))
        .collect::<HashMap<_, _>>();
    for record in items(inputs, "evidence") {
        for subject in strings(record, "subjects") {
            if !subjects.contains_key(subject.as_str()) {
                issues.push(issue(
                    "UNKNOWN_UNCERTAINTY_EVIDENCE_SUBJECT",
                    "Evidence references an unavailable graph subject",
                    Some(s(record, "id")),
                ));
            }
        }
    }
    for assessment in items(inputs, "assessments") {
        let id = s(assessment, "id");
        let subject = s(assessment, "subject");
        if !subjects.contains_key(subject) {
            issues.push(issue(
                "UNKNOWN_ASSESSMENT_SUBJECT",
                "An assessment must name an available graph subject or explicit prospective result",
                Some(id),
            ));
        }
        if let Some(Some(revision)) = subjects.get(subject)
            && revision.string() != Some(s(assessment, "sourceRevision"))
        {
            issues.push(issue(
                "ASSESSMENT_REVISION_MISMATCH",
                &format!(
                    "Assessment revision {} differs from declared subject revision {}",
                    s(assessment, "sourceRevision"),
                    display(revision)
                ),
                Some(id),
            ));
        }
        for reference in strings(assessment, "evidence") {
            let finding = match evidence.get(reference.as_str()) {
                None => Some((
                    "MISSING_UNCERTAINTY_EVIDENCE",
                    "Referenced typed evidence is unavailable",
                )),
                Some(record) if !strings(record, "subjects").iter().any(|s| s == subject) => {
                    Some((
                        "UNCERTAINTY_EVIDENCE_SCOPE_MISMATCH",
                        "Evidence does not cover its assessed subject",
                    ))
                }
                Some(record)
                    if s(record, "kind")
                        != format!("uncertainty:{}", s(assessment, "dimension")) =>
                {
                    Some((
                        "UNCERTAINTY_EVIDENCE_DIMENSION_MISMATCH",
                        "Evidence kind must name its assessed uncertainty dimension",
                    ))
                }
                _ => None,
            };
            if let Some((code, message)) = finding {
                issues.push(issue(code, message, Some(id)));
            }
        }
    }
    issues
}
pub(crate) fn unique(values: impl IntoIterator<Item = String>) -> Vec<String> {
    let mut result = values
        .into_iter()
        .collect::<HashSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();
    result.sort_by_key(|v| Data::string_units(v));
    result
}
pub(crate) fn unknown(dimension: &str) -> J {
    obj(vec![
        ("dimension", scalar(dimension)),
        ("status", scalar("unknown")),
        ("evidence", J::Array(vec![])),
        ("assessments", J::Array(vec![])),
        ("measurementModels", J::Array(vec![])),
        ("sourceRevisions", J::Array(vec![])),
    ])
}
pub(crate) fn combine(dimension: &str, values: &[J]) -> J {
    if values.is_empty() {
        return unknown(dimension);
    }
    let models = unique(values.iter().flat_map(|v| strings(v, "measurementModels")));
    let status = crate::uncertainty::qualitative_meet_status(
        values.iter().any(|v| s(v, "status") == "contradicted"),
        values.iter().any(|v| s(v, "status") == "unknown"),
        models.len(),
        values.iter().all(|v| s(v, "status") == "not-applicable"),
    );
    obj(vec![
        ("dimension", scalar(dimension)),
        ("status", native(status)),
        (
            "evidence",
            native(unique(values.iter().flat_map(|v| strings(v, "evidence")))),
        ),
        (
            "assessments",
            native(unique(
                values.iter().flat_map(|v| strings(v, "assessments")),
            )),
        ),
        ("measurementModels", native(models)),
        (
            "sourceRevisions",
            native(unique(
                values.iter().flat_map(|v| strings(v, "sourceRevisions")),
            )),
        ),
    ])
}
fn assessed(assessment: &J, evidence: &HashMap<&str, &J>) -> Result<J, LegacyWorkspaceError> {
    let mut results = Vec::new();
    for id in strings(assessment, "evidence") {
        let record = evidence.get(id.as_str()).ok_or_else(|| {
            error(
                "TypeError",
                "Cannot read properties of undefined (reading 'result')",
            )
        })?;
        results.push(s(record, "result"));
    }
    let status = if results.contains(&"contradicts") {
        "contradicted"
    } else if s(assessment, "status") == "supported" && results.contains(&"inconclusive") {
        "unknown"
    } else {
        s(assessment, "status")
    };
    Ok(obj(vec![
        ("dimension", scalar(s(assessment, "dimension"))),
        ("status", scalar(status)),
        ("evidence", native(strings(assessment, "evidence"))),
        ("assessments", native(vec![s(assessment, "id")])),
        (
            "measurementModels",
            native(if s(assessment, "measurementModel").is_empty() {
                vec![]
            } else {
                vec![s(assessment, "measurementModel")]
            }),
        ),
        (
            "sourceRevisions",
            native(vec![s(assessment, "sourceRevision")]),
        ),
    ]))
}
pub(crate) fn mapping(
    graph: &J,
    mapping: &J,
    inputs: &J,
    premises: &[J],
) -> Result<Vec<J>, LegacyWorkspaceError> {
    let endpoints = strings(mapping, "sources")
        .into_iter()
        .chain(strings(mapping, "targets"))
        .collect::<HashSet<_>>();
    let mut subjects = endpoints.clone();
    for authority in items(graph, "authorities") {
        if s(authority, "concept") == s(mapping, "id")
            || endpoints.contains(s(authority, "concept"))
        {
            subjects.insert(s(authority, "id").to_owned());
        }
    }
    subjects.insert(s(mapping, "id").to_owned());
    let assessments = items(inputs, "assessments")
        .iter()
        .filter(|a| subjects.contains(s(a, "subject")))
        .collect::<Vec<_>>();
    let evidence = items(inputs, "evidence")
        .iter()
        .map(|e| (s(e, "id"), e))
        .collect::<HashMap<_, _>>();
    DIMENSIONS
        .iter()
        .map(|dimension| {
            let mut values = premises
                .iter()
                .map(|p| {
                    p.array()
                        .unwrap_or(&[])
                        .iter()
                        .find(|v| s(v, "dimension") == *dimension)
                        .cloned()
                        .unwrap_or_else(|| unknown(dimension))
                })
                .collect::<Vec<_>>();
            for a in &assessments {
                if s(a, "dimension") == *dimension {
                    values.push(assessed(a, &evidence)?);
                }
            }
            Ok(combine(dimension, &values))
        })
        .collect()
}
pub(crate) fn graph_summaries(
    graph: &J,
    proofs: &[J],
    inputs: &J,
) -> Result<(Vec<J>, Vec<Option<usize>>), LegacyWorkspaceError> {
    let ids = proofs
        .iter()
        .enumerate()
        .map(|(i, p)| (s(p, "id"), i))
        .collect::<HashMap<_, _>>();
    let mut result = Vec::new();
    let mut ordinals = Vec::new();
    for m in items(graph, "mappings") {
        let index = m
            .get("attributes")
            .and_then(|a| a.get("metamap:derivation"))
            .and_then(J::string)
            .and_then(|id| ids.get(id))
            .copied();
        let dimensions = if let Some(i) = index {
            proofs[i].get("uncertainty").cloned().unwrap_or(J::Null)
        } else {
            J::Array(mapping(graph, m, inputs, &[])?)
        };
        result.push(obj(vec![
            ("mapping", scalar(s(m, "id"))),
            ("dimensions", dimensions),
        ]));
        ordinals.push(index);
    }
    Ok((result, ordinals))
}
fn selected(graph: &J, mapping: &J, select: &J) -> Result<bool, LegacyWorkspaceError> {
    let kinds = items(graph, "entities")
        .iter()
        .filter(|e| e.get("kind").and_then(J::string).is_some())
        .map(|e| vec![s(e, "id"), s(e, "kind")])
        .collect::<Vec<_>>();
    crate::legacy_evaluation::selector(
        &json!({"mapping":project(mapping)?,"selector":project(select)?,"entityKinds":kinds}),
    )
}
pub(crate) fn requirement_issues(
    graph: &J,
    active: &[String],
    summaries: &[J],
    requirements: &[J],
    inputs: &J,
) -> Result<Vec<J>, LegacyWorkspaceError> {
    let summaries = summaries
        .iter()
        .map(|s| (s.get("mapping").and_then(J::string).unwrap_or(""), s))
        .collect::<HashMap<_, _>>();
    let assessments = items(inputs, "assessments")
        .iter()
        .map(|a| (s(a, "id"), a))
        .collect::<HashMap<_, _>>();
    let active = active.iter().map(String::as_str).collect::<HashSet<_>>();
    let mut ids = HashSet::new();
    let mut issues = Vec::new();
    for r in requirements {
        let id = s(r, "id");
        if !ids.insert(id) {
            issues.push(issue(
                "DUPLICATE_UNCERTAINTY_REQUIREMENT",
                "Requirement identity must be unique",
                Some(id),
            ));
        }
        let select = get(r, "select")?;
        for reference in strings(select, "ids") {
            if !summaries.contains_key(reference.as_str()) {
                issues.push(issue(
                    "UNKNOWN_UNCERTAINTY_SELECTOR_MAPPING",
                    &format!("Requirement references missing mapping {reference}"),
                    Some(id),
                ));
            }
        }
        let mut matches = Vec::new();
        for m in items(graph, "mappings") {
            if selected(graph, m, select)? {
                matches.push(m);
            }
        }
        if matches.is_empty() {
            issues.push(issue(
                "STALE_UNCERTAINTY_REQUIREMENT",
                "Requirement selector matches no graph mappings",
                Some(id),
            ));
        }
        for m in matches.into_iter().filter(|m| active.contains(s(m, "id"))) {
            let default = unknown(s(r, "dimension"));
            let dimension = summaries
                .get(s(m, "id"))
                .and_then(|summary| {
                    items(summary, "dimensions")
                        .iter()
                        .find(|d| s(d, "dimension") == s(r, "dimension"))
                })
                .unwrap_or(&default);
            let allowed = strings(r, "allowedStates");
            let refs = strings(dimension, "assessments");
            if !allowed.iter().any(|v| v == s(dimension, "status")) {
                issues.push(issue(
                    "UNCERTAINTY_STATE_NOT_ALLOWED",
                    &format!(
                        "{id} requires {} in [{}]; recorded state is {}{}",
                        s(r, "dimension"),
                        allowed.join(", "),
                        s(dimension, "status"),
                        if items(dimension, "measurementModels").len() > 1 {
                            " with incompatible named measurement models"
                        } else {
                            ""
                        }
                    ),
                    Some(s(m, "id")),
                ));
            }
            if !allowed.iter().any(|v| v == "not-applicable")
                && refs.iter().any(|id| {
                    assessments
                        .get(id.as_str())
                        .is_some_and(|a| s(a, "status") == "not-applicable")
                })
            {
                issues.push(issue(
                    "UNCERTAINTY_NOT_APPLICABLE_NOT_ALLOWED",
                    &format!(
                        "{id} does not permit a contributing {} assessment to be not-applicable",
                        s(r, "dimension")
                    ),
                    Some(s(m, "id")),
                ));
            }
            if matches!(r.get("requireEvidence"), Some(J::Bool(true)))
                && (items(dimension, "evidence").is_empty()
                    || refs.is_empty()
                    || refs.iter().any(|id| {
                        assessments
                            .get(id.as_str())
                            .is_none_or(|a| items(a, "evidence").is_empty())
                    }))
            {
                issues.push(issue(
                    "UNCERTAINTY_EVIDENCE_REQUIRED",
                    &format!(
                        "{id} requires evidence for every contributing {} assessment",
                        s(r, "dimension")
                    ),
                    Some(s(m, "id")),
                ));
            }
        }
    }
    Ok(issues)
}
fn safe_integer(value: Option<&J>) -> Option<f64> {
    match value {
        Some(J::Number(v))
            if v.is_finite() && v.fract() == 0.0 && v.abs() <= 9_007_199_254_740_991.0 =>
        {
            Some(*v)
        }
        _ => None,
    }
}
pub(crate) fn budget_issues(graph: &J, budgets: &[J]) -> Result<Vec<J>, LegacyWorkspaceError> {
    let mappings = items(graph, "mappings")
        .iter()
        .map(|m| s(m, "id"))
        .collect::<HashSet<_>>();
    let mut ids = HashSet::new();
    let mut issues = Vec::new();
    for b in budgets {
        let id = s(b, "id");
        if !ids.insert(id) {
            issues.push(risk_issue(
                "DUPLICATE_CONSUMER_BUDGET",
                "Budget identity must be unique",
                Some(id),
            ));
        }
        let mut rules = HashSet::new();
        for r in items(b, "classifications") {
            let id = s(r, "id");
            if !rules.insert(id) {
                issues.push(risk_issue(
                    "DUPLICATE_RISK_CLASSIFICATION",
                    "Classification identity must be unique within its budget",
                    Some(id),
                ));
            }
            if safe_integer(r.get("cost")).is_none_or(|n| n < 0.0) {
                issues.push(risk_issue(
                    "INVALID_RISK_COST",
                    "Classification cost must be a nonnegative safe integer",
                    Some(id),
                ));
            }
            let select = get(r, "select")?;
            for reference in strings(select, "ids") {
                if !mappings.contains(reference.as_str()) {
                    issues.push(risk_issue(
                        "UNKNOWN_RISK_SELECTOR_MAPPING",
                        &format!("Risk selector references missing mapping {reference}"),
                        Some(id),
                    ));
                }
            }
            let mut matches = false;
            for m in items(graph, "mappings") {
                if selected(graph, m, select)? {
                    matches = true;
                    break;
                }
            }
            if !matches {
                issues.push(risk_issue(
                    "STALE_RISK_CLASSIFICATION",
                    "Risk selector matches no graph mappings",
                    Some(id),
                ));
            }
        }
        for field in [
            "maximumTotalCost",
            "maximumLossyMappings",
            "maximumInferredMappings",
        ] {
            if let Some(v) = b.get(field)
                && safe_integer(Some(v)).is_none_or(|n| n < 0.0)
            {
                issues.push(risk_issue(
                    "INVALID_RISK_LIMIT",
                    "Budget limits must be nonnegative safe integers",
                    Some(s(b, "id")),
                ));
            }
        }
    }
    Ok(issues)
}
fn to_number(v: &J) -> f64 {
    match v {
        J::Number(v) => *v,
        J::Null => 0.0,
        J::Bool(v) => {
            if *v {
                1.0
            } else {
                0.0
            }
        }
        J::String(v) => {
            let s = v.trim_matches(|c: char| c.is_whitespace() || c == '\u{feff}');
            if s.is_empty() {
                0.0
            } else {
                s.parse().unwrap_or(f64::NAN)
            }
        }
        J::Array(v) if v.is_empty() => 0.0,
        J::Array(v) if v.len() == 1 => to_number(&scalar(&display(&v[0]))),
        _ => f64::NAN,
    }
}
pub(crate) fn evaluate_risk(
    graph: &J,
    generation: &J,
    spec: &J,
    used: &[String],
) -> Result<(J, Vec<usize>, Option<usize>), LegacyWorkspaceError> {
    let semantic = get(generation, "semantic")?;
    let budgets = items(semantic, "riskBudgets");
    let mut issues = budget_issues(graph, budgets)?;
    let mappings = items(graph, "mappings")
        .iter()
        .map(|m| (s(m, "id"), m))
        .collect::<HashMap<_, _>>();
    let summaries = items(semantic, "uncertainty")
        .iter()
        .enumerate()
        .map(|(i, s)| (s.get("mapping").and_then(J::string).unwrap_or(""), i))
        .collect::<HashMap<_, _>>();
    let used = unique(used.iter().cloned());
    let lossy = used
        .iter()
        .filter(|id| {
            mappings
                .get(id.as_str())
                .is_some_and(|m| s(m, "lossiness") == "lossy")
        })
        .cloned()
        .collect::<Vec<_>>();
    let inferred = used
        .iter()
        .filter(|id| {
            mappings.get(id.as_str()).is_some_and(|m| {
                m.get("provenance")
                    .is_some_and(|p| s(p, "status") == "inferred")
            })
        })
        .cloned()
        .collect::<Vec<_>>();
    let ordinals = used
        .iter()
        .filter_map(|id| summaries.get(id.as_str()).copied())
        .collect::<Vec<_>>();
    let mut classifications = Vec::new();
    let mut selected_budget = None;
    for id in &used {
        if !mappings.contains_key(id.as_str()) || !summaries.contains_key(id.as_str()) {
            issues.push(risk_issue(
                "INCOMPLETE_PROJECTION_RISK_INPUT",
                "Used mapping and uncertainty input must be available",
                Some(id),
            ));
        }
    }
    if matches!(spec.get("budget"), Some(J::Null)) {
        if budgets
            .iter()
            .any(|b| s(b, "consumer") == s(spec, "consumer"))
        {
            issues.push(risk_issue(
                "CONSUMER_BUDGET_REQUIRED",
                "A consumer with a declared budget must select its matching budget",
                Some(s(spec, "consumer")),
            ));
        }
    } else if let Some((index, budget)) = budgets
        .iter()
        .enumerate()
        .find(|(_, b)| s(b, "id") == s(spec, "budget"))
    {
        if s(budget, "consumer") != s(spec, "consumer") {
            issues.push(risk_issue(
                "CONSUMER_BUDGET_MISMATCH",
                "Requested budget belongs to another consumer",
                Some(s(spec, "consumer")),
            ));
        } else {
            let mut total = 0u128;
            for id in &used {
                let Some(mapping) = mappings.get(id.as_str()) else {
                    continue;
                };
                let mut rules = Vec::new();
                for rule in items(budget, "classifications") {
                    if selected(graph, mapping, get(rule, "select")?)? {
                        rules.push(rule);
                    }
                }
                if rules.len() != 1 {
                    issues.push(risk_issue(if rules.is_empty(){"MISSING_RISK_CLASSIFICATION"}else{"AMBIGUOUS_RISK_CLASSIFICATION"},"Each used mapping must match exactly one consumer classification, including zero cost",Some(id)));
                    continue;
                }
                let Some(cost) = safe_integer(rules[0].get("cost")).filter(|n| *n >= 0.0) else {
                    continue;
                };
                classifications.push(obj(vec![
                    ("mapping", scalar(id)),
                    ("classification", scalar(s(rules[0], "classification"))),
                    ("cost", J::Number(cost)),
                ]));
                total = total.checked_add(cost as u128).ok_or_else(|| {
                    error(
                        "Error",
                        "Risk accumulator exceeds its addressable input range",
                    )
                })?;
            }
            if total > 9_007_199_254_740_991 {
                issues.push(risk_issue(
                    "RISK_COST_OVERFLOW",
                    "Unique mapping costs exceed the safe integer range",
                    Some(s(budget, "id")),
                ));
            } else if let Some(maximum) = safe_integer(budget.get("maximumTotalCost"))
                && (total as f64) > maximum
            {
                issues.push(risk_issue(
                    "CONSUMER_RISK_BUDGET_EXCEEDED",
                    &format!(
                        "Unique mapping cost {total} exceeds consumer maximum {}",
                        display(get(budget, "maximumTotalCost")?)
                    ),
                    Some(s(budget, "id")),
                ));
            }
            for (field, count, code, label) in [
                (
                    "maximumLossyMappings",
                    lossy.len(),
                    "CONSUMER_LOSSY_LIMIT_EXCEEDED",
                    "lossy",
                ),
                (
                    "maximumInferredMappings",
                    inferred.len(),
                    "CONSUMER_INFERRED_LIMIT_EXCEEDED",
                    "inferred",
                ),
            ] {
                if let Some(limit) = budget.get(field)
                    && count as f64 > to_number(limit)
                {
                    issues.push(risk_issue(
                        code,
                        &format!(
                            "Used {label} mapping count {count} exceeds consumer maximum {}",
                            display(limit)
                        ),
                        Some(s(budget, "id")),
                    ));
                }
            }
            if issues.is_empty() {
                selected_budget = Some((index, total as f64));
            }
        }
    } else {
        issues.push(risk_issue(
            "MISSING_CONSUMER_BUDGET",
            "Requested budget is unavailable",
            Some(s(spec, "budget")),
        ));
    }
    let risk = obj(vec![
        (
            "status",
            scalar(if selected_budget.is_some() {
                "evaluated"
            } else {
                "not-evaluated"
            }),
        ),
        ("budget", J::Null),
        ("classifications", J::Array(classifications)),
        (
            "totalCost",
            selected_budget
                .map(|(_, v)| J::Number(v))
                .unwrap_or(J::Null),
        ),
        ("lossyMappings", native(lossy)),
        ("inferredMappings", native(inferred)),
        (
            "uncertainty",
            J::Array(
                ordinals
                    .iter()
                    .map(|i| items(semantic, "uncertainty")[*i].clone())
                    .collect(),
            ),
        ),
    ]);
    Ok((
        obj(vec![("risk", risk), ("issues", J::Array(issues))]),
        ordinals,
        selected_budget.map(|(i, _)| i),
    ))
}
fn report(value: J) -> J {
    obj(vec![("value", value)])
}
pub(crate) fn request(operation: &str, input: &J) -> Result<J, LegacyWorkspaceError> {
    let mut result = match operation {
        "uncertainty-shape" => Ok(report(J::Array(input_shape(
            input.get("inputs").unwrap_or(&J::Null),
            input.get("canonicalError").and_then(J::string),
        )))),
        "uncertainty-validate" => Ok(report(J::Array(validate_inputs(
            get(input, "graph")?,
            get(input, "inputs")?,
            input.get("prospective").and_then(J::string),
            &strings(input, "proofIds"),
        )))),
        "uncertainty-unknown" => Ok(report(unknown(s(input, "dimension")))),
        "uncertainty-combine" => Ok(report(combine(
            s(input, "dimension"),
            items(input, "values"),
        ))),
        "uncertainty-mapping" => Ok(report(J::Array(mapping(
            get(input, "graph")?,
            get(input, "mapping")?,
            get(input, "inputs")?,
            items(input, "premises"),
        )?))),
        "uncertainty-graph" => {
            let (value, ordinals) = graph_summaries(
                get(input, "graph")?,
                items(input, "proofs"),
                get(input, "inputs")?,
            )?;
            Ok(obj(vec![
                ("value", J::Array(value)),
                ("proofOrdinals", native(ordinals)),
            ]))
        }
        "uncertainty-dependency-plan" => {
            let records = items(input, "recordIds")
                .iter()
                .enumerate()
                .filter_map(|(i, v)| v.string().map(|id| (id, i)))
                .collect::<HashMap<_, _>>();
            let ids = unique(items(input, "summary").iter().flat_map(|d| {
                strings(d, "assessments")
                    .into_iter()
                    .chain(strings(d, "evidence"))
            }));
            Ok(report(J::Array(
                ids.into_iter()
                    .map(|id| native(json!({"ordinal":records.get(id.as_str()),"id":id})))
                    .collect(),
            )))
        }
        "uncertainty-bindings" => {
            let values = items(input, "records")
                .iter()
                .map(|record| {
                    Ok(obj(vec![
                        ("id", scalar(s(record, "id"))),
                        (
                            "digest",
                            scalar(
                                &canonical_digest(&project(get(record, "value")?)?)
                                    .map_err(|e| error("Error", &e.to_string()))?,
                            ),
                        ),
                    ]))
                })
                .collect::<Result<Vec<_>, LegacyWorkspaceError>>()?;
            Ok(report(J::Array(values)))
        }
        "uncertainty-summary" => Ok(report(J::Array(
            crate::legacy_semantic::uncertainty_summary_issues(items(input, "summaries"))
                .into_iter()
                .map(|v| match v {
                    J::Object(fields) => J::Object(
                        fields
                            .into_iter()
                            .filter(|(k, _)| k != "severity")
                            .collect(),
                    ),
                    _ => v,
                })
                .collect(),
        ))),
        "uncertainty-requirements" => Ok(report(J::Array(requirement_issues(
            get(input, "graph")?,
            &strings(input, "active"),
            items(input, "summaries"),
            items(input, "requirements"),
            get(input, "inputs")?,
        )?))),
        "risk-budgets" => Ok(report(J::Array(budget_issues(
            get(input, "graph")?,
            items(input, "budgets"),
        )?))),
        "risk-evaluate" => {
            let (value, ordinals, budget) = evaluate_risk(
                get(input, "graph")?,
                get(input, "generation")?,
                get(input, "spec")?,
                &strings(input, "used"),
            )?;
            Ok(obj(vec![
                ("value", value),
                ("summaryOrdinals", native(ordinals)),
                ("budgetOrdinal", native(budget)),
            ]))
        }
        _ => Err(error(
            "TypeError",
            "Unknown original uncertainty/risk operation",
        )),
    }?;
    let mut numbers = Vec::new();
    crate::legacy_viability::numeric_facts(&mut result, &mut Vec::new(), &mut numbers);
    if !numbers.is_empty() {
        let J::Object(fields) = &mut result else {
            unreachable!("report envelope")
        };
        fields.push(("numberFacts".into(), J::Array(numbers)));
    }
    Ok(result)
}
