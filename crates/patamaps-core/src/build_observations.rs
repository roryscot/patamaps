//! Closed-world validation of explicit bindings to observed entity fields.
//! Existence/cardinality remain ordinary mapping obligations. No evidence is upgraded.
use crate::{CheckError, CheckedGraph, Issue, WorkControl};
use patamaps_contracts::{Constraint, Entity, canonical_bytes};
use serde::Deserialize;
use serde_json::Value;
use std::collections::{BTreeSet, HashSet};

const MAX_WORK: usize = 2_000_000;
pub(crate) fn supported(kind: &str) -> bool {
    kind == "build:observation-binding-v1"
}

pub(crate) struct Work<'a> {
    control: Option<&'a WorkControl>,
    used: usize,
}
impl<'a> Work<'a> {
    pub(crate) fn new(control: Option<&'a WorkControl>) -> Self {
        Self { control, used: 0 }
    }
    fn step(&mut self, c: &Constraint) -> Result<(), CheckError> {
        crate::control::poll(self.control)?;
        if self.used >= MAX_WORK {
            return Err(CheckError(vec![issue(
                c,
                "BUILD_OBSERVATION_RESOURCE_LIMIT",
                &c.id,
                "Observation-binding work bound exceeded",
            )]));
        }
        self.used += 1;
        Ok(())
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Selector {
    relation: String,
    target_kind: String,
    conditions: Vec<Condition>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Condition {
    path: Vec<String>,
    equals: Value,
}

fn issue(c: &Constraint, code: &str, subject: &str, message: &str) -> Issue {
    Issue::error(code, format!("{}: {message}", c.id), subject)
}
fn matches(
    entity: &Entity,
    conditions: &[(Vec<String>, Vec<u8>)],
    work: &mut Work<'_>,
    c: &Constraint,
) -> Result<bool, CheckError> {
    work.step(c)?;
    let value = serde_json::to_value(entity).map_err(|e| {
        CheckError(vec![issue(
            c,
            "BUILD_OBSERVATION_ENCODING",
            &entity.id,
            &e.to_string(),
        )])
    })?;
    for (path, expected) in conditions {
        let mut selected = Some(&value);
        for component in path {
            work.step(c)?;
            selected = selected.and_then(|v| match v {
                Value::Object(object) => object.get(component),
                Value::Array(array) => component.parse::<usize>().ok().and_then(|i| array.get(i)),
                _ => None,
            });
        }
        let Some(value) = selected else {
            return Ok(false);
        };
        if canonical_bytes(value)? != *expected {
            return Ok(false);
        }
        work.step(c)?;
    }
    Ok(true)
}

fn selected<'g>(
    c: &Constraint,
    graph: &'g CheckedGraph,
    work: &mut Work<'_>,
) -> Result<Option<(String, BTreeSet<&'g str>)>, CheckError> {
    let Some(parameters) = &c.parameters else {
        return Ok(None);
    };
    let Ok(selector) = serde_json::from_slice::<Selector>(&canonical_bytes(parameters)?) else {
        return Ok(None);
    };
    if c.subjects.is_empty()
        || c.subjects.len() > 128
        || c.subjects.iter().collect::<BTreeSet<_>>().len() != c.subjects.len()
        || graph.relation(&selector.relation).is_none()
        || selector.target_kind.is_empty()
        || selector.target_kind.len() > 256
        || selector.conditions.is_empty()
        || selector.conditions.len() > 64
    {
        return Ok(None);
    }
    let mut conditions = Vec::new();
    for condition in selector.conditions {
        work.step(c)?;
        if condition.path.is_empty()
            || condition.path.len() > 32
            || condition.path.iter().any(|p| p.len() > 256)
        {
            return Ok(None);
        }
        let expected = canonical_bytes(&condition.equals)?;
        if expected.len() > 65536 {
            return Ok(None);
        }
        conditions.push((condition.path, expected));
    }
    let mut observed = BTreeSet::new();
    for entity in &graph.document().entities {
        work.step(c)?;
        if entity.kind == selector.target_kind && matches(entity, &conditions, work, c)? {
            observed.insert(entity.id.as_str());
        }
    }
    Ok(Some((selector.relation, observed)))
}

/// Read-only matching proposals over a structurally checked graph.
/// This does not evaluate a policy, select active bindings or create admitted state.
pub fn observation_matches(
    graph: &CheckedGraph,
    constraint: &Constraint,
) -> Result<Vec<String>, CheckError> {
    if !supported(&constraint.kind) {
        return Err(CheckError(vec![issue(
            constraint,
            "UNKNOWN_CONSTRAINT_KIND",
            &constraint.id,
            "Unsupported observation query version",
        )]));
    }
    let mut work = Work::new(None);
    let Some((_, observed)) = selected(constraint, graph, &mut work)? else {
        return Err(CheckError(vec![issue(
            constraint,
            "INVALID_CONSTRAINT_PARAMETERS",
            &constraint.id,
            "Invalid bounded observation selector",
        )]));
    };
    let mut result: Vec<String> = observed.into_iter().map(str::to_owned).collect();
    result.sort_by(|a, b| a.encode_utf16().cmp(b.encode_utf16()));
    Ok(result)
}

pub(crate) fn evaluate(
    c: &Constraint,
    graph: &CheckedGraph,
    active: &HashSet<String>,
    work: &mut Work<'_>,
) -> Result<Vec<Issue>, CheckError> {
    let Some((relation, observed)) = selected(c, graph, work)? else {
        return Ok(vec![issue(
            c,
            "INVALID_CONSTRAINT_PARAMETERS",
            &c.id,
            "Expected unique requirement subjects and a bounded relation/kind/field selector",
        )]);
    };
    let mut findings = Vec::new();
    for subject in &c.subjects {
        work.step(c)?;
        let mut bound = BTreeSet::new();
        for mapping in graph.incident(subject) {
            work.step(c)?;
            if active.contains(&mapping.id)
                && mapping.relation == relation
                && mapping.sources.contains(subject)
            {
                for target in &mapping.targets {
                    work.step(c)?;
                    bound.insert(target.as_str());
                }
            }
        }
        if bound != observed {
            findings.push(issue(
                c,
                "BUILD_OBSERVATION_BINDING_MISMATCH",
                subject,
                "Active bindings differ from the complete observed selector result",
            ));
        }
    }
    Ok(findings)
}
