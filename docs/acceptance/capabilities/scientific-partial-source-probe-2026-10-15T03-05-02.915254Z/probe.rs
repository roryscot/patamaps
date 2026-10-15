use patamaps_contracts::*;
use patamaps_projection::*;
use patamaps_scientific::*;
use serde_json::{Value, json};
use std::collections::BTreeMap;

fn decode<T: serde::de::DeserializeOwned>(value: Value) -> T {
    parse(&canonical_bytes(&value).unwrap()).unwrap()
}

fn example(raw: &str, changed: bool, partial: bool) -> Value {
    let original = parse_tsv(raw.as_bytes(), None).unwrap();
    let mut document = original.document().clone();
    if changed {
        let column = document.columns.iter().position(|c| c == "subject_id").unwrap();
        document.rows[0][column].push_str("-FORGED-PROBE");
    }
    let checked = check_document(&document).unwrap();
    let source: ImportOptions = decode(json!({"id":"urn:source:partial-probe","namespace":"partial-probe","sourceRevision":"probe-r1"}));
    let mut graph = import_graph(&checked, &source).unwrap();
    for mapping in &mut graph.mappings { mapping.lossiness = Lossiness::Lossy; }
    let policy: PolicyDocument = decode(json!({
        "schemaVersion":"0.1.0","documentType":"policy","id":"urn:policy:partial-probe",
        "graph":{"id":graph.id,"digest":canonical_digest(&graph).unwrap()},
        "mappings":[{"select":{"ids":graph.mappings.iter().map(|m| m.id.clone()).collect::<Vec<_>>()},
            "coverage":"partial","determinism":"deterministic","reversibility":"irreversible"}],
        "constraints":[],"evidence":[],"semantics":{"interpretation":"declared-law-application",
            "derivations":[],"assessments":[],"uncertaintyRequirements":[],"riskBudgets":[],
            "derivationLimits":{"maxDepth":8,"maxDerivations":32}}
    }));
    let spec: ProjectionSpec = decode(json!({
        "schemaVersion":"0.1.0","documentType":"projection-spec","id":"urn:projection:partial-probe",
        "select":{"kinds":["scientific:entity"]},"slots":[],
        "semantics":{"consumer":"urn:consumer:partial-probe","budget":null}
    }));
    let mut receipts = vec![SourceReceipt { id:"urn:receipt:tsv".into(), locator:"urn:source:tsv".into(),
        digest:byte_digest(raw.as_bytes()), byte_length:SafeInteger::new(raw.len() as u64).unwrap(), content:Some(raw.into()) }];
    if partial {
        receipts.push(SourceReceipt { id:"urn:receipt:metadata".into(), locator:"urn:source:metadata".into(),
            digest:byte_digest(b"{}\n"), byte_length:SafeInteger::new(3).unwrap(), content:None });
    }
    let captured = capture(CaptureInputs {graph, packs:vec![scientific_pack()], policy, context:JsonObject::new(),
        evaluated_at:"2026-10-10T00:00:00Z".into(), projection_spec:Some(spec), projection_specs:vec![]}, receipts).unwrap();
    assert_eq!(captured.result["status"], "viable");
    let mut option_value = json!({
        "name":"Partial raw source falsification probe","description":"Synthetic altered row; original source bytes remain unchanged",
        "datePublished":"2026-10-10","consumer":"urn:consumer:partial-probe","environment":"isolated-test",
        "source":source,"tsvReceipt":"urn:receipt:tsv","metadataReceipt":if partial {Some("urn:receipt:metadata")}else{None},
        "externalSources":[],"rawInputs":BTreeMap::from([("urn:receipt:tsv", raw)])
    });
    if !partial { option_value.as_object_mut().unwrap().remove("metadataReceipt"); }
    let options: CrateOptions = decode(option_value);
    match create_crate(&captured, &options) {
        Ok(package) => {
            let verified = verify_crate(package.record()).is_ok();
            if changed && partial {
                std::fs::write("altered-partial.crate.json", canonical_bytes(package.record()).unwrap()).unwrap();
            }
            json!({"changedRecordedRow":changed,"missingMetadata":partial,"accepted":true,"verificationAccepted":verified,
                "externalRawInputs":package.external_raw_inputs()})
        },
        Err(error) => json!({"changedRecordedRow":changed,"missingMetadata":partial,"accepted":false,"error":error.code})
    }
}

fn main() {
    let raw = std::fs::read_to_string(std::env::args().nth(1).unwrap()).unwrap();
    println!("{}", json!({"cases":[example(&raw,false,true),example(&raw,true,false),example(&raw,true,true)]}));
}
