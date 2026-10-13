use patamaps_contracts::*;
use patamaps_core::{
    CancellationToken, CheckError, CheckedGraph, EvaluationOptions, Issue, WorkControl,
    admit_controlled,
};
use patamaps_governance::{GovernanceAction, GovernanceRequirement, GovernanceScope};
use patamaps_projection::{CaptureRecord, capture, compare, replay};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    time::{Duration, Instant},
};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "kebab-case", deny_unknown_fields)]
pub enum RepairOperation {
    RestoreMapping {
        mapping: Mapping,
    },
    SelectTarget {
        #[serde(rename = "mappingIndex")]
        mapping_index: SafeInteger,
        #[serde(rename = "expectedDigest")]
        expected_digest: String,
        target: String,
    },
    RemoveDuplicate {
        #[serde(rename = "mappingIndex")]
        mapping_index: SafeInteger,
        #[serde(rename = "expectedDigest")]
        expected_digest: String,
        #[serde(rename = "keepIndex")]
        keep_index: SafeInteger,
        #[serde(rename = "keepDigest")]
        keep_digest: String,
    },
    SupplyDeclaration {
        declaration: Declaration,
    },
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RepairEdit {
    pub id: String,
    pub semantic_cost: SafeInteger,
    pub operation: RepairOperation,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RepairBounds {
    pub maximum_candidates: SafeInteger,
    pub maximum_edits: SafeInteger,
    pub maximum_derivation_depth: SafeInteger,
    pub maximum_elapsed_milliseconds: SafeInteger,
    pub maximum_work_units: SafeInteger,
}
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum RepairType {
    #[serde(rename = "repair-request")]
    Draft1,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RepairRequest {
    pub schema_version: ProtocolVersion,
    pub document_type: RepairType,
    pub baseline: CaptureRecord,
    pub consumer: String,
    pub allowed_facts: Vec<GovernanceScope>,
    pub protected_facts: Vec<GovernanceScope>,
    pub edits: Vec<RepairEdit>,
    pub bounds: RepairBounds,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RepairReport {
    pub schema_version: ProtocolVersion,
    pub document_type: &'static str,
    pub id: String,
    pub digest: String,
    pub request: RepairRequest,
    pub status: &'static str,
    pub applied: bool,
    pub space: &'static str,
    pub attempts: Vec<Value>,
    pub proposals: Vec<String>,
    pub coverage: Value,
    pub minimality: Value,
}
fn fail<T>(code: &str, message: &str) -> Result<T, CheckError> {
    Err(CheckError(vec![Issue::error(code, message, "repair")]))
}
fn stopping(e: &CheckError) -> bool {
    e.0.iter().any(|i| i.code.starts_with("WORK_"))
}
fn matches(scope: &GovernanceScope, subject: &str, fact: &str, protect: bool) -> bool {
    (scope.subject == "*" || scope.subject == subject)
        && (scope.fact == "*"
            || scope.fact == fact
            || (scope.fact == "mapping.record" && fact.starts_with("mapping."))
            || (protect && fact == "mapping.record" && scope.fact.starts_with("mapping.")))
}
fn permit(request: &RepairRequest, subject: &str, fact: &str) -> Result<(), CheckError> {
    if request
        .protected_facts
        .iter()
        .any(|s| matches(s, subject, fact, true))
    {
        return fail(
            "REPAIR_PROTECTED_FACT",
            "Supplied edit touches a protected fact",
        );
    }
    if !request
        .allowed_facts
        .iter()
        .any(|s| matches(s, subject, fact, false))
    {
        return fail(
            "REPAIR_SCOPE_DENIED",
            "Supplied edit is outside the proposal boundary",
        );
    }
    Ok(())
}
fn index(value: SafeInteger, length: usize) -> Result<usize, CheckError> {
    usize::try_from(value.get())
        .ok()
        .filter(|n| *n < length)
        .ok_or_else(|| {
            CheckError(vec![Issue::error(
                "REPAIR_STALE_MAPPING",
                "Index is outside captured mapping records",
                "repair",
            )])
        })
}
fn claim(occupied: &mut BTreeSet<String>, key: String) -> Result<(), CheckError> {
    if !occupied.insert(key) {
        return fail(
            "REPAIR_CONFLICTING_EDITS",
            "Supplied edits change the same captured record",
        );
    }
    Ok(())
}
fn select(graph: &GraphDocument, mapping: &Mapping, selector: &MappingSelector) -> bool {
    selector
        .ids
        .as_ref()
        .is_none_or(|v| v.contains(&mapping.id))
        && selector
            .relations
            .as_ref()
            .is_none_or(|v| v.contains(&mapping.relation))
        && selector
            .provenance_statuses
            .as_ref()
            .is_none_or(|v| v.contains(&mapping.provenance.status))
        && [
            (&selector.source_kinds, &mapping.sources),
            (&selector.target_kinds, &mapping.targets),
        ]
        .into_iter()
        .all(|(kinds, ids)| {
            kinds.as_ref().is_none_or(|v| {
                ids.iter().any(|id| {
                    graph
                        .entities
                        .iter()
                        .any(|e| &e.id == id && v.contains(&e.kind))
                })
            })
        })
}
fn attempt(
    request: &RepairRequest,
    selected: &[usize],
    control: &WorkControl,
) -> Result<Value, CheckError> {
    let base = &request.baseline;
    let original = &base.inputs.graph;
    let mut inputs = base.inputs.clone();
    let (mut occupied, mut removed, mut keepers, mut targets, mut restored, mut declarations) = (
        BTreeSet::new(),
        BTreeSet::new(),
        Vec::new(),
        BTreeMap::new(),
        Vec::new(),
        Vec::new(),
    );
    let mut requirements = vec![GovernanceRequirement {
        action: GovernanceAction::Activate,
        subject: request.consumer.clone(),
        fact: "activation".into(),
    }];
    let mut cost = SafeInteger::new(0).expect("zero is safe");
    let add = |requirements: &mut Vec<GovernanceRequirement>, action, subject: &str, fact: &str| {
        requirements.push(GovernanceRequirement {
            action,
            subject: subject.into(),
            fact: fact.into(),
        })
    };
    for i in selected {
        control.poll()?;
        let edit = &request.edits[*i];
        let Some(sum) = cost.checked_add(edit.semantic_cost) else {
            return fail(
                "REPAIR_COST_OVERFLOW",
                "Summed ordinal cost exceeds the safe-integer contract",
            );
        };
        cost = sum;
        match &edit.operation {
            RepairOperation::SupplyDeclaration { declaration } => {
                let Some(id) = &declaration.mapping else {
                    return fail(
                        "REPAIR_UNSUPPORTED_DECLARATION",
                        "Only an explicit mapping declaration may be supplied",
                    );
                };
                if declaration.select.is_some() || declaration.applicability.is_some() {
                    return fail(
                        "REPAIR_UNSUPPORTED_DECLARATION",
                        "Repair cannot invent selectors or applicability",
                    );
                }
                let mapping = original.mappings.iter().find(|m| &m.id == id).or_else(|| {
                    selected.iter().find_map(|i| {
                        if let RepairOperation::RestoreMapping { mapping } =
                            &request.edits[*i].operation
                        {
                            (&mapping.id == id).then_some(mapping)
                        } else {
                            None
                        }
                    })
                });
                let Some(mapping) = mapping else {
                    return fail(
                        "REPAIR_UNKNOWN_MAPPING",
                        "Declaration must name a captured or explicitly restored mapping",
                    );
                };
                if base.inputs.policy.mappings.iter().any(|d| {
                    d.mapping.as_ref() == Some(id)
                        || d.select
                            .as_ref()
                            .is_some_and(|s| select(original, mapping, s))
                }) {
                    return fail(
                        "REPAIR_DECLARATION_EXISTS",
                        "Replacement or weakening of an effective declaration is forbidden",
                    );
                }
                permit(request, &inputs.policy.id, "policy.mappings")?;
                claim(&mut occupied, format!("declaration:{id}"))?;
                add(
                    &mut requirements,
                    GovernanceAction::ChangePolicy,
                    &inputs.policy.id,
                    "policy.mappings",
                );
                add(
                    &mut requirements,
                    GovernanceAction::RelaxPolicy,
                    &inputs.policy.id,
                    "policy.mappings",
                );
                declarations.push(declaration.clone());
            }
            RepairOperation::RestoreMapping { mapping } => {
                if original.mappings.iter().any(|m| m.id == mapping.id) {
                    return fail(
                        "REPAIR_MAPPING_EXISTS",
                        "Only an explicitly supplied absent mapping can be restored",
                    );
                }
                if mapping.provenance.status != ProvenanceStatus::Declared
                    || mapping
                        .attributes
                        .as_ref()
                        .is_some_and(|a| a.contains_key(DERIVATION_ATTRIBUTE))
                {
                    return fail(
                        "REPAIR_PROOF_INVENTION",
                        "Repair cannot invent an inferred assertion or derivation proof",
                    );
                }
                permit(request, &mapping.id, "mapping.record")?;
                permit(request, &inputs.policy.id, "policy.graph")?;
                claim(&mut occupied, format!("restore:{}", mapping.id))?;
                add(
                    &mut requirements,
                    GovernanceAction::ChangeGraph,
                    &mapping.id,
                    "mapping.record",
                );
                restored.push(mapping.clone());
            }
            RepairOperation::SelectTarget {
                mapping_index,
                expected_digest,
                target,
            } => {
                let n = index(*mapping_index, original.mappings.len())?;
                let mapping = &original.mappings[n];
                if canonical_digest(mapping)? != *expected_digest {
                    return fail(
                        "REPAIR_STALE_MAPPING",
                        "Index/digest must bind exact captured mapping",
                    );
                }
                if mapping.sources.len() != 1 || mapping.targets.len() != 1 {
                    return fail(
                        "REPAIR_UNSUPPORTED_ARITY",
                        "Target selection requires an existing binary mapping",
                    );
                }
                if mapping.targets[0] == *target
                    || !original.entities.iter().any(|e| e.id == *target)
                {
                    return fail(
                        "REPAIR_INVALID_TARGET",
                        "Target must be a different explicitly captured entity",
                    );
                }
                if mapping
                    .attributes
                    .as_ref()
                    .is_some_and(|a| a.contains_key(DERIVATION_ATTRIBUTE))
                {
                    return fail(
                        "REPAIR_PROOF_INVENTION",
                        "Inferred mappings cannot be retargeted",
                    );
                }
                permit(request, &mapping.id, "mapping.targets")?;
                permit(request, &inputs.policy.id, "policy.graph")?;
                claim(&mut occupied, format!("mapping:{n}"))?;
                add(
                    &mut requirements,
                    GovernanceAction::RebindImplementation,
                    &mapping.id,
                    "mapping.targets",
                );
                targets.insert(n, target.clone());
            }
            RepairOperation::RemoveDuplicate {
                mapping_index,
                expected_digest,
                keep_index,
                keep_digest,
            } => {
                let n = index(*mapping_index, original.mappings.len())?;
                let k = index(*keep_index, original.mappings.len())?;
                let (m, kept) = (&original.mappings[n], &original.mappings[k]);
                if n == k
                    || canonical_digest(m)? != *expected_digest
                    || canonical_digest(kept)? != *keep_digest
                {
                    return fail(
                        "REPAIR_STALE_MAPPING",
                        "Exact removed and retained captured records are required",
                    );
                }
                let (mut a, mut b) = (
                    serde_json::to_value(m).map_err(ContractError::from)?,
                    serde_json::to_value(kept).map_err(ContractError::from)?,
                );
                a.as_object_mut().unwrap().remove("id");
                b.as_object_mut().unwrap().remove("id");
                if canonical_bytes(&a)? != canonical_bytes(&b)? {
                    return fail(
                        "REPAIR_NOT_DUPLICATE",
                        "Records must be identical apart from identity",
                    );
                }
                permit(request, &m.id, "mapping.record")?;
                permit(request, &inputs.policy.id, "policy.graph")?;
                claim(&mut occupied, format!("mapping:{n}"))?;
                add(
                    &mut requirements,
                    GovernanceAction::ChangeGraph,
                    &m.id,
                    "mapping.record",
                );
                removed.insert(n);
                keepers.push(k);
            }
        }
    }
    if keepers
        .iter()
        .any(|k| occupied.contains(&format!("mapping:{k}")))
    {
        return fail(
            "REPAIR_KEEPER_CHANGED",
            "Retained duplicate cannot change in the same subset",
        );
    }
    inputs.graph.mappings = original
        .mappings
        .iter()
        .enumerate()
        .filter(|(n, _)| !removed.contains(n))
        .map(|(n, m)| {
            let mut m = m.clone();
            if let Some(target) = targets.get(&n) {
                m.targets = vec![target.clone()];
            }
            m
        })
        .chain(restored)
        .collect();
    inputs.policy.mappings.extend(declarations);
    let (before, after) = (
        canonical_digest(original)?,
        canonical_digest(&inputs.graph)?,
    );
    let old_binding = inputs.policy.graph.clone();
    if before != after {
        inputs.policy.graph.digest = Some(after.clone());
    }
    // Cooperative polls occur in graph indexing, cycle analysis, policy mapping
    // coverage and before/after the remaining bounded synchronous stages.
    match CheckedGraph::check_controlled(inputs.graph.clone(), inputs.packs.clone(), control)
        .and_then(|g| {
            admit_controlled(
                &g,
                &inputs.policy,
                EvaluationOptions {
                    context: inputs.context.clone(),
                    evaluated_at: inputs.evaluated_at.clone(),
                },
                control,
            )
            .map(|_| ())
        }) {
        Err(e) if stopping(&e) => return Err(e),
        _ => (),
    };
    control.poll()?;
    let candidate = capture(inputs, base.sources.clone())?;
    control.poll()?;
    let viable = candidate.result["status"] == "viable";
    let comparison = match compare(&replay(base)?, &replay(&candidate)?) {
        Ok(r) => json!({"status":"compared","report":r}),
        Err(e) => json!({"status":"unavailable","issues":e.0}),
    };
    requirements.sort_by_key(|r| {
        String::from_utf8(canonical_bytes(r).unwrap())
            .unwrap()
            .encode_utf16()
            .collect::<Vec<_>>()
    });
    requirements.dedup();
    Ok(
        json!({"status":"evaluated","edits":selected.iter().map(|i|&request.edits[*i].id).collect::<Vec<_>>(),"candidate":candidate,"comparison":comparison,
        "patch":{"graph":{"beforeDigest":before,"afterDigest":after},"policy":{"beforeDigest":canonical_digest(&base.inputs.policy)?,"afterDigest":canonical_digest(&candidate.inputs.policy)?},"bindingUpdates":if old_binding!=candidate.inputs.policy.graph {vec![json!({"subject":candidate.inputs.policy.id,"fact":"policy.graph","before":old_binding,"after":candidate.inputs.policy.graph})]}else{vec![]}},
        "viable":viable,"authorization":if viable{"approval-required"}else{"unavailable"},"requirements":requirements,"requirementInterpretation":"Conservative proposal requirements; exact governed proposal recomputes all actions against the protected baseline",
        "rank":{"editedRecords":occupied.len(),"semanticCost":cost}}),
    )
}
pub fn search_repairs(
    value: &RepairRequest,
    token: CancellationToken,
) -> Result<RepairReport, CheckError> {
    if value.edits.len() > 32 {
        return fail(
            "REPAIR_RESOURCE_LIMIT",
            "At most 32 supplied edits are permitted",
        );
    }
    for edit in &value.edits {
        match &edit.operation {
            RepairOperation::RestoreMapping { mapping } => patamaps_core::check_metadata_bounds(
                mapping.attributes.iter().map(|v| (v, 6)).chain(
                    mapping
                        .transform
                        .iter()
                        .filter_map(|t| t.configuration.as_ref())
                        .map(|v| (v, 7)),
                ),
                &edit.id,
                "REPAIR_RESOURCE_LIMIT",
            )?,
            RepairOperation::SupplyDeclaration { declaration }
                if declaration.applicability.is_some() =>
            {
                return fail(
                    "REPAIR_UNSUPPORTED_DECLARATION",
                    "Repair cannot invent applicability",
                );
            }
            _ => (),
        }
    }
    patamaps_core::check_input_bounds(
        &value.baseline.inputs.graph,
        &value.baseline.inputs.packs,
        &value.baseline.inputs.policy,
        &value.baseline.inputs.context,
    )?;
    replay(&value.baseline)?;
    let mut request: RepairRequest = parse(&canonical_bytes(value)?)?;
    request
        .edits
        .sort_by(|a, b| a.id.encode_utf16().cmp(b.id.encode_utf16()));
    if request.edits.is_empty()
        || request.edits.len() > 32
        || request.bounds.maximum_candidates.get() > 4096
        || request.bounds.maximum_edits.get() > 32
        || request.bounds.maximum_elapsed_milliseconds.get() > 60_000
        || request.bounds.maximum_work_units.get() > 20_000_000
        || request.allowed_facts.len() > 128
        || request.protected_facts.len() > 128
    {
        return fail(
            "REPAIR_RESOURCE_LIMIT",
            "Repair space or runtime bounds exceed Draft 1",
        );
    }
    if request.baseline.inputs.specs().next().is_none() {
        return Err(CheckError(vec![Issue::error(
            "REPAIR_MISSING_PROJECTION",
            "Repair requires a captured consumer projection",
            "repair",
        )]));
    }
    for spec in request.baseline.inputs.specs() {
        if spec
            .consumer
            .as_deref()
            .or_else(|| spec.semantics.as_ref().map(|s| s.consumer.as_str()))
            != Some(&request.consumer)
        {
            return fail(
                "REPAIR_WRONG_CONSUMER",
                "Repair consumer must bind every captured projection",
            );
        }
    }
    if request
        .baseline
        .inputs
        .policy
        .semantics
        .as_ref()
        .is_some_and(|s| {
            s.derivation_limits.max_depth.get() > request.bounds.maximum_derivation_depth.get()
        })
    {
        return fail(
            "REPAIR_DERIVATION_BOUND_MISMATCH",
            "Repair cannot silently change policy proof limits",
        );
    }
    if request
        .edits
        .iter()
        .map(|e| &e.id)
        .collect::<BTreeSet<_>>()
        .len()
        != request.edits.len()
        || request.edits.iter().any(|e| e.id.is_empty())
    {
        return fail(
            "REPAIR_DUPLICATE_EDIT",
            "Supplied edit IDs must be nonempty and unique",
        );
    }
    let started = Instant::now();
    let control = WorkControl::new(
        token,
        Duration::from_millis(request.bounds.maximum_elapsed_milliseconds.get()),
        request.bounds.maximum_work_units.get(),
    );
    let n = request.edits.len();
    let total = (1u64 << n) - 1;
    let mut permitted = 0u64;
    let mut choose = 1u64;
    for size in 1..=n.min(request.bounds.maximum_edits.get() as usize) {
        choose = choose * (n - size + 1) as u64 / size as u64;
        permitted += choose;
    }
    let mut attempts = Vec::new();
    let mut reasons = Vec::new();
    let mut ranked = Vec::new();
    let mut examined = 0u64;
    let mut output_bytes = canonical_bytes(&request)?.len().saturating_add(16_384);
    if permitted < total {
        reasons.push("edit-limit".to_string());
    }
    'sizes: for size in 1..=n.min(request.bounds.maximum_edits.get() as usize) {
        let mut indices: Vec<usize> = (0..size).collect();
        loop {
            if let Err(e) = control.poll() {
                reasons.push(e.0[0].code.clone());
                break 'sizes;
            }
            if attempts.len() as u64 >= request.bounds.maximum_candidates.get() {
                reasons.push("candidate-limit".into());
                break 'sizes;
            }
            let mut result = match attempt(&request, &indices, &control) {
                Ok(v) => v,
                Err(e) if stopping(&e) => {
                    reasons.push(e.0[0].code.clone());
                    break 'sizes;
                }
                Err(e) => {
                    json!({"status":"blocked","edits":indices.iter().map(|i|&request.edits[*i].id).collect::<Vec<_>>(),"issues":e.0})
                }
            };
            let digest = canonical_digest(&result)?;
            let id = format!("urn:patamaps:repair-proposal:{}", &digest[7..]);
            result["id"] = json!(id);
            result["digest"] = json!(digest);
            examined += 1;
            let bytes = canonical_bytes(&result)?.len();
            if output_bytes.saturating_add(bytes) > MAX_INPUT_BYTES {
                reasons.push("output-limit".into());
                break 'sizes;
            }
            output_bytes += bytes;
            if result["viable"] == true {
                ranked.push((
                    result["rank"]["editedRecords"].as_u64().unwrap(),
                    result["rank"]["semanticCost"].as_u64().unwrap(),
                    id,
                ));
            }
            attempts.push(result);
            let Some(pos) = (0..size).rev().find(|p| indices[*p] < n - size + *p) else {
                break;
            };
            indices[pos] += 1;
            for p in pos + 1..size {
                indices[p] = indices[p - 1] + 1;
            }
        }
    }
    ranked.sort();
    let proposals: Vec<_> = ranked.into_iter().map(|(_, _, id)| id).collect();
    let complete = attempts.len() as u64 == total;
    let mut report = RepairReport {
        schema_version: ProtocolVersion::Draft1,
        document_type: "repair-result",
        id: String::new(),
        digest: String::new(),
        request,
        status: if complete { "complete" } else { "incomplete" },
        applied: false,
        space: "nonempty-subsets-of-supplied-edits",
        proposals: proposals.clone(),
        coverage: json!({"totalCombinations":total.to_string(),"examined":examined,"recorded":attempts.len(),"unrecorded":examined-attempts.len() as u64,"unexamined":(total-examined).to_string(),"excludedByEditLimit":(total-permitted).to_string(),"elapsedMilliseconds":started.elapsed().as_millis(),"workUnits":control.used(),"stopReasons":if complete{vec![]}else{reasons}}),
        attempts,
        minimality: json!({"status":if complete&&!proposals.is_empty(){"within-finite-space"}else{"not-established"},"proposal":if complete{proposals.first()}else{None},"global":false}),
    };
    report.digest = patamaps_governance::document_digest(&report)?;
    report.id = format!("urn:patamaps:repair-result:{}", &report.digest[7..]);
    parse_value(&canonical_bytes(&report)?)?;
    Ok(report)
}
