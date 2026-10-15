use crate::{CaptureInputs, VerifiedReplay};
use patamaps_contracts::*;
use patamaps_core::{CheckError, CheckedGraph, EvaluationOptions, Issue, RecordDelta, admit, diff};
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet, VecDeque};

/// Rejected inputs may contain repeated identities. Retain occurrence counts
/// instead of overwriting records or pretending that this is a unique-ID diff.
fn records<T: Serialize>(before: &[T], after: &[T]) -> Result<Value, CheckError> {
    let mut maps: [BTreeMap<String, Vec<String>>; 2] = Default::default();
    for (map, values) in maps.iter_mut().zip([before, after]) {
        for value in values {
            let wire = serde_json::to_value(value).map_err(ContractError::from)?;
            let id = wire["id"].as_str().ok_or_else(|| {
                CheckError(vec![patamaps_core::Issue::error(
                    "COMPARISON_RECORD_ID",
                    "Compared record has no identity",
                    "comparison",
                )])
            })?;
            map.entry(id.into())
                .or_default()
                .push(canonical_digest(value)?);
        }
        for occurrences in map.values_mut() {
            occurrences.sort();
        }
    }
    let ids: BTreeSet<_> = maps.iter().flat_map(|m| m.keys()).collect();
    let mut added = Vec::new();
    let mut removed = Vec::new();
    let mut changed = Vec::new();
    let mut occurrences = Vec::new();
    for id in ids {
        let a = maps[0].get(id);
        let b = maps[1].get(id);
        if a != b {
            if a.is_none() {
                added.push(id);
            } else if b.is_none() {
                removed.push(id);
            } else {
                changed.push(id);
            }
            occurrences.push(json!({"id":id,"beforeDigests":a,"afterDigests":b}));
        }
    }
    Ok(json!({"added":added,"removed":removed,"changed":changed,"occurrences":occurrences}))
}

fn semantic_records(inputs: &CaptureInputs, name: &str) -> Result<Vec<Value>, CheckError> {
    let wire = serde_json::to_value(&inputs.policy.semantics).map_err(ContractError::from)?;
    Ok(wire[name].as_array().cloned().unwrap_or_default())
}

fn changed<T: Serialize>(a: &T, b: &T) -> Result<bool, CheckError> {
    Ok(canonical_bytes(a)? != canonical_bytes(b)?)
}

fn input_changes(
    before: &crate::CaptureRecord,
    after: &crate::CaptureRecord,
) -> Result<Vec<Value>, CheckError> {
    let a = serde_json::to_value(&before.inputs).map_err(ContractError::from)?;
    let b = serde_json::to_value(&after.inputs).map_err(ContractError::from)?;
    let mut names = BTreeSet::new();
    names.extend(a.as_object().expect("capture inputs").keys());
    names.extend(b.as_object().expect("capture inputs").keys());
    let mut changes = Vec::new();
    for name in names {
        // Option distinguishes an absent input from explicit null.
        let old = a.get(name);
        let new = b.get(name);
        if old.is_some() != new.is_some() || changed(&old, &new)? {
            changes.push(json!({"input":name,"beforePresent":old.is_some(),"afterPresent":new.is_some(),
            "beforeDigest":old.map(canonical_digest).transpose()?,"afterDigest":new.map(canonical_digest).transpose()?}));
        }
    }
    for (name, old, new) in [
        (
            "sources",
            serde_json::to_value(&before.sources),
            serde_json::to_value(&after.sources),
        ),
        (
            "executor",
            serde_json::to_value(&before.executor),
            serde_json::to_value(&after.executor),
        ),
    ] {
        let (old, new) = (
            old.map_err(ContractError::from)?,
            new.map_err(ContractError::from)?,
        );
        if changed(&old, &new)? {
            changes.push(json!({"input":name,"beforePresent":true,"afterPresent":true,"beforeDigest":canonical_digest(&old)?,"afterDigest":canonical_digest(&new)?}));
        }
    }
    Ok(changes)
}

fn projected<'a>(
    capture: &'a crate::CaptureRecord,
    id: &str,
) -> Option<(&'a Value, Option<&'a Value>)> {
    if !capture.inputs.projection_specs.is_empty() {
        let outcome = capture.result["projections"]
            .as_array()?
            .iter()
            .find(|outcome| outcome["specId"] == id)?;
        let projection = outcome.get("projection").filter(|v| !v.is_null())?;
        return Some((projection, outcome.get("pathTree").filter(|v| !v.is_null())));
    }
    let spec = capture.inputs.projection_spec.as_ref()?;
    if spec.id != id {
        return None;
    }
    let projection = capture.result.get("projection").filter(|v| !v.is_null())?;
    Some((
        projection,
        capture.result.get("pathTree").filter(|v| !v.is_null()),
    ))
}

fn projection_changes(
    before: &crate::CaptureRecord,
    after: &crate::CaptureRecord,
) -> Result<Vec<Value>, CheckError> {
    let ids: BTreeSet<_> = before
        .inputs
        .specs()
        .chain(after.inputs.specs())
        .map(|s| &s.id)
        .collect();
    ids.into_iter().map(|id| {
        let a = projected(before,id);
        let b = projected(after,id);
        let delta = |pointer: &str| -> Result<Option<bool>, CheckError> {
            match (a.and_then(|(p,_)|p.pointer(pointer)),b.and_then(|(p,_)|p.pointer(pointer))) { (Some(a),Some(b)) => Ok(Some(changed(a,b)?)), _ => Ok(None) }
        };
        let tree_changed = match (a.and_then(|(_,t)|t),b.and_then(|(_,t)|t)) { (Some(a),Some(b)) => Some(changed(a,b)?), _ => None };
        Ok(json!({"specId":id,"beforeKnown":a.is_some(),"afterKnown":b.is_some(),
        "beforeSemanticsKnown":a.is_some_and(|(p,_)|p.get("semantics").is_some()),"afterSemanticsKnown":b.is_some_and(|(p,_)|p.get("semantics").is_some()),
        "usedMappingsChanged":delta("/semantics/usedMappings")?,"dependenciesChanged":delta("/semantics/dependencies")?,
        "riskChanged":delta("/semantics/risk")?,"entriesChanged":delta("/entries")?,"pathTreeChanged":tree_changed,
        "before":a.map(|(p,t)|json!({"projection":p,"pathTree":t})),"after":b.map(|(p,t)|json!({"projection":p,"pathTree":t}))}))
    }).collect()
}

// These are recorded dependency edges, including in a replayed rejection.
// Traversing a claim never validates its proof or changes admission state.
fn recorded_proof_paths(inputs: &CaptureInputs, origins: &BTreeSet<String>) -> Value {
    if origins.len() > 256 {
        return json!({"status":"unavailable","scope":"recorded-proof-dependencies",
            "reason":"Origin limit exceeds 256","complete":false});
    }
    let proofs = inputs
        .policy
        .semantics
        .as_ref()
        .map(|s| s.derivations.as_slice())
        .unwrap_or(&[]);
    let mut edges: BTreeMap<&str, BTreeSet<&str>> = BTreeMap::new();
    let mut identities = BTreeSet::new();
    let mut ambiguous = BTreeSet::new();
    let mut limits = BTreeSet::new();
    let mut edge_count = 0usize;
    let mut edge_bytes = 0usize;
    'index: for proof in proofs {
        if !identities.insert(proof.id.as_str()) {
            ambiguous.insert(proof.id.as_str());
        }
        for (from, to) in proof
            .premises
            .iter()
            .map(|p| (p.mapping.as_str(), proof.id.as_str()))
            .chain(std::iter::once((
                proof.id.as_str(),
                proof.result.id.as_str(),
            )))
        {
            edge_count += 1;
            edge_bytes = edge_bytes
                .saturating_add(from.len())
                .saturating_add(to.len());
            if edge_count > 20_000 || edge_bytes > MAX_INPUT_BYTES {
                limits.insert("recorded-edge-limit");
                break 'index;
            }
            edges.entry(from).or_default().insert(to);
        }
    }
    let mut paths = Vec::new();
    let mut report_bytes = 0usize;
    let mut work = 0usize;
    // Six bytes per UTF-8 byte is a conservative JSON-escaping bound.
    let string_cost = |id: &str| id.len().saturating_mul(6).saturating_add(3);
    'origins: for origin in origins {
        let mut visited = BTreeSet::from([origin.as_str()]);
        let mut queue = VecDeque::from([(vec![origin.as_str()], string_cost(origin))]);
        while let Some((path, path_bytes)) = queue.pop_front() {
            let subject = *path.last().expect("nonempty dependency path");
            let cost = path_bytes
                .saturating_add(string_cost(origin))
                .saturating_add(string_cost(subject))
                .saturating_add(128);
            if paths.len() >= 10_000 || report_bytes.saturating_add(cost) > MAX_INPUT_BYTES {
                limits.insert("recorded-path-output-limit");
                break 'origins;
            }
            report_bytes += cost;
            paths.push(json!({"origin":origin,"subjectId":subject,"path":path}));
            let Some(targets) = edges.get(subject) else {
                continue;
            };
            for target in targets {
                work += 1;
                if work > 2_000_000 {
                    limits.insert("recorded-path-work-limit");
                    break 'origins;
                }
                if visited.contains(target) {
                    continue;
                }
                if path.len() > 64 {
                    limits.insert("recorded-path-depth-limit");
                    continue;
                }
                if visited.len() >= 10_000 {
                    limits.insert("recorded-path-visit-limit");
                    continue;
                }
                visited.insert(target);
                let mut next = path.clone();
                next.push(target);
                queue.push_back((next, path_bytes.saturating_add(string_cost(target))));
            }
        }
    }
    paths.sort_by(|a, b| {
        (a["origin"].as_str(), a["subjectId"].as_str())
            .cmp(&(b["origin"].as_str(), b["subjectId"].as_str()))
    });
    json!({"status":"available","scope":"recorded-proof-dependencies","report":{
        "complete":limits.is_empty() && ambiguous.is_empty(),"origins":origins,"paths":paths,
        "limits":limits,"ambiguousDerivations":ambiguous,
        "interpretation":"Recorded identifier dependencies only; proof validity, admission, unique causality and present authorization are not established"}})
}

fn support_subjects(inputs: &CaptureInputs) -> BTreeSet<&str> {
    inputs
        .policy
        .evidence
        .iter()
        .filter(|e| e.result == EvidenceResult::Supports)
        .flat_map(|e| e.subjects.iter().map(String::as_str))
        .collect()
}

// A rejection can retain duplicate graph identities. Keep the ordinary unique-ID
// diff contract, but do not lose the whole diagnostic report when it refuses.
fn graph_changes(
    a: &CaptureInputs,
    b: &CaptureInputs,
) -> Result<(Vec<RecordDelta>, Value, &'static str), CheckError> {
    let inventory = json!({
        "entity":records(&a.graph.entities,&b.graph.entities)?,
        "mapping":records(&a.graph.mappings,&b.graph.mappings)?,
        "authority":records(&a.graph.authorities,&b.graph.authorities)?
    });
    match diff(&a.graph, &b.graph) {
        Ok(changes) => Ok((changes, inventory, "unique-ids")),
        Err(error) if error.0.iter().all(|i| i.code == "DUPLICATE_DIFF_ID") => {
            let mut changes = Vec::new();
            for kind in ["entity", "mapping", "authority"] {
                for row in inventory[kind]["occurrences"]
                    .as_array()
                    .expect("record occurrences")
                {
                    let digest = |key: &str| {
                        row[key]
                            .as_array()
                            .filter(|v| v.len() == 1)
                            .and_then(|v| v[0].as_str())
                            .map(str::to_owned)
                    };
                    changes.push(RecordDelta {
                        kind,
                        id: row["id"].as_str().expect("record id").into(),
                        change: if row["beforeDigests"].is_null() {
                            "added"
                        } else if row["afterDigests"].is_null() {
                            "removed"
                        } else {
                            "modified"
                        },
                        before_digest: digest("beforeDigests"),
                        after_digest: digest("afterDigests"),
                    });
                }
            }
            let (mut old, mut new) = (a.graph.clone(), b.graph.clone());
            old.entities.clear();
            old.mappings.clear();
            old.authorities.clear();
            new.entities.clear();
            new.mappings.clear();
            new.authorities.clear();
            changes.extend(diff(&old, &new)?);
            changes.sort_by(|a, b| (&a.kind, &a.id).cmp(&(&b.kind, &b.id)));
            Ok((changes, inventory, "occurrence-aware"))
        }
        Err(error) => Err(error),
    }
}

fn issue_counts(values: &[Value]) -> Result<BTreeMap<String, (Value, usize)>, CheckError> {
    let mut counts = BTreeMap::new();
    for value in values {
        let entry = counts
            .entry(canonical_digest(value)?)
            .or_insert_with(|| (value.clone(), 0));
        entry.1 += 1;
    }
    Ok(counts)
}

fn issue_delta(a: Option<&[Value]>, b: Option<&[Value]>) -> Result<Value, CheckError> {
    let (Some(old), Some(new)) = (a, b) else {
        return Ok(
            json!({"beforeKnown":a.is_some(),"afterKnown":b.is_some(),"introduced":null,"resolved":null,
            "reason":"A stage was not recorded, requested or evaluated; absence is not resolution"}),
        );
    };
    let (old, new) = (issue_counts(old)?, issue_counts(new)?);
    let ids: BTreeSet<_> = old.keys().chain(new.keys()).collect();
    let (mut introduced, mut resolved) = (Vec::new(), Vec::new());
    for id in ids {
        let (a, b) = (
            old.get(id).map_or(0, |v| v.1),
            new.get(id).map_or(0, |v| v.1),
        );
        if b > a {
            introduced.push(json!({"issue":new[id].0,"count":b-a}));
        }
        if a > b {
            resolved.push(json!({"issue":old[id].0,"count":a-b}));
        }
    }
    Ok(json!({"beforeKnown":true,"afterKnown":true,"introduced":introduced,"resolved":resolved}))
}

type IssueStages = BTreeMap<(&'static str, Option<String>), Option<Vec<Value>>>;

fn issue_stages(capture: &crate::CaptureRecord) -> Result<IssueStages, CheckError> {
    let mut stages = IssueStages::new();
    let top = capture.result["issues"]
        .as_array()
        .expect("verified evaluation issues");
    let collection = !capture.inputs.projection_specs.is_empty();
    let compilation = if collection && capture.result["compilationStatus"] == "viable" {
        let mut remaining = issue_counts(top)?;
        for outcome in capture.result["projections"]
            .as_array()
            .expect("verified projection outcomes")
        {
            for issue in outcome["issues"]
                .as_array()
                .expect("verified projection issues")
            {
                remaining
                    .get_mut(&canonical_digest(issue)?)
                    .expect("aggregate includes outcome issues")
                    .1 -= 1;
            }
        }
        Some(
            remaining
                .into_values()
                .flat_map(|(v, n)| std::iter::repeat_n(v, n))
                .collect(),
        )
    } else if collection || capture.result["status"] == "viable" {
        Some(top.clone())
    } else {
        None
    };
    stages.insert(("compilation", None), compilation);
    for spec in capture.inputs.specs() {
        let outcome = if collection {
            capture.result["projections"]
                .as_array()
                .and_then(|values| values.iter().find(|v| v["specId"] == spec.id))
        } else {
            None
        };
        let projected = outcome
            .is_some_and(|v| v["status"] == "projected" || v["status"] == "path-tree-rejected")
            || (!collection && capture.result["status"] == "viable");
        let projection = if projected {
            Some(vec![])
        } else {
            outcome
                .filter(|v| v["status"] == "rejected")
                .and_then(|v| v["issues"].as_array().cloned())
        };
        stages.insert(("projection", Some(spec.id.clone())), projection);
        let tree = if spec.path_tree.is_none() {
            None
        } else if outcome.is_some_and(|v| v["status"] == "path-tree-rejected") {
            outcome.and_then(|v| v["issues"].as_array().cloned())
        } else if projected {
            Some(vec![])
        } else {
            None
        };
        stages.insert(("path-tree", Some(spec.id.clone())), tree);
    }
    Ok(stages)
}

fn stage_deltas(
    a: &crate::CaptureRecord,
    b: &crate::CaptureRecord,
) -> Result<Vec<Value>, CheckError> {
    let (a, b) = (issue_stages(a)?, issue_stages(b)?);
    let keys: BTreeSet<_> = a.keys().chain(b.keys()).collect();
    keys.into_iter().map(|key|Ok(json!({"stage":key.0,"specId":key.1,
        "delta":issue_delta(a.get(key).and_then(|v|v.as_deref()),b.get(key).and_then(|v|v.as_deref()))?}))).collect()
}

// Declarations have no stable record identity. A digest multiset finds changed
// occurrences without depending on order or losing identical repetitions.
fn changed_values(a: &[Value], b: &[Value]) -> Result<Vec<Value>, CheckError> {
    let (old, new) = (issue_counts(a)?, issue_counts(b)?);
    let keys: BTreeSet<_> = old.keys().chain(new.keys()).collect();
    Ok(keys
        .into_iter()
        .filter(|key| old.get(*key).map(|v| v.1) != new.get(*key).map(|v| v.1))
        .map(|key| {
            old.get(key)
                .or_else(|| new.get(key))
                .expect("changed record")
                .0
                .clone()
        })
        .collect())
}

fn references(value: &Value, known: &BTreeSet<&str>, subjects: &mut BTreeSet<String>) {
    match value {
        Value::String(id) if known.contains(id.as_str()) => {
            subjects.insert(id.clone());
        }
        Value::Array(values) => {
            for value in values {
                references(value, known, subjects);
            }
        }
        Value::Object(object) => {
            for (key, value) in object {
                if key == "subjects" {
                    subjects.extend(
                        value
                            .as_array()
                            .into_iter()
                            .flatten()
                            .filter_map(Value::as_str)
                            .map(str::to_owned),
                    );
                }
                references(value, known, subjects);
            }
        }
        _ => {}
    }
}

fn diagnostic_origins(
    a: &CaptureInputs,
    b: &CaptureInputs,
    changes: &[RecordDelta],
    explicit: &[String],
) -> Result<(BTreeMap<String, BTreeSet<&'static str>>, bool), CheckError> {
    let mut reasons: BTreeMap<String, BTreeSet<&'static str>> = BTreeMap::new();
    let mut complete = true;
    let mut add = |id: String, reason| {
        if reasons.contains_key(&id) || reasons.len() < 256 {
            reasons.entry(id).or_default().insert(reason);
        } else {
            complete = false;
        }
    };
    for id in explicit {
        add(id.clone(), "explicit-diagnostic");
    }
    for change in changes.iter().filter(|d| d.kind != "document") {
        add(change.id.clone(), "graph-record");
    }
    let known: BTreeSet<_> = [a, b]
        .into_iter()
        .flat_map(|i| {
            i.graph
                .entities
                .iter()
                .map(|v| v.id.as_str())
                .chain(i.graph.mappings.iter().map(|v| v.id.as_str()))
                .chain(i.graph.authorities.iter().map(|v| v.id.as_str()))
        })
        .collect();
    let (old, new) = (
        serde_json::to_value(&a.policy).map_err(ContractError::from)?,
        serde_json::to_value(&b.policy).map_err(ContractError::from)?,
    );
    let mut selector_changed = false;
    for field in ["mappings", "constraints", "evidence", "waivers"] {
        for record in changed_values(
            old[field].as_array().map(Vec::as_slice).unwrap_or(&[]),
            new[field].as_array().map(Vec::as_slice).unwrap_or(&[]),
        )? {
            let mut subjects = BTreeSet::new();
            references(&record, &known, &mut subjects);
            for id in subjects {
                add(id, "policy-record-reference");
            }
            if field == "mappings" && record.get("select").is_some() {
                selector_changed = true;
            }
        }
    }
    if selector_changed {
        for input in [a, b] {
            for m in &input.graph.mappings {
                add(m.id.clone(), "policy-selector-potential");
            }
        }
    }
    let mut semantic_selector_changed = false;
    for field in [
        "derivations",
        "assessments",
        "uncertaintyRequirements",
        "riskBudgets",
    ] {
        for record in changed_values(
            old["semantics"][field]
                .as_array()
                .map(Vec::as_slice)
                .unwrap_or(&[]),
            new["semantics"][field]
                .as_array()
                .map(Vec::as_slice)
                .unwrap_or(&[]),
        )? {
            if field == "derivations" {
                if let Some(id) = record["id"].as_str() {
                    add(id.into(), "recorded-derivation");
                }
            } else {
                let mut subjects = BTreeSet::new();
                references(&record, &known, &mut subjects);
                for id in subjects {
                    add(id, "semantic-policy-reference");
                }
                semantic_selector_changed |= record.get("select").is_some();
            }
        }
    }
    semantic_selector_changed |= changed(
        &old["semantics"]["interpretation"],
        &new["semantics"]["interpretation"],
    )? || changed(
        &old["semantics"]["derivationLimits"],
        &new["semantics"]["derivationLimits"],
    )?;
    if semantic_selector_changed {
        for input in [a, b] {
            for mapping in &input.graph.mappings {
                add(mapping.id.clone(), "semantic-selector-potential");
            }
        }
    }
    if changed(&a.context, &b.context)?
        || a.evaluated_at != b.evaluated_at
        || changed(&a.packs, &b.packs)?
    {
        for input in [a, b] {
            for m in &input.graph.mappings {
                add(m.id.clone(), "evaluation-input-potential");
            }
        }
    }
    let spec_values = |input: &CaptureInputs| {
        input
            .specs()
            .map(|v| serde_json::to_value(v).map_err(ContractError::from))
            .collect::<Result<Vec<_>, _>>()
    };
    let changed_specs = changed_values(&spec_values(a)?, &spec_values(b)?)?;
    let changed_ids: BTreeSet<_> = changed_specs
        .iter()
        .filter_map(|v| v["id"].as_str())
        .collect();
    let mut selection_work = 0usize;
    let mut work_exhausted = false;
    'selection: for input in [a, b] {
        for spec in input
            .specs()
            .filter(|s| changed_ids.contains(s.id.as_str()))
        {
            let selected_ids = spec
                .select
                .ids
                .as_ref()
                .map(|v| v.iter().collect::<BTreeSet<_>>());
            let selected_kinds = spec
                .select
                .kinds
                .as_ref()
                .map(|v| v.iter().collect::<BTreeSet<_>>());
            for entity in &input.graph.entities {
                selection_work += 1;
                if selection_work > 2_000_000 {
                    work_exhausted = true;
                    break 'selection;
                }
                if selected_ids
                    .as_ref()
                    .is_none_or(|ids| ids.contains(&entity.id))
                    && selected_kinds
                        .as_ref()
                        .is_none_or(|kinds| kinds.contains(&entity.kind))
                {
                    add(entity.id.clone(), "consumer-selection-potential");
                }
            }
        }
    }
    Ok((reasons, complete && !work_exhausted))
}

fn admitted_paths(inputs: &CaptureInputs, origins: &[String]) -> Result<Value, CheckError> {
    let graph = match CheckedGraph::check(inputs.graph.clone(), inputs.packs.clone()) {
        Ok(graph) => graph,
        Err(error) => {
            return Ok(
                json!({"status":"unavailable","scope":"admitted-authored-graph","issues":error.0}),
            );
        }
    };
    let generation = match admit(
        &graph,
        &inputs.policy,
        EvaluationOptions {
            context: inputs.context.clone(),
            evaluated_at: inputs.evaluated_at.clone(),
        },
    ) {
        Ok(generation) => generation,
        Err(error) => {
            return Ok(
                json!({"status":"unavailable","scope":"admitted-authored-graph","issues":error.0}),
            );
        }
    };
    match patamaps_core::impact_admitted(&generation, origins, 64) {
        Ok(report) => Ok(
            json!({"status":"available","scope":"admitted-authored-graph","recomputed":true,"generation":generation.record().digest,"report":report}),
        ),
        Err(error) => {
            Ok(json!({"status":"unavailable","scope":"admitted-authored-graph","issues":error.0}))
        }
    }
}

/// Compare verified inputs/results; unavailable deltas remain explicit nulls.
pub fn compare(
    before: &VerifiedReplay<'_>,
    after: &VerifiedReplay<'_>,
) -> Result<Value, CheckError> {
    compare_with_origins(before, after, &[])
}

/// Add diagnostic subjects without altering either captured input or result.
/// Potential policy/consumer influence is not a unique causal attribution.
pub fn compare_with_origins(
    before: &VerifiedReplay<'_>,
    after: &VerifiedReplay<'_>,
    explicit_origins: &[String],
) -> Result<Value, CheckError> {
    if explicit_origins.len() > 256
        || explicit_origins
            .iter()
            .any(|id| !patamaps_core::valid_identifier(id))
    {
        return Err(CheckError(vec![Issue::error(
            "COMPARISON_ORIGIN_LIMIT",
            "Diagnostic origins require at most 256 valid subject identifiers",
            "comparison",
        )]));
    }
    let a = before.record();
    let b = after.record();
    let (changes, graph_records, graph_identity_mode) = graph_changes(&a.inputs, &b.inputs)?;
    let projection_delta = match (
        a.result.get("projection").filter(|v| !v.is_null()),
        b.result.get("projection").filter(|v| !v.is_null()),
    ) {
        (Some(a), Some(b)) => Some(canonical_bytes(a)? != canonical_bytes(b)?),
        _ => None,
    };
    let tree_delta = match (
        a.result.get("pathTree").filter(|v| !v.is_null()),
        b.result.get("pathTree").filter(|v| !v.is_null()),
    ) {
        (Some(a), Some(b)) => Some(canonical_bytes(a)? != canonical_bytes(b)?),
        _ => None,
    };
    let changed_origins: Vec<_> = changes
        .iter()
        .map(|d| json!({"kind":d.kind,"id":d.id,"change":d.change}))
        .collect();
    let risk_delta = match (
        a.result.pointer("/projection/semantics/risk"),
        b.result.pointer("/projection/semantics/risk"),
    ) {
        (Some(a), Some(b)) if a["status"] == "evaluated" && b["status"] == "evaluated" => {
            let before: SafeInteger =
                serde_json::from_value(a["totalCost"].clone()).map_err(ContractError::from)?;
            let after: SafeInteger =
                serde_json::from_value(b["totalCost"].clone()).map_err(ContractError::from)?;
            Some(
                json!({"status":"available","before":a,"after":b,"totalCostChange":after.get() as i64-before.get() as i64}),
            )
        }
        _ => None,
    };
    let (origin_reasons, origins_complete) =
        diagnostic_origins(&a.inputs, &b.inputs, &changes, explicit_origins)?;
    let origins: Vec<_> = origin_reasons.keys().cloned().collect();
    let source_maps: Vec<BTreeMap<_, _>> = [&a.sources, &b.sources]
        .iter()
        .map(|sources| sources.iter().map(|s| (s.id.clone(), s)).collect())
        .collect();
    let source_ids: BTreeSet<_> = source_maps.iter().flat_map(|m| m.keys()).collect();
    let mut source_deltas = Vec::new();
    for id in source_ids {
        let before = source_maps[0].get(id);
        let after = source_maps[1].get(id);
        let before_receipt = before.map(canonical_digest).transpose()?;
        let after_receipt = after.map(canonical_digest).transpose()?;
        if before_receipt != after_receipt {
            source_deltas.push(json!({"id":id,"change":if before.is_none(){"added"}else if after.is_none(){"removed"}else{"modified"},
            "beforeDigest":before.map(|s|&s.digest),"afterDigest":after.map(|s|&s.digest),
            "byteChange":before.map(|s|&s.digest)!=after.map(|s|&s.digest),
            "beforeReceiptDigest":before_receipt,"afterReceiptDigest":after_receipt,"graphExtractionRecomputed":false}));
        }
    }
    let declared_paths = |inputs: &CaptureInputs| -> Result<Value, CheckError> {
        if !origins_complete {
            return Ok(
                json!({"status":"unavailable","scope":"declared-graph","reason":"Diagnostic origin count or selection work limit exceeded","complete":false}),
            );
        }
        match CheckedGraph::check(inputs.graph.clone(), inputs.packs.clone()) {
            Ok(g) => match patamaps_core::impact(&g, &origins, 64) {
                Ok(report) => {
                    Ok(json!({"status":"available","scope":"declared-graph","report":report}))
                }
                Err(error) => Ok(json!({"status":"unavailable","issues":error.0})),
            },
            Err(error) => Ok(json!({"status":"unavailable","issues":error.0})),
        }
    };
    let mut semantic = serde_json::Map::new();
    for name in [
        "derivations",
        "assessments",
        "uncertaintyRequirements",
        "riskBudgets",
    ] {
        semantic.insert(
            name.into(),
            records(
                &semantic_records(&a.inputs, name)?,
                &semantic_records(&b.inputs, name)?,
            )?,
        );
    }
    let proof_origins: BTreeSet<String> = origins
        .iter()
        .cloned()
        .chain(
            ["added", "removed", "changed"]
                .into_iter()
                .flat_map(|kind| {
                    semantic["derivations"][kind]
                        .as_array()
                        .into_iter()
                        .flatten()
                        .filter_map(Value::as_str)
                        .map(str::to_owned)
                }),
        )
        .collect();
    let support_before = support_subjects(&a.inputs);
    let support_after = support_subjects(&b.inputs);
    let policy_records = json!({
        "constraints":records(&a.inputs.policy.constraints,&b.inputs.policy.constraints)?,
        "evidence":records(&a.inputs.policy.evidence,&b.inputs.policy.evidence)?,
        "waivers":records(a.inputs.policy.waivers.as_deref().unwrap_or(&[]),b.inputs.policy.waivers.as_deref().unwrap_or(&[]))?
    });
    semantic.insert("sourceReceipts".into(), records(&a.sources, &b.sources)?);
    semantic.insert(
        "projections".into(),
        serde_json::to_value(projection_changes(a, b)?).map_err(ContractError::from)?,
    );
    let mapping_states = match (
        a.result.pointer("/generation/activeMappings"),
        b.result.pointer("/generation/activeMappings"),
    ) {
        (Some(Value::Array(a)), Some(Value::Array(b))) => {
            json!({"beforeKnown":true,"afterKnown":true,
            "activated":b.iter().filter(|id|!a.contains(id)).collect::<Vec<_>>(),"deactivated":a.iter().filter(|id|!b.contains(id)).collect::<Vec<_>>()})
        }
        (a, b) => {
            json!({"beforeKnown":a.is_some(),"afterKnown":b.is_some(),"activated":null,"deactivated":null})
        }
    };
    let checked_paths = |inputs: &CaptureInputs| -> Result<Value, CheckError> {
        if origins_complete {
            admitted_paths(inputs, &origins)
        } else {
            Ok(
                json!({"status":"unavailable","scope":"admitted-authored-graph","reason":"Diagnostic origin count or selection work limit exceeded","complete":false}),
            )
        }
    };
    let proof_paths = |inputs: &CaptureInputs| {
        if origins_complete {
            recorded_proof_paths(inputs, &proof_origins)
        } else {
            json!({"status":"unavailable","scope":"recorded-proof-dependencies","reason":"Diagnostic origin count or selection work limit exceeded","complete":false})
        }
    };
    let mut report = json!({"before":a.digest,"after":b.digest,"changes":changes,"changedOrigins":changed_origins,
        "statusChanged":a.result["status"] != b.result["status"],"projectionChanged":projection_delta,"pathTreeChanged":tree_delta,
        "policyChanged":canonical_digest(&a.inputs.policy)? != canonical_digest(&b.inputs.policy)?,
        "contextChanged":canonical_bytes(&a.inputs.context)? != canonical_bytes(&b.inputs.context)?,
        "packChanged":canonical_bytes(&a.inputs.packs)? != canonical_bytes(&b.inputs.packs)?,
        "riskDelta":risk_delta,"missingSourcesBefore":before.missing_sources(),"missingSourcesAfter":after.missing_sources(),
        "declaredPathsBefore":declared_paths(&a.inputs)?,"declaredPathsAfter":declared_paths(&b.inputs)?,
        "recordedProofPathsBefore":proof_paths(&a.inputs),
        "recordedProofPathsAfter":proof_paths(&b.inputs),
        "policyRecords":policy_records,
        "evidenceSupport":{"recordedSupportLost":support_before.difference(&support_after).collect::<Vec<_>>(),
            "recordedSupportGained":support_after.difference(&support_before).collect::<Vec<_>>(),
            "interpretation":"Recorded support presence only; evidence validity and scientific truth are not established"},
        "sourceDeltas":source_deltas,
        "issueSubjectsBefore":a.result.get("issues"),"issueSubjectsAfter":b.result.get("issues"),
        "inputChanges":input_changes(a,b)?,"semantic":semantic,"mappingStates":mapping_states,
        "packChanges":records(&a.inputs.packs,&b.inputs.packs)?,"projectionSpecs":records(&a.inputs.specs().collect::<Vec<_>>(),&b.inputs.specs().collect::<Vec<_>>())?,
        "evaluatedAtChanged":a.inputs.evaluated_at!=b.inputs.evaluated_at,"executorChanged":a.executor!=b.executor,
        "generationChanged":match(a.result.get("generation"),b.result.get("generation")){(Some(a),Some(b))=>Some(changed(a,b)?),_=>None},
        "sourceInspectionBefore":{"capturedBytesVerified":a.sources.iter().filter(|s|s.content.is_some()).map(|s|&s.id).collect::<Vec<_>>(),"missingBytes":before.missing_sources(),"currentSourceRediscovery":{"status":"unavailable","reason":"No current source rediscovery was requested or executed"}},
        "sourceInspectionAfter":{"capturedBytesVerified":b.sources.iter().filter(|s|s.content.is_some()).map(|s|&s.id).collect::<Vec<_>>(),"missingBytes":after.missing_sources(),"currentSourceRediscovery":{"status":"unavailable","reason":"No current source rediscovery was requested or executed"}},
        "causalClaim":"Observed input differences and findings; unique causal responsibility is not established"});
    let diagnostics = json!({
        "graphRecords":graph_records,"graphIdentityMode":graph_identity_mode,
        "diagnosticOrigins":{"subjects":origins,"reasons":origin_reasons,"complete":origins_complete,"withinPathOriginLimit":origins_complete,
            "interpretation":"Diagnostic subjects and conservative potential influence; graph document metadata alone does not seed paths, and unique causal responsibility is not established"},
        "issueDelta":issue_delta(a.result["issues"].as_array().map(Vec::as_slice),b.result["issues"].as_array().map(Vec::as_slice))?,
        "issueStages":stage_deltas(a,b)?,
        "admittedPathsBefore":checked_paths(&a.inputs)?,"admittedPathsAfter":checked_paths(&b.inputs)?
    });
    if let Value::Object(fields) = diagnostics {
        report
            .as_object_mut()
            .expect("comparison report")
            .extend(fields);
    }
    Ok(report)
}
