//! Original context, selector and impact observations. Numeric transport facts
//! are private inputs to read-only decisions, never graph admission values.
use crate::admission::{matches_context_with, selector_matches_with, visit_required};
use crate::legacy_workspace::{error, get, list, locale, native, obj, parse, raw, text};
use crate::{LegacyWorkspaceError, LegacyWorkspaceRequest};
use patamaps_contracts::{
    ComparisonOperator, ContextExpression, ExistsOperator, JsonObject, LegacyOrderedJson as J,
    LegacyReadOnlyJson as Data, MappingSelector, MembershipOperator, ProvenanceStatus,
};
use serde_json::{Value, json, value::RawValue};
use std::collections::{HashMap, HashSet};

const NUMBER_FACT: &str = "urn:patamaps:internal:legacy-number-fact";
fn marker(kind: &str) -> Value {
    json!({NUMBER_FACT:kind})
}
fn fact(value: &Value) -> Option<&str> {
    value.get(NUMBER_FACT).and_then(Value::as_str)
}
fn equal(a: &Value, b: &Value) -> bool {
    if fact(a) == Some("hole") || fact(b) == Some("hole") {
        return false;
    }
    match (fact(a), fact(b)) {
        (Some(a), Some(b)) => a == b,
        (Some(_), None) | (None, Some(_)) => false,
        (None, None) if a.is_number() && b.is_number() => a.as_f64() == b.as_f64(),
        (None, None) => a == b,
    }
}
pub(crate) struct LegacyNumberFact {
    pub path: Vec<String>,
    pub kind: String,
}
pub(crate) fn number_facts(input: &J) -> Result<Vec<LegacyNumberFact>, LegacyWorkspaceError> {
    let value = get(input, "value")?;
    let mut seen = HashSet::new();
    let mut facts = Vec::new();
    for record in list(input, "numbers")? {
        let path: Vec<String> = list(record, "path")?
            .iter()
            .map(|v| {
                v.string()
                    .map(str::to_owned)
                    .ok_or_else(|| error("TypeError", "Numeric fact paths require strings"))
            })
            .collect::<Result<_, _>>()?;
        if path.is_empty() || !seen.insert(path.clone()) {
            return Err(error(
                "TypeError",
                "Numeric fact path must be unique and nonempty",
            ));
        }
        let kind = text(record, "kind")?;
        if ![
            "nan",
            "negative-zero",
            "positive-infinity",
            "negative-infinity",
            "hole",
        ]
        .contains(&kind)
        {
            return Err(error("TypeError", "Unknown numeric observation fact"));
        }
        let mut slot = value;
        for key in &path {
            slot = match slot {
                J::Array(values) => key.parse::<usize>().ok().and_then(|i| values.get(i)),
                _ => slot.get(key),
            }
            .ok_or_else(|| error("TypeError", "Numeric observation path does not exist"))?;
        }
        if !matches!(slot, J::Number(v) if *v == 0.0) {
            return Err(error(
                "TypeError",
                "Numeric observation requires a zero placeholder",
            ));
        }
        facts.push(LegacyNumberFact {
            path,
            kind: kind.to_owned(),
        });
    }
    Ok(facts)
}
fn value_input(input: &J) -> Result<Value, LegacyWorkspaceError> {
    let mut value =
        Data::projected_value(get(input, "value")?).map_err(|e| error("Error", &e.to_string()))?;
    for fact in number_facts(input)? {
        let mut slot = &mut value;
        for key in &fact.path {
            slot = if slot.is_array() {
                key.parse::<usize>().ok().and_then(|i| slot.get_mut(i))
            } else {
                slot.get_mut(key)
            }
            .expect("numeric observation path was checked");
        }
        *slot = marker(&fact.kind);
    }
    Ok(value)
}
fn field<'a>(value: &'a Value, key: &str) -> Result<&'a Value, LegacyWorkspaceError> {
    value
        .get(key)
        .ok_or_else(|| error("TypeError", &format!("Evaluation input requires {key}")))
}
fn string<'a>(value: &'a Value, key: &str) -> Result<&'a str, LegacyWorkspaceError> {
    field(value, key)?
        .as_str()
        .ok_or_else(|| error("TypeError", &format!("Evaluation {key} requires a string")))
}
fn array<'a>(value: &'a Value, key: &str) -> Result<&'a [Value], LegacyWorkspaceError> {
    field(value, key)?
        .as_array()
        .map(Vec::as_slice)
        .ok_or_else(|| error("TypeError", &format!("Evaluation {key} requires an array")))
}
fn expression(v: &Value) -> Result<ContextExpression, LegacyWorkspaceError> {
    for (field, all) in [("all", true), ("any", false)] {
        if v.get(field).is_some() {
            let children = array(v, field)?
                .iter()
                .filter(|v| fact(v) != Some("hole"))
                .map(expression)
                .collect::<Result<_, _>>()?;
            return Ok(if all {
                ContextExpression::All { all: children }
            } else {
                ContextExpression::Any { any: children }
            });
        }
    }
    if let Some(v) = v.get("not") {
        return Ok(ContextExpression::Not {
            not: Box::new(expression(v)?),
        });
    }
    let key = string(v, "key")?.to_owned();
    let operator = string(v, "operator")?;
    Ok(match operator {
        "exists" => ContextExpression::Exists {
            key,
            operator: ExistsOperator::Exists,
            value: Some(v.get("value") != Some(&Value::Bool(false))),
        },
        "equals" | "not-equals" => ContextExpression::Comparison {
            key,
            operator: if operator == "equals" {
                ComparisonOperator::Equals
            } else {
                ComparisonOperator::NotEquals
            },
            value: v
                .get("value")
                .cloned()
                .unwrap_or_else(|| marker("undefined")),
        },
        _ => ContextExpression::Membership {
            key,
            operator: if operator == "in" || v.get("values").is_none() {
                MembershipOperator::In
            } else {
                MembershipOperator::NotIn
            },
            values: if v.get("values").is_some() {
                array(v, "values")?.to_vec()
            } else {
                vec![]
            },
        },
    })
}
fn context(v: &Value) -> Result<JsonObject, LegacyWorkspaceError> {
    v.as_object()
        .map(|v| v.iter().map(|(k, v)| (k.clone(), v.clone())).collect())
        .ok_or_else(|| error("TypeError", "Evaluation context requires an object"))
}
fn primitive_kind(kind: &str) -> bool {
    ["null", "boolean", "number", "string"].contains(&kind)
}
fn parse_context_observation(v: &J) -> Result<J, LegacyWorkspaceError> {
    if text(v, "rootKind")? != "object" {
        return Err(error("Error", "Evaluation context must be an object"));
    }
    let mut indices = Vec::new();
    for (index, entry) in list(v, "entries")?.iter().enumerate() {
        let key = text(entry, "key")?;
        if key.is_empty() {
            return Err(error("Error", "Evaluation context keys cannot be empty"));
        }
        let kind = text(entry, "kind")?;
        if !primitive_kind(kind)
            && (kind != "array"
                || !list(entry, "elementKinds")?
                    .iter()
                    .all(|v| v.string().is_some_and(primitive_kind)))
        {
            return Err(error(
                "Error",
                &format!("Evaluation context {key} must be a JSON primitive or primitive array"),
            ));
        }
        indices.push(J::Number(index as f64));
    }
    Ok(obj(vec![("indices", J::Array(indices))]))
}
pub(crate) fn selector(v: &Value) -> Result<bool, LegacyWorkspaceError> {
    let mapping = field(v, "mapping")?;
    let source = field(v, "selector")?;
    let mut projected = serde_json::Map::new();
    for key in [
        "ids",
        "relations",
        "sourceKinds",
        "targetKinds",
        "provenanceStatuses",
    ] {
        if let Some(v) = source
            .get(key)
            .filter(|v| !v.is_null() && v != &&Value::Bool(false))
        {
            projected.insert(key.into(), v.clone());
        }
    }
    let s: MappingSelector = serde_json::from_value(Value::Object(projected))
        .map_err(|e| error("TypeError", &e.to_string()))?;
    let mut kinds = HashMap::new();
    for pair in array(v, "entityKinds")? {
        let pair = pair
            .as_array()
            .ok_or_else(|| error("TypeError", "Entity kind entries require pairs"))?;
        if pair.len() != 2 {
            return Err(error("TypeError", "Entity kind entries require two items"));
        }
        kinds.insert(
            pair[0]
                .as_str()
                .ok_or_else(|| error("TypeError", "Entity kind keys require strings"))?,
            pair[1]
                .as_str()
                .ok_or_else(|| error("TypeError", "Entity kinds require strings"))?,
        );
    }
    let endpoints = |field_name: &str, selected: &[String]| -> bool {
        mapping
            .get(field_name)
            .and_then(Value::as_array)
            .is_some_and(|ids| {
                ids.iter().any(|id| {
                    id.as_str()
                        .and_then(|id| kinds.get(id))
                        .is_some_and(|kind| selected.iter().any(|v| v == kind))
                })
            })
    };
    let status = mapping
        .get("provenance")
        .and_then(|v| v.get("status"))
        .and_then(|v| serde_json::from_value::<ProvenanceStatus>(v.clone()).ok());
    Ok(selector_matches_with(
        &s,
        string(mapping, "id")?,
        string(mapping, "relation")?,
        |k| endpoints("sources", k),
        |k| endpoints("targets", k),
        |selected| status.is_some_and(|s| selected.contains(&s)),
    ))
}

struct Edge {
    mapping: String,
    target: String,
}
fn strings(value: &Value, key: &str) -> Result<Vec<String>, LegacyWorkspaceError> {
    array(value, key)?
        .iter()
        .map(|v| {
            v.as_str()
                .map(str::to_owned)
                .ok_or_else(|| error("TypeError", &format!("Evaluation {key} requires strings")))
        })
        .collect()
}
fn index_by_id(items: &[Value]) -> Result<HashMap<&str, &Value>, LegacyWorkspaceError> {
    items
        .iter()
        .map(|v| string(v, "id").map(|id| (id, v)))
        .collect()
}
fn enqueue(
    paths: &mut HashMap<String, Vec<String>>,
    queue: &mut Vec<String>,
    order: &mut Vec<String>,
    id: &str,
    path: Vec<String>,
) {
    if !paths.contains_key(id) {
        paths.insert(id.to_owned(), path);
        order.push(id.to_owned());
        queue.push(id.to_owned());
    }
}
fn extended(path: &[String], id: &str) -> Vec<String> {
    let mut v = path.to_vec();
    v.push(id.into());
    v
}
pub(crate) fn impact(v: &Value, locale_name: &str) -> Result<J, LegacyWorkspaceError> {
    let graph = field(v, "document")?;
    let options = field(v, "options")?;
    let mut changed = strings(options, "changedSubjects")?;
    changed.sort_by_key(|s| Data::string_units(s));
    changed.dedup();
    let mappings = array(graph, "mappings")?;
    let authorities = array(graph, "authorities")?;
    let map_index = index_by_id(mappings)?;
    let authority_index = index_by_id(authorities)?;
    let policy = options.get("policy");
    let constraints = index_by_id(
        policy
            .and_then(|p| p.get("constraints"))
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or(&[]),
    )?;
    let evidence = index_by_id(
        policy
            .and_then(|p| p.get("evidence"))
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or(&[]),
    )?;
    let proofs = options
        .get("derivations")
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or(&[]);
    let mut directions = HashMap::new();
    if let Some(registry) = v.get("registry") {
        for d in array(registry, "definitions")? {
            directions.insert(
                string(d, "key")?.to_owned(),
                d.get("value")
                    .and_then(|v| v.get("impactDirection"))
                    .and_then(Value::as_str)
                    .unwrap_or("both")
                    .to_owned(),
            );
        }
    } else {
        // Direct callers get exactly the original core direction defaults.
        let core = parse(include_str!("legacy_core.json"))?;
        for d in list(&core, "relations")? {
            directions.insert(
                text(d, "id")?.to_owned(),
                d.get("impactDirection")
                    .and_then(J::string)
                    .unwrap_or("both")
                    .to_owned(),
            );
        }
    }
    let active = options
        .get("activeMappings")
        .map(|_| strings(options, "activeMappings"))
        .transpose()?
        .map(|v| v.into_iter().collect::<HashSet<_>>());
    let mut adjacency: HashMap<String, Vec<Edge>> = HashMap::new();
    for mapping in mappings {
        let id = string(mapping, "id")?;
        if active.as_ref().is_some_and(|v| !v.contains(id)) {
            continue;
        }
        let direction = directions
            .get(string(mapping, "relation")?)
            .map(String::as_str)
            .unwrap_or("both");
        let sources = strings(mapping, "sources")?;
        let targets = strings(mapping, "targets")?;
        for source in &sources {
            for target in &targets {
                if ["source-to-target", "both"].contains(&direction) {
                    adjacency.entry(source.clone()).or_default().push(Edge {
                        mapping: id.into(),
                        target: target.clone(),
                    });
                }
                if ["target-to-source", "both"].contains(&direction) {
                    adjacency.entry(target.clone()).or_default().push(Edge {
                        mapping: id.into(),
                        target: source.clone(),
                    });
                }
            }
        }
    }
    let mut proof_edges: HashMap<String, HashSet<String>> = HashMap::new();
    for proof in proofs {
        let id = string(proof, "id")?;
        for premise in array(proof, "premises")? {
            proof_edges
                .entry(string(premise, "mapping")?.into())
                .or_default()
                .insert(id.into());
        }
        proof_edges
            .entry(id.into())
            .or_default()
            .insert(string(field(proof, "result")?, "id")?.into());
    }
    let mut paths = HashMap::new();
    let mut queue = Vec::new();
    let mut order = Vec::new();
    for seed in &changed {
        enqueue(&mut paths, &mut queue, &mut order, seed, vec![seed.clone()]);
        if let Some(mapping) = map_index.get(seed.as_str()) {
            for endpoint in strings(mapping, "sources")?
                .into_iter()
                .chain(strings(mapping, "targets")?)
            {
                enqueue(
                    &mut paths,
                    &mut queue,
                    &mut order,
                    &endpoint,
                    vec![seed.clone(), endpoint.clone()],
                );
            }
        }
        if let Some(authority) = authority_index.get(seed.as_str()) {
            for key in ["concept", "source"] {
                let endpoint = string(authority, key)?;
                enqueue(
                    &mut paths,
                    &mut queue,
                    &mut order,
                    endpoint,
                    vec![seed.clone(), endpoint.into()],
                );
            }
        }
        for declaration in [constraints.get(seed.as_str()), evidence.get(seed.as_str())]
            .into_iter()
            .flatten()
        {
            for subject in strings(declaration, "subjects")? {
                enqueue(
                    &mut paths,
                    &mut queue,
                    &mut order,
                    &subject,
                    vec![seed.clone(), subject.clone()],
                );
            }
        }
    }
    let mut cursor = 0;
    while cursor < queue.len() {
        let current = queue[cursor].clone();
        cursor += 1;
        let path = paths[&current].clone();
        if let Some(targets) = proof_edges.get(&current) {
            let mut targets: Vec<_> = targets.iter().collect();
            targets.sort_by_key(|s| Data::string_units(s));
            for target in targets {
                enqueue(
                    &mut paths,
                    &mut queue,
                    &mut order,
                    target,
                    extended(&path, target),
                );
            }
        }
        if !proofs.is_empty()
            && let Some(mapping) = map_index.get(current.as_str())
        {
            for endpoint in strings(mapping, "sources")?
                .into_iter()
                .chain(strings(mapping, "targets")?)
            {
                enqueue(
                    &mut paths,
                    &mut queue,
                    &mut order,
                    &endpoint,
                    extended(&path, &endpoint),
                );
            }
        }
        for edge in adjacency.get(&current).into_iter().flatten() {
            let mapping_path = extended(&path, &edge.mapping);
            if !proofs.is_empty() {
                enqueue(
                    &mut paths,
                    &mut queue,
                    &mut order,
                    &edge.mapping,
                    mapping_path.clone(),
                );
            } else if !paths.contains_key(&edge.mapping) {
                order.push(edge.mapping.clone());
                paths.insert(edge.mapping.clone(), mapping_path.clone());
            }
            enqueue(
                &mut paths,
                &mut queue,
                &mut order,
                &edge.target,
                extended(&mapping_path, &edge.target),
            );
        }
    }
    let col = locale(locale_name)?;
    let mut entries: Vec<_> = order
        .into_iter()
        .map(|id| {
            let path = paths.remove(&id).expect("retained impact path");
            (id, path)
        })
        .collect();
    entries.sort_by(|a, b| {
        col.compare_legacy_utf16(&Data::string_units(&a.0), &Data::string_units(&b.0))
    });
    let js_strings = |items: Vec<String>| J::Array(items.into_iter().map(J::String).collect());
    Ok(obj(vec![
        ("changedSubjects", js_strings(changed)),
        (
            "affectedSubjects",
            js_strings(entries.iter().map(|(id, _)| id.clone()).collect()),
        ),
        (
            "paths",
            J::Array(
                entries
                    .into_iter()
                    .map(|(id, path)| {
                        obj(vec![
                            ("subjectId", J::String(id)),
                            ("path", js_strings(path)),
                        ])
                    })
                    .collect(),
            ),
        ),
    ]))
}

pub fn legacy_evaluation_request(
    request: LegacyWorkspaceRequest,
) -> Result<Box<RawValue>, LegacyWorkspaceError> {
    let parsed = parse(&request.input)?;
    let result = if request.operation == "parse-context" {
        parse_context_observation(&parsed)?
    } else {
        let v = value_input(&parsed)?;
        match request.operation.as_str() {
            "evaluate" => native(matches_context_with(
                &expression(field(&v, "expression")?)?,
                &context(field(&v, "context")?)?,
                &equal,
            )),
            "required" => {
                let expr = expression(field(&v, "expression")?)?;
                let mut keys = Vec::new();
                let mut seen = HashSet::new();
                visit_required(&expr, &mut |key| {
                    if seen.insert(key) {
                        keys.push(J::String(key.to_owned()));
                    }
                });
                J::Array(keys)
            }
            "inactive" => {
                let ctx = context(field(&v, "context")?)?;
                let applicability = v.get("applicability");
                let reason = if let Some(when) = applicability
                    .and_then(|a| a.get("when"))
                    .filter(|v| !v.is_null() && v != &&Value::Bool(false))
                {
                    (!matches_context_with(&expression(when)?, &ctx, &equal))
                        .then_some("when-not-satisfied")
                } else {
                    None
                };
                let reason = if reason.is_some() {
                    reason
                } else if let Some(unless) = applicability
                    .and_then(|a| a.get("unless"))
                    .filter(|v| !v.is_null() && v != &&Value::Bool(false))
                {
                    matches_context_with(&expression(unless)?, &ctx, &equal).then_some("inhibited")
                } else {
                    None
                };
                native(reason)
            }
            "selector" => native(selector(&v)?),
            "impact" => impact(&v, &request.locale)?,
            _ => return Err(error("TypeError", "Unknown legacy evaluation operation")),
        }
    };
    RawValue::from_string(raw(&result)?).map_err(|e| error("Error", &e.to_string()))
}
