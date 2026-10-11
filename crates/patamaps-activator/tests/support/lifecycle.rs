//! Shared pure fixture for the real protected-host lifecycle and portable checks.
use patamaps_contracts::*;
use patamaps_core::{CheckedGraph, DerivationStatus, compose, derive};
use patamaps_projection::{CaptureInputs, CaptureRecord, SourceReceipt, capture};
use serde::de::DeserializeOwned;
use serde_json::json;

fn typed<T: DeserializeOwned>(value: serde_json::Value) -> T {
    parse(&canonical_bytes(&value).unwrap()).unwrap()
}

pub fn consumer_capture(revision: &str, module: &str) -> CaptureRecord {
    let concept: GraphDocument = typed(json!({
        "schemaVersion":"0.1.0", "documentType":"graph", "id":"urn:shard:linux:concept",
        "namespace":"concept-owner", "revision":"1",
        "entities":[{"id":"urn:command:greet", "kind":"routing:command", "attributes":{"path":"/greet/:id"}}],
        "mappings":[{"id":"urn:mapping:alias", "relation":"lifecycle:alias",
            "sources":["urn:command:greet"], "targets":["urn:command:implementation-greet"],
            "cardinality":"one-to-one", "lossiness":"lossless",
            "provenance":{"status":"declared", "assertedBy":"concept-owner"}}],
        "authorities":[{"id":"urn:authority:concept", "concept":"urn:command:greet",
            "source":"urn:command:greet", "facts":["implementation","signature"], "mode":"canonical",
            "provenance":{"status":"declared", "assertedBy":"concept-owner"}}]
    }));
    let implementation: GraphDocument = typed(json!({
        "schemaVersion":"0.1.0", "documentType":"graph", "id":"urn:shard:linux:implementation",
        "namespace":"implementation-owner", "revision":revision,
        "entities":[{"id":"urn:command:implementation-greet", "kind":"routing:command"},
            {"id":"urn:handler:greet", "kind":"routing:handler", "locators":[{"uri":format!("rust:crate::{module}::greet")}]}],
        "mappings":[{"id":"urn:mapping:implementation-handler", "relation":"routing:handled_by",
            "sources":["urn:command:implementation-greet"], "targets":["urn:handler:greet"],
            "cardinality":"one-to-one", "lossiness":"lossless",
            "provenance":{"status":"declared", "assertedBy":"implementation-owner"}}],
        "authorities":[{"id":"urn:authority:implementation", "concept":"urn:command:greet",
            "source":"urn:handler:greet", "facts":["implementation"], "mode":"delegated",
            "delegatedFrom":"urn:authority:concept",
            "provenance":{"status":"declared", "assertedBy":"concept-owner"}}]
    }));
    let routing: RelationPack =
        parse(include_bytes!("../../../../relation-packs/routing.json")).unwrap();
    let law: RelationPack = typed(json!({
        "schemaVersion":"0.1.0", "documentType":"relation-pack", "id":"urn:pack:linux:lifecycle", "version":"1.0.0",
        "imports":[{"id":routing.id, "version":routing.version, "digest":canonical_digest(&routing).unwrap()}],
        "relations":[{"id":"lifecycle:alias", "cyclePolicy":"forbid", "impactDirection":"source-to-target",
            "sourceKinds":["routing:command"], "targetKinds":["routing:command"]}],
        "laws":[{"id":"urn:law:linux:binding-chain", "operation":"chain",
            "operands":["lifecycle:alias","routing:handled_by"], "resultRelation":"routing:handled_by",
            "handling":{"lossiness":"conservative", "uncertainty":"conservative", "authority":"none"}}]
    }));
    let packs = vec![routing, law];
    let mut graph = compose(
        &[concept.clone(), implementation.clone()],
        "urn:graph:linux".into(),
        "linux".into(),
    )
    .unwrap();
    graph.revision = Some(revision.into());
    let checked = CheckedGraph::check(graph.clone(), packs.clone()).unwrap();
    let request: CompositionRequest = typed(json!({
        "schemaVersion":"0.1.0", "documentType":"composition-request", "law":"urn:law:linux:binding-chain",
        "premises":["urn:mapping:alias","urn:mapping:implementation-handler"], "context":{},
        "bounds":{"maxDepth":8,"maxDerivations":32}, "derivations":[], "assessments":[], "evidence":[],
        "resultId":"urn:mapping:greet"
    }));
    let derived = derive(&checked, &request);
    assert_eq!(
        derived.status,
        DerivationStatus::Proposed,
        "{:?}",
        derived.issues
    );
    let proof = derived.derivation.unwrap();
    graph.mappings.push(derived.mapping.unwrap());
    let policy = typed(json!({
        "schemaVersion":"0.1.0", "documentType":"policy", "id":"urn:policy:linux",
        "graph":{"id":graph.id,"revision":revision},
        "mappings":[{"select":{"ids":["urn:mapping:alias","urn:mapping:implementation-handler","urn:mapping:greet"]},
            "coverage":"total", "determinism":"deterministic", "reversibility":"irreversible"}],
        "constraints":[], "evidence":[],
        "semantics":{"interpretation":"declared-law-application", "derivations":[proof],
            "derivationLimits":{"maxDepth":8,"maxDerivations":32}, "assessments":[],
            "uncertaintyRequirements":[{"id":"urn:requirement:linux:identity", "select":{"ids":["urn:mapping:greet"]},
                "dimension":"identity", "allowedStates":["unknown"], "requireEvidence":false}],
            "riskBudgets":[{"id":"urn:budget:linux", "consumer":"urn:consumer:linux", "maximumTotalCost":3,
                "maximumInferredMappings":1, "maximumLossyMappings":0,
                "requireCompleteClassification":true, "requireCompleteDependencies":true,
                "classifications":[{"id":"urn:class:linux", "select":{"ids":["urn:mapping:alias","urn:mapping:implementation-handler","urn:mapping:greet"]},
                    "classification":"explicit-unit-cost", "cost":1}]}]}
    }));
    let spec = typed(json!({
        "schemaVersion":"0.1.0", "documentType":"projection-spec", "id":"urn:projection:linux",
        "consumer":"urn:consumer:linux", "select":{"ids":["urn:command:greet"]},
        "slots":[{"name":"handler", "relation":"routing:handled_by", "direction":"outgoing",
            "cardinality":"exactly-one", "targetKinds":["routing:handler"]}], "pathTree":{},
        "semantics":{"consumer":"urn:consumer:linux", "budget":"urn:budget:linux"}
    }));
    let code = "pub fn greet(input:&str)->String{format!(\"Hello, {}!\",input)}\n";
    let mut sources = vec![SourceReceipt {
        id: "urn:source:linux".into(),
        locator: format!("rust:crate::{module}"),
        digest: byte_digest(code.as_bytes()),
        byte_length: SafeInteger::new(code.len() as u64).unwrap(),
        content: Some(code.into()),
    }];
    for shard in [concept, implementation] {
        let raw = canonical_bytes(&shard).unwrap();
        sources.push(SourceReceipt {
            id: shard.id,
            locator: format!("workspace:{}.json", shard.namespace),
            digest: byte_digest(&raw),
            byte_length: SafeInteger::new(raw.len() as u64).unwrap(),
            content: Some(String::from_utf8(raw).unwrap()),
        });
    }
    capture(
        CaptureInputs {
            graph,
            packs,
            policy,
            context: Default::default(),
            evaluated_at: "2026-10-10T00:00:00Z".into(),
            projection_spec: Some(spec),
        },
        sources,
    )
    .unwrap()
}
