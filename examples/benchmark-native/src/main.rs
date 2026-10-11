//! Explicit in-process SDK phase measurements; no alternative evaluator.
use patamaps_contracts::*;
use patamaps_core::{CancellationToken, CheckedGraph, EvaluationOptions, admit, derive};
use patamaps_inspect::{RepairRequest, search_repairs};
use patamaps_projection::{CaptureInputs, capture, emit_rust, emit_typescript, project, replay};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{hint::black_box, time::Instant};

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Case {
    name: String,
    inputs: CaptureInputs,
    expected_status: String,
    expected_code: Option<String>,
    expected_cost: Option<SafeInteger>,
    projection_batch: SafeInteger,
    authority_queries: Vec<(String, String, String)>,
    repair: Option<RepairRequest>,
}
fn typed<T: serde::de::DeserializeOwned>(v: Value) -> T {
    parse(&canonical_bytes(&v).unwrap()).unwrap()
}
fn exact_branch() -> Case {
    let pack: RelationPack = parse(include_bytes!("../../../fixtures/laws/pack.json")).unwrap();
    let mut entities = Vec::new();
    for id in (0..8)
        .map(|i| format!("urn:bench:node:{i}"))
        .chain(["urn:bench:leaf:left".into(), "urn:bench:leaf:right".into()])
    {
        entities.push(json!({"id":id,"kind":"concept"}));
    }
    let mut mappings = Vec::new();
    for (id, source, target) in (0..7)
        .map(|i| {
            (
                format!("urn:bench:base:{i}"),
                format!("urn:bench:node:{i}"),
                format!("urn:bench:node:{}", i + 1),
            )
        })
        .chain([
            (
                "urn:bench:base:left".into(),
                "urn:bench:node:7".into(),
                "urn:bench:leaf:left".into(),
            ),
            (
                "urn:bench:base:right".into(),
                "urn:bench:node:7".into(),
                "urn:bench:leaf:right".into(),
            ),
        ])
    {
        mappings.push(json!({"id":id,"relation":"example:exact","sources":[source],"targets":[target],
            "cardinality":"one-to-one","lossiness":"lossless","provenance":{"status":"declared","assertedBy":"benchmark-owner"}}));
    }
    let mut graph: GraphDocument = typed(
        json!({"schemaVersion":"0.1.0","documentType":"graph","id":"urn:bench:proof-graph",
        "namespace":"benchmark","revision":"1","entities":entities,"mappings":mappings,"authorities":[]}),
    );
    let mut proofs = Vec::new();
    let mut prefix = "urn:bench:base:0".to_owned();
    for (suffix, edge) in (1..7)
        .map(|i| (i.to_string(), format!("urn:bench:base:{i}")))
        .chain([
            ("left".into(), "urn:bench:base:left".into()),
            ("right".into(), "urn:bench:base:right".into()),
        ])
    {
        let checked = CheckedGraph::check(graph.clone(), vec![pack.clone()]).unwrap();
        let result = format!("urn:bench:derived:{suffix}");
        let request = typed(
            json!({"schemaVersion":"0.1.0","documentType":"composition-request","law":"urn:example:law:exact-chain",
            "premises":[prefix,edge],"context":{},"bounds":{"maxDepth":16,"maxDerivations":64},
            "derivations":proofs,"resultId":result,"assessments":[],"evidence":[]}),
        );
        let outcome = derive(&checked, &request);
        assert_eq!(
            outcome.status,
            patamaps_core::DerivationStatus::Proposed,
            "{:?}",
            outcome.issues
        );
        graph.mappings.push(outcome.mapping.unwrap());
        proofs.push(outcome.derivation.unwrap());
        if suffix != "left" && suffix != "right" {
            prefix = result;
        }
    }
    assert_eq!(graph.mappings.len(), 17);
    assert_eq!(proofs.len(), 8);
    let policy = typed(
        json!({"schemaVersion":"0.1.0","documentType":"policy","id":"urn:bench:proof-policy",
        "graph":{"id":graph.id,"revision":"1"},"mappings":[{"select":{"relations":["example:exact"]},
            "coverage":"total","determinism":"deterministic","reversibility":"irreversible"}],"constraints":[],"evidence":[],
        "semantics":{"interpretation":"declared-law-application","derivations":proofs,"derivationLimits":{"maxDepth":16,"maxDerivations":64},
            "assessments":[],"uncertaintyRequirements":[],"riskBudgets":[{"id":"urn:bench:budget","consumer":"urn:bench:consumer",
                "classifications":[{"id":"urn:bench:classification","select":{"relations":["example:exact"]},"classification":"unit-cost","cost":1}],
                "maximumTotalCost":17,"requireCompleteClassification":true,"requireCompleteDependencies":true}]}}),
    );
    let spec = typed(
        json!({"schemaVersion":"0.1.0","documentType":"projection-spec","id":"urn:bench:projection",
        "select":{"ids":["urn:bench:node:0"]},"slots":[{"name":"related","relation":"example:exact","direction":"outgoing","cardinality":"many"}],
        "semantics":{"consumer":"urn:bench:consumer","budget":"urn:bench:budget"}}),
    );
    Case {
        name: "branching-proofs-overlapping-closure".into(),
        inputs: CaptureInputs {
            graph,
            packs: vec![pack],
            policy,
            context: Default::default(),
            evaluated_at: "2026-10-10T00:00:00Z".into(),
            projection_spec: Some(spec),
        },
        expected_status: "viable".into(),
        expected_code: None,
        expected_cost: Some(SafeInteger::new(17).unwrap()),
        projection_batch: SafeInteger::new(32).unwrap(),
        authority_queries: vec![],
        repair: None,
    }
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    if args[1] == "prepare-branch" {
        println!(
            "{}",
            String::from_utf8(canonical_bytes(&exact_branch()).unwrap()).unwrap()
        );
        return;
    }
    let read_start = Instant::now();
    let raw = std::fs::read(&args[1]).unwrap();
    let read_ns = read_start.elapsed().as_nanos();
    let case: Case = parse(&raw).unwrap();
    let identity_start = Instant::now();
    let executor = patamaps_projection::executor_id();
    let identity_ns = identity_start.elapsed().as_nanos();
    let mut samples = Vec::new();
    let mut expected_capture = None;
    for trial in 0..7 {
        let mut phases = serde_json::Map::new();
        let started = Instant::now();
        let decoded: Case = parse(black_box(&raw)).unwrap();
        phases.insert("strictDecodeNs".into(), json!(started.elapsed().as_nanos()));
        black_box(decoded);
        let started = Instant::now();
        let digest = canonical_digest(black_box(&case.inputs)).unwrap();
        phases.insert(
            "canonicalHashNs".into(),
            json!(started.elapsed().as_nanos()),
        );
        black_box(digest);
        let graph = case.inputs.graph.clone();
        let packs = case.inputs.packs.clone();
        let started = Instant::now();
        let checked = CheckedGraph::check(graph, packs);
        phases.insert("graphCheckNs".into(), json!(started.elapsed().as_nanos()));
        let mut artifacts = Value::Null;
        if let Ok(checked) = checked {
            if !case.authority_queries.is_empty() {
                let started = Instant::now();
                for (concept, fact, effective) in &case.authority_queries {
                    let resolved = checked.resolve_authority(concept, fact);
                    assert!(
                        matches!(&resolved,patamaps_core::AuthorityResolution::Resolved {effective: actual,..} if actual==effective)
                    );
                    black_box(resolved);
                }
                phases.insert(
                    "authorityQueriesNs".into(),
                    json!(started.elapsed().as_nanos()),
                );
            }
            let options = EvaluationOptions {
                context: case.inputs.context.clone(),
                evaluated_at: case.inputs.evaluated_at.clone(),
            };
            let started = Instant::now();
            let admitted = admit(&checked, &case.inputs.policy, options);
            phases.insert("admissionNs".into(), json!(started.elapsed().as_nanos()));
            if let (Ok(admitted), Some(spec)) = (admitted, &case.inputs.projection_spec) {
                let started = Instant::now();
                let first = project(&admitted, spec).unwrap();
                phases.insert(
                    "oneProjectionNs".into(),
                    json!(started.elapsed().as_nanos()),
                );
                if let Some(cost) = case.expected_cost {
                    assert_eq!(
                        first
                            .record()
                            .semantics
                            .as_ref()
                            .unwrap()
                            .risk
                            .total_cost
                            .unwrap()
                            .get(),
                        cost.get()
                    );
                }
                let started = Instant::now();
                for i in 0..case.projection_batch.get() {
                    let mut other = spec.clone();
                    other.id = format!("urn:bench:batch:{i}");
                    black_box(project(&admitted, &other).unwrap());
                }
                phases.insert(
                    "projectionBatchNs".into(),
                    json!(started.elapsed().as_nanos()),
                );
                let started = Instant::now();
                let json_bytes = canonical_bytes(first.record()).unwrap();
                let rust = emit_rust(&first, None).unwrap();
                let ts = emit_typescript(&first, "bindings", None).unwrap();
                phases.insert(
                    "threeEmissionsNs".into(),
                    json!(started.elapsed().as_nanos()),
                );
                artifacts = json!({"jsonBytes":json_bytes.len(),"rustBytes":rust.len(),"typescriptBytes":ts.len(),"projectionDigest":first.record().digest});
            }
        }
        let started = Instant::now();
        let captured = capture(case.inputs.clone(), vec![]).unwrap();
        phases.insert("captureNs".into(), json!(started.elapsed().as_nanos()));
        assert_eq!(
            captured.result["status"], case.expected_status,
            "{}",
            captured.result
        );
        if let Some(code) = &case.expected_code {
            assert!(
                captured.result["issues"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .any(|i| i["code"] == *code)
            );
        }
        if let Some(previous) = &expected_capture {
            assert_eq!(&captured.digest, previous);
        } else {
            expected_capture = Some(captured.digest.clone());
        }
        let started = Instant::now();
        let verified = replay(&captured).unwrap();
        phases.insert("replayNs".into(), json!(started.elapsed().as_nanos()));
        black_box(verified);
        if let Some(request) = &case.repair {
            let started = Instant::now();
            let repaired = search_repairs(request, CancellationToken::default()).unwrap();
            phases.insert(
                "boundedRepairNs".into(),
                json!(started.elapsed().as_nanos()),
            );
            assert_eq!(repaired.status, "complete");
            assert!(!repaired.applied);
            black_box(repaired);
        }
        samples.push(json!({"trial":trial,"phases":phases,"artifactSizes":artifacts,"captureDigest":captured.digest}));
    }
    println!(
        "{}",
        json!({"name":case.name,"executor":executor,"inputDigest":byte_digest(&raw),"inputBytes":raw.len(),
        "entities":case.inputs.graph.entities.len(),"mappings":case.inputs.graph.mappings.len(),"authorityRecords":case.inputs.graph.authorities.len(),
        "expectedStatus":case.expected_status,"expectedCost":case.expected_cost,"projectionBatch":case.projection_batch,
        "fileReadNs":read_ns,"firstExecutorSourceHashNs":identity_ns,"samples":samples,
        "scope":"Seven same-process SDK samples; graph input cloning precedes the graph-check timer; initial I/O and executor hashing are separate; no activation"})
    );
}
