//! Original built-in constraint decisions over the retained legacy graph view.
use crate::legacy_references::{reference, relation};
use crate::legacy_viability::{ObservationIssue as Issue, items, project, s, strings};
use crate::legacy_workspace::{error, raw};
use crate::{LegacyWorkspaceError, legacy_graph_request};
use patamaps_contracts::{LegacyOrderedJson as J, LegacyReadOnlyJson as Data};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};

pub(crate) const KINDS: [&str; 8] = [
    "core:requires-evidence",
    "core:requires-mapping",
    "core:forbids-mapping",
    "core:unique-target",
    "core:requires-authority",
    "topology:relation-totality",
    "topology:reachable",
    "topology:context-satisfied",
];
fn p<'a>(constraint: &'a J, key: &str) -> Option<&'a J> {
    constraint.get("parameters").and_then(|p| p.get(key))
}
fn ps<'a>(constraint: &'a J, key: &str) -> Option<&'a str> {
    p(constraint, key).and_then(J::string)
}
fn pa(constraint: &J, key: &str) -> Option<Vec<String>> {
    p(constraint, key)?
        .array()?
        .iter()
        .map(|v| v.string().map(str::to_owned))
        .collect()
}
fn has(items: &[J], value: &str) -> bool {
    items.iter().any(|i| i.string() == Some(value))
}
fn unique(values: impl IntoIterator<Item = String>) -> Vec<String> {
    let mut seen = HashSet::new();
    values
        .into_iter()
        .filter(|v| seen.insert(v.clone()))
        .collect()
}
fn issue(c: &J, code: &str, message: &str, subject: Option<&str>) -> Issue {
    Issue::constraint(code, message, subject.unwrap_or(s(c, "id")))
}
fn invalid(c: &J, message: &str) -> Vec<Issue> {
    vec![issue(c, "INVALID_CONSTRAINT_PARAMETERS", message, None)]
}
fn entity_matches(
    e: &J,
    kinds: &[String],
    attributes: Option<&J>,
) -> Result<bool, LegacyWorkspaceError> {
    if !kinds.iter().any(|k| k == s(e, "kind")) {
        return Ok(false);
    }
    if let Some(J::Object(pairs)) = attributes {
        for (key, value) in pairs {
            let Some(actual) = e.get("attributes").and_then(|a| a.get(key)) else {
                return Ok(false);
            };
            if raw(actual)? != raw(value)? {
                return Ok(false);
            }
        }
    }
    Ok(true)
}
fn excluded(e: &J, relation_id: &str) -> bool {
    let Some(a) = e.get("attributes") else {
        return false;
    };
    if s(a, "topologyDisposition") != "excluded" {
        return false;
    }
    a.get("exclusionRelations").is_none()
        || a.get("exclusionRelations")
            .and_then(J::array)
            .is_some_and(|v| has(v, relation_id))
}
fn exclusions(c: &J, e: &J) -> Vec<Issue> {
    let Some(a) = e.get("attributes") else {
        return vec![];
    };
    if s(a, "topologyDisposition") != "excluded" {
        return vec![];
    }
    let mut out = Vec::new();
    if s(a, "exclusionReason").is_empty() || s(a, "exclusionOwner").is_empty() {
        out.push(issue(
            c,
            "INVALID_TOPOLOGY_EXCLUSION",
            &format!(
                "{} is excluded without a non-empty exclusionReason and exclusionOwner",
                s(e, "id")
            ),
            Some(s(e, "id")),
        ));
    }
    if let Some(v) = a.get("exclusionRelations")
        && v.array().is_none_or(|a| {
            a.is_empty()
                || !a
                    .iter()
                    .all(|v| v.string().is_some_and(|s| relation(&Data::string_units(s))))
        })
    {
        out.push(issue(
            c,
            "INVALID_TOPOLOGY_EXCLUSION",
            &format!("{} has invalid exclusionRelations", s(e, "id")),
            Some(s(e, "id")),
        ));
    }
    out
}
fn graph_query(input: Value) -> Result<Value, LegacyWorkspaceError> {
    let request = serde_json::from_value(input).map_err(|e| error("TypeError", &e.to_string()))?;
    legacy_graph_request(request).map_err(|e| error(&e.name, &e.message))
}
pub(crate) fn evaluate(
    c: &J,
    document: &J,
    active: &HashSet<String>,
    evidence: &[J],
    registry: &Value,
) -> Result<Vec<Issue>, LegacyWorkspaceError> {
    let kind = s(c, "kind");
    evaluate_as(kind, c, document, active, evidence, registry, None)
}
pub(crate) fn evaluate_as(
    kind: &str,
    c: &J,
    document: &J,
    active: &HashSet<String>,
    evidence: &[J],
    registry: &Value,
    graph: Option<&Value>,
) -> Result<Vec<Issue>, LegacyWorkspaceError> {
    let id = s(c, "id");
    let allowed: &[&str] = match kind {
        "core:requires-evidence" => &["minimumConfidence", "kinds"],
        "core:requires-mapping" | "core:forbids-mapping" | "core:unique-target" => {
            &["relation", "target", "direction"]
        }
        "core:requires-authority" => &["fact"],
        "topology:relation-totality" => &[
            "subjectKinds",
            "subjectAttributes",
            "relation",
            "direction",
            "cardinality",
            "counterpartKinds",
            "allowExcluded",
        ],
        "topology:reachable" => &["root", "relation", "subjectKinds", "subjectAttributes"],
        "topology:context-satisfied" => &[
            "subjectKinds",
            "subjectAttributes",
            "requiresRelation",
            "providesRelation",
            "renderedInRelation",
            "parentRelation",
            "hostsProviderRelation",
        ],
        _ => return Ok(vec![]),
    };
    if let Some(J::Object(pairs)) = c.get("parameters") {
        let unexpected = pairs
            .iter()
            .filter(|(k, _)| !allowed.contains(&k.as_str()))
            .map(|(k, _)| Data::string_units(k))
            .map(|u| String::from_utf16_lossy(&u))
            .collect::<Vec<_>>();
        if !unexpected.is_empty() {
            return Ok(invalid(
                c,
                &format!(
                    "{id} has unsupported parameter(s): {}",
                    unexpected.join(", ")
                ),
            ));
        }
    }
    let mappings = items(document, "mappings")
        .iter()
        .filter(|m| active.contains(s(m, "id")))
        .collect::<Vec<_>>();
    let subjects = strings(c, "subjects");
    let mut out = Vec::new();
    if kind == "core:requires-evidence" {
        let minimum = match p(c, "minimumConfidence") {
            Some(J::Number(n)) => *n,
            None => 0.0,
            _ => {
                return Ok(invalid(
                    c,
                    &format!("{id} minimumConfidence must be between 0 and 1"),
                ));
            }
        };
        let kinds = pa(c, "kinds");
        if !(0.0..=1.0).contains(&minimum) || (p(c, "kinds").is_some() && kinds.is_none()) {
            return Ok(invalid(
                c,
                &format!("{id} minimumConfidence must be between 0 and 1"),
            ));
        }
        for subject in &subjects {
            if items(document, "mappings")
                .iter()
                .any(|m| s(m, "id") == subject)
                && !active.contains(subject)
            {
                continue;
            }
            let supporting = evidence.iter().any(|e| {
                s(e, "result") == "supports"
                    && has(items(e, "subjects"), subject)
                    && kinds
                        .as_ref()
                        .is_none_or(|k| k.iter().any(|k| k == s(e, "kind")))
                    && match e.get("confidence") {
                        Some(J::Number(n)) => *n >= minimum,
                        None => 0.0 >= minimum,
                        _ => false,
                    }
            });
            if !supporting {
                out.push(issue(
                    c,
                    "REQUIRED_EVIDENCE_MISSING",
                    &format!("{subject} has no supporting evidence meeting {id}"),
                    Some(subject),
                ));
            }
        }
        return Ok(out);
    }
    if matches!(
        kind,
        "core:requires-mapping" | "core:forbids-mapping" | "core:unique-target"
    ) {
        let relation_id = ps(c, "relation");
        let target = ps(c, "target");
        let direction = ps(c, "direction").unwrap_or("source");
        if ["relation", "target", "direction"]
            .iter()
            .any(|k| p(c, k).is_some() && ps(c, k).is_none_or(str::is_empty))
            || !["source", "target", "either"].contains(&direction)
            || relation_id.is_some_and(|r| !relation(&Data::string_units(r)))
            || target.is_some_and(|r| !reference(&Data::string_units(r)))
        {
            return Ok(invalid(
                c,
                &format!("{id} has an invalid relation, target, or direction parameter"),
            ));
        }
        for subject in &subjects {
            let matches = mappings
                .iter()
                .copied()
                .filter(|m| match direction {
                    "target" => has(items(m, "targets"), subject),
                    "either" => {
                        has(items(m, "targets"), subject) || has(items(m, "sources"), subject)
                    }
                    _ => has(items(m, "sources"), subject),
                })
                .filter(|m| {
                    relation_id.is_none_or(|r| s(m, "relation") == r)
                        && target.is_none_or(|t| has(items(m, "targets"), t))
                })
                .collect::<Vec<_>>();
            if kind == "core:requires-mapping" && matches.is_empty() {
                out.push(issue(
                    c,
                    "REQUIRED_MAPPING_MISSING",
                    &format!("{subject} has no active mapping meeting {id}"),
                    Some(subject),
                ));
            }
            if kind == "core:forbids-mapping" && !matches.is_empty() {
                out.push(issue(
                    c,
                    "FORBIDDEN_MAPPING_ACTIVE",
                    &format!(
                        "{subject} has forbidden active mapping(s): {}",
                        matches
                            .iter()
                            .map(|m| s(m, "id"))
                            .collect::<Vec<_>>()
                            .join(", ")
                    ),
                    Some(subject),
                ));
            }
            if kind == "core:unique-target" {
                let counterparts = unique(matches.into_iter().flat_map(|m| {
                    strings(
                        m,
                        if direction == "target"
                            || (direction == "either" && !has(items(m, "sources"), subject))
                        {
                            "sources"
                        } else {
                            "targets"
                        },
                    )
                }));
                if counterparts.len() > 1 {
                    out.push(issue(
                        c,
                        "NON_UNIQUE_MAPPING_TARGET",
                        &format!(
                            "{subject} resolves to {} active targets under {id}",
                            counterparts.len()
                        ),
                        Some(subject),
                    ));
                }
            }
        }
        return Ok(out);
    }
    if kind == "core:requires-authority" {
        let Some(fact) = ps(c, "fact").filter(|v| !v.is_empty()) else {
            return Ok(invalid(
                c,
                &format!("{id} requires a string fact parameter"),
            ));
        };
        let doc = project(document)?;
        let built = match graph {
            Some(graph) => graph.clone(),
            None => graph_query(json!({"operation":"build","document":doc,"registry":registry}))?,
        };
        if built["index"].is_null() {
            return Err(error(
                "MetamapValidationError",
                "Constraint graph is invalid",
            ));
        }
        for subject in &subjects {
            let objects = built.get("objects").cloned().unwrap_or_else(|| json!({"entities":doc["entities"],"mappings":doc["mappings"],"authorities":doc["authorities"]}));
            let resolution = graph_query(
                json!({"operation":"resolve-authority","registry":registry,"index":built["index"],"objects":objects,"id":subject,"fact":fact}),
            )?;
            let status = resolution["status"].as_str().unwrap_or("");
            if status != "resolved" {
                out.push(issue(
                    c,
                    "REQUIRED_AUTHORITY_UNRESOLVED",
                    &format!("{subject} has {status} authority for {fact}"),
                    Some(subject),
                ));
            }
        }
        return Ok(out);
    }
    let kinds = pa(c, "subjectKinds");
    let attrs = p(c, "subjectAttributes");
    let selection_valid = kinds.as_ref().is_some_and(|k| !k.is_empty())
        && attrs.is_none_or(|a| matches!(a, J::Object(_)));
    if kind == "topology:relation-totality" {
        let relation_id = ps(c, "relation").unwrap_or("");
        let direction = ps(c, "direction").unwrap_or("");
        let cardinality = ps(c, "cardinality").unwrap_or("");
        let counterparts = pa(c, "counterpartKinds");
        let allow_excluded = matches!(p(c, "allowExcluded"), Some(J::Bool(true)));
        if !selection_valid
            || !relation(&Data::string_units(relation_id))
            || !["source", "target"].contains(&direction)
            || !["exactly-one", "zero-or-one", "one-or-more", "many"].contains(&cardinality)
            || (p(c, "counterpartKinds").is_some() && counterparts.is_none())
            || p(c, "allowExcluded").is_some_and(|a| !matches!(a, J::Bool(_)))
        {
            return Ok(invalid(
                c,
                &format!(
                    "{id} requires subjectKinds, a relation, source|target direction, and a supported cardinality"
                ),
            ));
        }
        let kinds = kinds.expect("validated subject kinds");
        let selected = items(document, "entities")
            .iter()
            .filter_map(|e| match entity_matches(e, &kinds, attrs) {
                Ok(true) => Some(Ok(e)),
                Ok(false) => None,
                Err(e) => Some(Err(e)),
            })
            .collect::<Result<Vec<_>, _>>()?;
        if selected.is_empty() {
            return Ok(vec![issue(
                c,
                "EMPTY_TOPOLOGY_SELECTION",
                &format!("{id} selects no topology entities"),
                None,
            )]);
        }
        let entity_kinds = items(document, "entities")
            .iter()
            .map(|e| (s(e, "id"), s(e, "kind")))
            .collect::<HashMap<_, _>>();
        for e in selected {
            let subject = s(e, "id");
            out.extend(exclusions(c, e));
            let matches = mappings
                .iter()
                .copied()
                .filter(|m| {
                    s(m, "relation") == relation_id
                        && has(
                            items(
                                m,
                                if direction == "source" {
                                    "sources"
                                } else {
                                    "targets"
                                },
                            ),
                            subject,
                        )
                })
                .collect::<Vec<_>>();
            if excluded(e, relation_id) {
                if !allow_excluded {
                    out.push(issue(
                        c,
                        "TOPOLOGY_EXCLUSION_NOT_ALLOWED",
                        &format!("{subject} is excluded, but {id} does not allow exclusions"),
                        Some(subject),
                    ));
                } else if !matches.is_empty() {
                    out.push(issue(
                        c,
                        "EXCLUDED_TOPOLOGY_SUBJECT_MAPPED",
                        &format!("{subject} is both excluded and mapped through {relation_id}"),
                        Some(subject),
                    ));
                }
                continue;
            }
            let targets = unique(matches.into_iter().flat_map(|m| {
                strings(
                    m,
                    if direction == "source" {
                        "targets"
                    } else {
                        "sources"
                    },
                )
            }));
            let wrong = targets
                .iter()
                .filter(|t| {
                    counterparts.as_ref().is_some_and(|ks| {
                        entity_kinds
                            .get(t.as_str())
                            .is_none_or(|k| !ks.iter().any(|v| v == k))
                    })
                })
                .cloned()
                .collect::<Vec<_>>();
            if !wrong.is_empty() {
                out.push(issue(
                    c,
                    "TOPOLOGY_COUNTERPART_KIND_MISMATCH",
                    &format!(
                        "{subject} resolves through {relation_id} to disallowed kind(s): {}",
                        wrong.join(", ")
                    ),
                    Some(subject),
                ));
            }
            if ["exactly-one", "one-or-more"].contains(&cardinality) && targets.is_empty() {
                out.push(issue(
                    c,
                    "TOPOLOGY_REQUIRED_RELATION_MISSING",
                    &format!("{subject} has no active {relation_id} counterpart"),
                    Some(subject),
                ));
            }
            if ["exactly-one", "zero-or-one"].contains(&cardinality) && targets.len() > 1 {
                out.push(issue(
                    c,
                    "TOPOLOGY_RELATION_AMBIGUOUS",
                    &format!(
                        "{subject} resolves through {relation_id} to {} counterparts",
                        targets.len()
                    ),
                    Some(subject),
                ));
            }
        }
        return Ok(out);
    }
    if kind == "topology:reachable" {
        let root = ps(c, "root").unwrap_or("");
        let relation_id = ps(c, "relation").unwrap_or("");
        if !selection_valid
            || root.is_empty()
            || !items(document, "entities")
                .iter()
                .any(|e| s(e, "id") == root)
            || !relation(&Data::string_units(relation_id))
        {
            return Ok(invalid(
                c,
                &format!("{id} requires a known root, relation, and subjectKinds"),
            ));
        }
        let mut visited = HashSet::from([root.to_owned()]);
        let mut queue = vec![root.to_owned()];
        let mut index = 0;
        while index < queue.len() {
            for m in &mappings {
                if s(m, "relation") == relation_id && has(items(m, "sources"), &queue[index]) {
                    for target in strings(m, "targets") {
                        if visited.insert(target.clone()) {
                            queue.push(target);
                        }
                    }
                }
            }
            index += 1;
        }
        let kinds = kinds.expect("validated subject kinds");
        let mut count = 0;
        for e in items(document, "entities") {
            if entity_matches(e, &kinds, attrs)? {
                count += 1;
                let subject = s(e, "id");
                if !visited.contains(subject) {
                    out.push(issue(
                        c,
                        "TOPOLOGY_ENTITY_UNREACHABLE",
                        &format!("{subject} is not reachable from {root} through {relation_id}"),
                        Some(subject),
                    ));
                }
            }
        }
        if count == 0 {
            out.push(issue(
                c,
                "EMPTY_TOPOLOGY_SELECTION",
                &format!("{id} selects no topology entities"),
                None,
            ));
        }
        return Ok(out);
    }
    let fields = [
        "requiresRelation",
        "providesRelation",
        "renderedInRelation",
        "parentRelation",
        "hostsProviderRelation",
    ];
    let relations = fields.map(|k| ps(c, k).unwrap_or(""));
    if !selection_valid || relations.iter().any(|r| !relation(&Data::string_units(r))) {
        return Ok(invalid(
            c,
            &format!("{id} requires subjectKinds and five valid topology relations"),
        ));
    }
    let [requires, provides, rendered, parent, hosts] = relations;
    let outgoing = |source: &str, relation_id: &str| {
        unique(
            mappings
                .iter()
                .filter(|m| s(m, "relation") == relation_id && has(items(m, "sources"), source))
                .flat_map(|m| strings(m, "targets")),
        )
    };
    let incoming = |target: &str, relation_id: &str| {
        unique(
            mappings
                .iter()
                .filter(|m| s(m, "relation") == relation_id && has(items(m, "targets"), target))
                .flat_map(|m| strings(m, "sources")),
        )
    };
    let kinds = kinds.expect("validated subject kinds");
    let mut count = 0;
    for e in items(document, "entities") {
        if !entity_matches(e, &kinds, attrs)? || excluded(e, requires) {
            continue;
        }
        count += 1;
        let subject = s(e, "id");
        for required in outgoing(subject, requires) {
            let mut level = outgoing(subject, rendered);
            let mut visited = HashSet::new();
            let mut satisfied = false;
            while !level.is_empty() {
                let mut providers = HashSet::new();
                for scope in &level {
                    if outgoing(scope, provides).contains(&required) {
                        providers.insert(scope.clone());
                    }
                    for provider in outgoing(scope, hosts) {
                        if outgoing(&provider, provides).contains(&required) {
                            providers.insert(provider);
                        }
                    }
                }
                if providers.len() == 1 {
                    satisfied = true;
                    break;
                }
                if providers.len() > 1 {
                    out.push(issue(
                        c,
                        "TOPOLOGY_CONTEXT_PROVIDER_AMBIGUOUS",
                        &format!(
                            "{subject} resolves {required} to {} providers at the same scope depth",
                            providers.len()
                        ),
                        Some(subject),
                    ));
                    satisfied = true;
                    break;
                }
                let mut next = Vec::new();
                for scope in &level {
                    visited.insert(scope.clone());
                    for p in incoming(scope, parent) {
                        if !visited.contains(&p) {
                            next.push(p);
                        }
                    }
                }
                level = unique(next);
            }
            if !satisfied {
                out.push(issue(c,"TOPOLOGY_CONTEXT_PROVIDER_MISSING",&format!("{subject} requires {required}, but no provider dominates its rendering scope"),Some(subject)));
            }
        }
    }
    if count == 0 {
        out.push(issue(
            c,
            "EMPTY_TOPOLOGY_SELECTION",
            &format!("{id} selects no topology entities"),
            None,
        ));
    }
    Ok(out)
}
