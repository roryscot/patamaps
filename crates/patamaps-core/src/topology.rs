//! Built-in topology obligations. Declarations are data, never owner grants.
//! Traverse checked incident mappings without materializing a Cartesian graph.
use crate::{CheckError, CheckedGraph, Issue, WorkControl};
use patamaps_contracts::{Constraint, Entity, JsonObject};
use serde_json::Value;
use std::collections::{BTreeSet, HashSet, VecDeque};

const MAX_WORK: usize = 2_000_000;
const MAX_ISSUES: usize = 1_024;
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
            return Err(CheckError(vec![issue(c, "TOPOLOGY_RESOURCE_LIMIT", &c.id)]));
        }
        self.used += 1;
        Ok(())
    }
}
pub(crate) fn supported(kind: &str) -> bool {
    matches!(
        kind,
        "topology:relation-totality" | "topology:reachable" | "topology:context-satisfied"
    )
}
fn issue(c: &Constraint, code: &str, subject: &str) -> Issue {
    Issue::error(
        code,
        format!("Topology obligation {}: {code}", c.id),
        subject,
    )
}
fn invalid(c: &Constraint) -> Vec<Issue> {
    vec![issue(c, "INVALID_CONSTRAINT_PARAMETERS", &c.id)]
}
fn push(issues: &mut Vec<Issue>, finding: Issue, c: &Constraint) -> Result<(), CheckError> {
    if issues.len() >= MAX_ISSUES {
        return Err(CheckError(vec![issue(
            c,
            "TOPOLOGY_DIAGNOSTIC_LIMIT",
            &c.id,
        )]));
    }
    issues.push(finding);
    Ok(())
}
fn strings<'a>(p: &'a JsonObject, name: &str) -> Option<Vec<&'a str>> {
    p.get(name)?.as_array()?.iter().map(Value::as_str).collect()
}
fn selection<'a>(
    c: &Constraint,
    graph: &'a CheckedGraph,
    kinds: &BTreeSet<&str>,
    attributes: Option<&serde_json::Map<String, Value>>,
    work: &mut Work<'_>,
) -> Result<Vec<&'a Entity>, CheckError> {
    let mut selected = Vec::new();
    for entity in &graph.document().entities {
        work.step(c)?;
        let mut matches = kinds.contains(entity.kind.as_str());
        for (name, value) in attributes.into_iter().flatten() {
            work.step(c)?;
            matches &= entity.attributes.as_ref().and_then(|a| a.get(name)) == Some(value);
        }
        if matches {
            selected.push(entity);
        }
    }
    Ok(selected)
}
fn excluded(
    c: &Constraint,
    entity: &Entity,
    relation: Option<&str>,
    work: &mut Work<'_>,
) -> Result<bool, CheckError> {
    let Some(a) = &entity.attributes else {
        return Ok(false);
    };
    if a.get("topologyDisposition").and_then(Value::as_str) != Some("excluded") {
        return Ok(false);
    }
    match (relation, a.get("exclusionRelations")) {
        (Some(r), Some(values)) => {
            for value in values.as_array().into_iter().flatten() {
                work.step(c)?;
                if value.as_str() == Some(r) {
                    return Ok(true);
                }
            }
            Ok(false)
        }
        _ => Ok(true),
    }
}
fn exclusion_valid(
    c: &Constraint,
    entity: &Entity,
    work: &mut Work<'_>,
) -> Result<bool, CheckError> {
    if !excluded(c, entity, None, work)? {
        return Ok(true);
    }
    let a = entity
        .attributes
        .as_ref()
        .expect("excluded entity has attributes");
    if !["exclusionReason", "exclusionOwner"].iter().all(|key| {
        a.get(*key)
            .and_then(Value::as_str)
            .is_some_and(|s| !s.is_empty())
    }) {
        return Ok(false);
    }
    if let Some(value) = a.get("exclusionRelations") {
        let Some(values) = value.as_array().filter(|v| !v.is_empty()) else {
            return Ok(false);
        };
        for value in values {
            work.step(c)?;
            if !value.as_str().is_some_and(crate::graph::relation_id) {
                return Ok(false);
            }
        }
    }
    Ok(true)
}
fn counterparts<'a>(
    c: &Constraint,
    graph: &'a CheckedGraph,
    active: &HashSet<String>,
    subject: &str,
    relation: &str,
    outgoing: bool,
    work: &mut Work<'_>,
) -> Result<(bool, BTreeSet<&'a str>), CheckError> {
    let mut found = false;
    let mut result = BTreeSet::new();
    for m in graph.incident(subject) {
        work.step(c)?;
        let side = if outgoing { &m.sources } else { &m.targets };
        if m.relation != relation || !active.contains(&m.id) {
            continue;
        }
        let mut on_side = false;
        for endpoint in side {
            work.step(c)?;
            if endpoint == subject {
                on_side = true;
                break;
            }
        }
        if !on_side {
            continue;
        }
        found = true;
        for endpoint in if outgoing { &m.targets } else { &m.sources } {
            work.step(c)?;
            result.insert(endpoint.as_str());
        }
    }
    Ok((found, result))
}

pub(crate) fn evaluate(
    c: &Constraint,
    graph: &CheckedGraph,
    active: &HashSet<String>,
    work: &mut Work<'_>,
) -> Result<Vec<Issue>, CheckError> {
    let empty = JsonObject::new();
    let p = c.parameters.as_ref().unwrap_or(&empty);
    let allowed: &[&str] = match c.kind.as_str() {
        "topology:relation-totality" => &[
            "subjectKinds",
            "subjectAttributes",
            "relation",
            "direction",
            "cardinality",
            "counterpartKinds",
            "allowExcluded",
        ],
        "topology:reachable" => &["subjectKinds", "subjectAttributes", "root", "relation"],
        _ => &[
            "subjectKinds",
            "subjectAttributes",
            "requiresRelation",
            "providesRelation",
            "renderedInRelation",
            "parentRelation",
            "hostsProviderRelation",
        ],
    };
    if p.keys().any(|name| !allowed.contains(&name.as_str())) {
        return Ok(invalid(c));
    }
    let Some(kinds) = strings(p, "subjectKinds").filter(|v| !v.is_empty()) else {
        return Ok(invalid(c));
    };
    let mut kind_set = BTreeSet::new();
    for kind in kinds {
        work.step(c)?;
        kind_set.insert(kind);
    }
    let attributes = p.get("subjectAttributes").and_then(Value::as_object);
    if p.contains_key("subjectAttributes") && attributes.is_none() {
        return Ok(invalid(c));
    }
    match c.kind.as_str() {
        "topology:relation-totality" => {
            let relation = p.get("relation").and_then(Value::as_str);
            let direction = p.get("direction").and_then(Value::as_str);
            let cardinality = p.get("cardinality").and_then(Value::as_str);
            let counterpart_kinds = strings(p, "counterpartKinds");
            let allow = p.get("allowExcluded").and_then(Value::as_bool);
            if relation.is_none_or(|r| !crate::graph::relation_id(r))
                || !matches!(direction, Some("source" | "target"))
                || !matches!(
                    cardinality,
                    Some("exactly-one" | "zero-or-one" | "one-or-more" | "many")
                )
                || (p.contains_key("counterpartKinds") && counterpart_kinds.is_none())
                || (p.contains_key("allowExcluded") && allow.is_none())
            {
                return Ok(invalid(c));
            }
            let relation = relation.expect("checked relation");
            let counterpart_kinds = if let Some(values) = counterpart_kinds {
                let mut kinds = BTreeSet::new();
                for value in values {
                    work.step(c)?;
                    kinds.insert(value);
                }
                Some(kinds)
            } else {
                None
            };
            let subjects = selection(c, graph, &kind_set, attributes, work)?;
            if subjects.is_empty() {
                return Ok(vec![issue(c, "EMPTY_TOPOLOGY_SELECTION", &c.id)]);
            }
            let mut issues = Vec::new();
            for entity in subjects {
                work.step(c)?;
                if !exclusion_valid(c, entity, work)? {
                    push(
                        &mut issues,
                        issue(c, "INVALID_TOPOLOGY_EXCLUSION", &entity.id),
                        c,
                    )?;
                }
                let (mapped, counterparts) = counterparts(
                    c,
                    graph,
                    active,
                    &entity.id,
                    relation,
                    direction == Some("source"),
                    work,
                )?;
                if excluded(c, entity, Some(relation), work)? {
                    if !allow.unwrap_or(false) {
                        push(
                            &mut issues,
                            issue(c, "TOPOLOGY_EXCLUSION_NOT_ALLOWED", &entity.id),
                            c,
                        )?;
                    } else if mapped {
                        push(
                            &mut issues,
                            issue(c, "EXCLUDED_TOPOLOGY_SUBJECT_MAPPED", &entity.id),
                            c,
                        )?;
                    }
                    continue;
                }
                if counterpart_kinds.as_ref().is_some_and(|ks| {
                    counterparts.iter().any(|id| {
                        graph
                            .entity(id)
                            .is_none_or(|e| !ks.contains(e.kind.as_str()))
                    })
                }) {
                    push(
                        &mut issues,
                        issue(c, "TOPOLOGY_COUNTERPART_KIND_MISMATCH", &entity.id),
                        c,
                    )?;
                }
                if counterparts.is_empty()
                    && matches!(cardinality, Some("exactly-one" | "one-or-more"))
                {
                    push(
                        &mut issues,
                        issue(c, "TOPOLOGY_REQUIRED_RELATION_MISSING", &entity.id),
                        c,
                    )?;
                }
                if counterparts.len() > 1
                    && matches!(cardinality, Some("exactly-one" | "zero-or-one"))
                {
                    push(
                        &mut issues,
                        issue(c, "TOPOLOGY_RELATION_AMBIGUOUS", &entity.id),
                        c,
                    )?;
                }
            }
            Ok(issues)
        }
        "topology:reachable" => {
            let root = p.get("root").and_then(Value::as_str);
            let relation = p.get("relation").and_then(Value::as_str);
            if root.is_none_or(|r| graph.entity(r).is_none())
                || relation.is_none_or(|r| !crate::graph::relation_id(r))
            {
                return Ok(invalid(c));
            }
            let root = root.expect("checked root");
            let relation = relation.expect("checked relation");
            let subjects = selection(c, graph, &kind_set, attributes, work)?;
            if subjects.is_empty() {
                return Ok(vec![issue(c, "EMPTY_TOPOLOGY_SELECTION", &c.id)]);
            }
            let mut visited = BTreeSet::from([root]);
            let mut queue = VecDeque::from([root]);
            while let Some(current) = queue.pop_front() {
                work.step(c)?;
                for target in counterparts(c, graph, active, current, relation, true, work)?.1 {
                    if visited.insert(target) {
                        queue.push_back(target);
                    }
                }
            }
            let mut issues = Vec::new();
            for entity in subjects {
                work.step(c)?;
                if !visited.contains(entity.id.as_str()) {
                    push(
                        &mut issues,
                        issue(c, "TOPOLOGY_ENTITY_UNREACHABLE", &entity.id),
                        c,
                    )?;
                }
            }
            Ok(issues)
        }
        _ => {
            let names = [
                "requiresRelation",
                "providesRelation",
                "renderedInRelation",
                "parentRelation",
                "hostsProviderRelation",
            ];
            let relations: Option<Vec<&str>> = names
                .iter()
                .map(|name| {
                    p.get(*name)
                        .and_then(Value::as_str)
                        .filter(|r| crate::graph::relation_id(r))
                })
                .collect();
            let Some(relations) = relations else {
                return Ok(invalid(c));
            };
            let [requires, provides, rendered, parent, hosts] = relations[..] else {
                unreachable!("five relation parameters");
            };
            let mut subjects = Vec::new();
            for entity in selection(c, graph, &kind_set, attributes, work)? {
                work.step(c)?;
                if !excluded(c, entity, Some(requires), work)? {
                    subjects.push(entity);
                }
            }
            if subjects.is_empty() {
                return Ok(vec![issue(c, "EMPTY_TOPOLOGY_SELECTION", &c.id)]);
            }
            let mut issues = Vec::new();
            for entity in subjects {
                let required = counterparts(c, graph, active, &entity.id, requires, true, work)?.1;
                let initial = counterparts(c, graph, active, &entity.id, rendered, true, work)?.1;
                for context in required {
                    let mut level = initial.clone();
                    let mut visited = BTreeSet::<&str>::new();
                    let mut resolved = false;
                    while !level.is_empty() {
                        let mut providers = BTreeSet::new();
                        for scope in &level {
                            work.step(c)?;
                            if counterparts(c, graph, active, scope, provides, true, work)?
                                .1
                                .contains(context)
                            {
                                providers.insert(*scope);
                            }
                            for provider in
                                counterparts(c, graph, active, scope, hosts, true, work)?.1
                            {
                                if counterparts(c, graph, active, provider, provides, true, work)?
                                    .1
                                    .contains(context)
                                {
                                    providers.insert(provider);
                                }
                            }
                        }
                        if !providers.is_empty() {
                            resolved = true;
                            if providers.len() > 1 {
                                push(
                                    &mut issues,
                                    issue(c, "TOPOLOGY_CONTEXT_PROVIDER_AMBIGUOUS", &entity.id),
                                    c,
                                )?;
                            }
                            break;
                        }
                        visited.extend(level.iter().copied());
                        let mut next = BTreeSet::new();
                        for scope in &level {
                            for ancestor in
                                counterparts(c, graph, active, scope, parent, false, work)?.1
                            {
                                if !visited.contains(ancestor) {
                                    next.insert(ancestor);
                                }
                            }
                        }
                        level = next;
                    }
                    if !resolved {
                        push(
                            &mut issues,
                            issue(c, "TOPOLOGY_CONTEXT_PROVIDER_MISSING", &entity.id),
                            c,
                        )?;
                    }
                }
            }
            Ok(issues)
        }
    }
}
