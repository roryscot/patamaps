use patamaps_contracts::*;
use patamaps_core::*;
use patamaps_projection::*;
use serde_json::json;
use std::collections::BTreeMap;

fn main() {
    let mut graph: GraphDocument =
        parse(include_bytes!("../../typed-fixtures/graph.json")).unwrap();
    let pack: RelationPack = parse(include_bytes!("../../typed-fixtures/pack.json")).unwrap();
    let core_pack: RelationPack = parse(include_bytes!("../../typed-fixtures/core.json")).unwrap();
    let mut request: CompositionRequest =
        parse(include_bytes!("../../typed-fixtures/request.json")).unwrap();
    let mut policy: PolicyDocument =
        parse(include_bytes!("../../typed-fixtures/policy.json")).unwrap();
    let mut spec: ProjectionSpec =
        parse(include_bytes!("../../typed-fixtures/projection-spec.json")).unwrap();
    graph.entities[0].attributes = Some(JsonObject::from([(
        "path".into(),
        "/network/:networkId".into(),
    )]));
    for subject in ["urn:m:ab", "urn:m:bc"] {
        let index = request.assessments.len();
        let evidence = format!("urn:evidence:typed:{index}");
        request.evidence.push(
            parse(
                &canonical_bytes(&json!({
                    "id": evidence, "subjects": [subject], "kind": "uncertainty:identity",
                    "result": "supports", "producer": "recorded-source-owner"
                }))
                .unwrap(),
            )
            .unwrap(),
        );
        request.assessments.push(
            parse(
                &canonical_bytes(&json!({
                    "id": format!("urn:assessment:typed:{index}"),
                    "subject": subject, "dimension": "identity", "status": "supported",
                    "evidence": [evidence], "assessor": "recorded-reviewer", "sourceRevision": "1"
                }))
                .unwrap(),
            )
            .unwrap(),
        );
    }
    let proposed = derive(
        &CheckedGraph::check(graph.clone(), vec![pack.clone(), core_pack.clone()]).unwrap(),
        &request,
    );
    assert_eq!(proposed.status, DerivationStatus::Proposed);
    graph.mappings.push(proposed.mapping.unwrap());
    policy.evidence = request.evidence.clone();
    let semantic = policy.semantics.as_mut().unwrap();
    semantic.derivations.push(proposed.derivation.unwrap());
    semantic.assessments = request.assessments.clone();
    semantic.uncertainty_requirements.push(
        parse(
            &canonical_bytes(&json!({
                "id": "urn:requirement:typed-identity", "select": {"ids": ["urn:m:ac"]},
                "dimension": "identity", "allowedStates": ["supported"], "requireEvidence": true
            }))
            .unwrap(),
        )
        .unwrap(),
    );
    semantic.risk_budgets.push(parse(&canonical_bytes(&json!({
        "id": "urn:budget:typed", "consumer": "urn:consumer:example",
        "maximumTotalCost": 5, "requireCompleteClassification": true,
        "requireCompleteDependencies": true,
        "classifications": [
            {"id":"urn:cost:ab","select":{"ids":["urn:m:ab"]},"classification":"recorded","cost":2},
            {"id":"urn:cost:bc","select":{"ids":["urn:m:bc"]},"classification":"recorded","cost":3},
            {"id":"urn:cost:ac","select":{"ids":["urn:m:ac"]},"classification":"inference","cost":0}
        ]
    })).unwrap()).unwrap());
    spec.semantics.as_mut().unwrap().budget = Some("urn:budget:typed".into());
    spec.path_tree = Some(parse(b"{}").unwrap());
    let original = canonical_bytes(&(&graph, &policy, &spec)).unwrap();
    let checked =
        CheckedGraph::check(graph.clone(), vec![pack.clone(), core_pack.clone()]).unwrap();
    let generation = admit(
        &checked,
        &policy,
        EvaluationOptions {
            context: request.context.clone(),
            evaluated_at: "2026-10-10T12:00:00Z".into(),
        },
    )
    .unwrap();
    let projection = project(&generation, &spec).unwrap();
    let semantics = projection.record().semantics.as_ref().unwrap();
    assert_eq!(semantics.risk.total_cost.unwrap().get(), 5);
    assert_eq!(semantics.risk.classifications.len(), 3);
    let tree = compile_path_tree(&projection, &spec).unwrap();
    let template = canonical_bytes(tree.record()).unwrap();
    let hydrated = hydrate(&tree, BTreeMap::from([("networkId".into(), "99".into())])).unwrap();
    let node = &hydrated.tree.children["network"].children[":networkId"];
    assert_eq!(node.path, "/network/99");
    assert_eq!(node.occupant.as_ref().unwrap().id, "urn:a");
    assert_eq!(
        tree.record().tree.children["network"].children[":networkId"].path,
        "/network/:networkId"
    );
    assert_eq!(template, canonical_bytes(tree.record()).unwrap());
    assert!(
        hydrate(&tree, BTreeMap::new())
            .unwrap_err()
            .0
            .iter()
            .any(|issue| issue.code == "MISSING_PATH_PARAMETER")
    );
    std::fs::write(
        "native_tree.mts",
        emit_typescript_path_tree(&tree, "nativeTree").unwrap(),
    )
    .unwrap();
    std::fs::write(
        "params_tree.mts",
        emit_typescript_path_tree(&tree, "params").unwrap(),
    )
    .unwrap();
    std::fs::write(
        "prefixed_tree.mts",
        emit_typescript_path_tree(&tree, "_patamapsParams").unwrap(),
    )
    .unwrap();
    let edge_graph: GraphDocument = parse(&canonical_bytes(&json!({
        "schemaVersion":"0.1.0","documentType":"graph","id":"urn:tree:edge",
        "namespace":"edge","revision":"1","entities":[
            {"id":"urn:edge:users","kind":"route","label":"\";throw new Error('injected');//","attributes":{"path":"/users/:id/:next"}},
            {"id":"urn:edge:files","kind":"route","attributes":{"path":"/files/*rest?"}},
            {"id":"urn:edge:proto","kind":"route","attributes":{"path":"/__proto__/:id"}}
        ],"mappings":[],"authorities":[]
    })).unwrap()).unwrap();
    let edge_policy: PolicyDocument = parse(
        &canonical_bytes(&json!({
            "schemaVersion":"0.1.0","documentType":"policy","id":"urn:policy:edge",
            "graph":{"id":"urn:tree:edge","revision":"1"},"mappings":[],"constraints":[],"evidence":[]
        }))
        .unwrap(),
    )
    .unwrap();
    let edge_spec: ProjectionSpec = parse(
        &canonical_bytes(&json!({
            "schemaVersion":"0.1.0","documentType":"projection-spec","id":"urn:spec:edge",
            "select":{"kinds":["route"]},"slots":[],"pathTree":{}
        }))
        .unwrap(),
    )
    .unwrap();
    let edge_checked = CheckedGraph::check(edge_graph.clone(), vec![]).unwrap();
    let edge_generation = admit(
        &edge_checked,
        &edge_policy,
        EvaluationOptions {
            context: JsonObject::new(),
            evaluated_at: "2026-10-10T12:00:00Z".into(),
        },
    )
    .unwrap();
    let edge_projection = project(&edge_generation, &edge_spec).unwrap();
    let edge_tree = compile_path_tree(&edge_projection, &edge_spec).unwrap();
    std::fs::write(
        "edge_tree.mts",
        emit_typescript_path_tree(&edge_tree, "edgeTree").unwrap(),
    )
    .unwrap();
    let unicode = hydrate(
        &tree,
        BTreeMap::from([("networkId".into(), "a\u{85}b".into())]),
    )
    .unwrap();
    let unicode_path = &unicode.tree.children["network"].children[":networkId"].path;
    let mut alternate_graph = edge_graph.clone();
    alternate_graph.entities.truncate(1);
    alternate_graph.entities[0]
        .attributes
        .as_mut()
        .unwrap()
        .insert("path".into(), "--users--:id".into());
    let mut alternate_spec = edge_spec.clone();
    alternate_spec.path_tree.as_mut().unwrap().delimiter = Some(PathDelimiter::Hyphen);
    let alternate_checked = CheckedGraph::check(alternate_graph, vec![]).unwrap();
    let alternate_generation = admit(
        &alternate_checked,
        &edge_policy,
        EvaluationOptions {
            context: JsonObject::new(),
            evaluated_at: "2026-10-10T12:00:00Z".into(),
        },
    )
    .unwrap();
    let alternate_projection = project(&alternate_generation, &alternate_spec).unwrap();
    let alternate_tree = compile_path_tree(&alternate_projection, &alternate_spec).unwrap();
    let alternate_hydrated = hydrate(
        &alternate_tree,
        BTreeMap::from([("id".into(), "value".into())]),
    )
    .unwrap();
    assert_eq!(
        alternate_hydrated.tree.children["users"].children[":id"].path,
        "--users--value"
    );
    std::fs::write(
        "alternate_tree.mts",
        emit_typescript_path_tree(&alternate_tree, "alternateTree").unwrap(),
    )
    .unwrap();
    let mut repeated_graph = edge_graph;
    repeated_graph.entities.truncate(1);
    repeated_graph.entities[0]
        .attributes
        .as_mut()
        .unwrap()
        .insert(
            "path".into(),
            format!("/repeat/{}", vec![":id"; 16].join("/")).into(),
        );
    let repeated_checked = CheckedGraph::check(repeated_graph, vec![]).unwrap();
    let repeated_generation = admit(
        &repeated_checked,
        &edge_policy,
        EvaluationOptions {
            context: JsonObject::new(),
            evaluated_at: "2026-10-10T12:00:00Z".into(),
        },
    )
    .unwrap();
    let repeated_projection = project(&repeated_generation, &edge_spec).unwrap();
    let repeated_tree = compile_path_tree(&repeated_projection, &edge_spec).unwrap();
    assert!(
        hydrate(
            &repeated_tree,
            BTreeMap::from([("id".into(), "x".repeat(1_100_000))])
        )
        .is_err()
    );
    assert!(
        hydrate(
            &tree,
            BTreeMap::from([("networkId".into(), "\0".repeat(3_000_000))])
        )
        .is_err()
    );
    std::fs::write(
        "repeated_tree.mts",
        emit_typescript_path_tree(&repeated_tree, "repeatedTree").unwrap(),
    )
    .unwrap();
    let input = CaptureInputs {
        graph: graph.clone(),
        packs: vec![pack, core_pack],
        policy: policy.clone(),
        context: request.context,
        evaluated_at: "2026-10-10T12:00:00Z".into(),
        projection_spec: None,
        projection_specs: vec![spec.clone()],
    };
    let saved = capture(input.clone(), vec![]).unwrap();
    assert_eq!(saved.result["status"], "viable");
    let verified = replay(&saved).unwrap();
    let mut expensive = input;
    expensive.policy.semantics.as_mut().unwrap().risk_budgets[0].maximum_total_cost =
        SafeInteger::new(4).unwrap();
    let rejected = capture(expensive, vec![]).unwrap();
    assert_eq!(rejected.result["status"], "rejected");
    assert_eq!(rejected.result["compilationStatus"], "viable");
    let rejected_replay = replay(&rejected).unwrap();
    let difference = compare(&verified, &rejected_replay).unwrap();
    assert!(difference["semantic"]["projections"][0]["riskChanged"].is_null());
    let mut forged = saved.clone();
    forged.inputs.policy.evidence[0].producer = "substituted".into();
    let mut body = serde_json::to_value(&forged).unwrap();
    body.as_object_mut().unwrap().remove("id");
    body.as_object_mut().unwrap().remove("digest");
    forged.digest = canonical_digest(&body).unwrap();
    forged.id = format!("urn:patamaps:capture:{}", &forged.digest[7..]);
    assert!(
        replay(&forged)
            .unwrap_err()
            .0
            .iter()
            .any(|issue| issue.code == "REPLAY_RESULT_MISMATCH")
    );
    assert_eq!(
        original,
        canonical_bytes(&(&graph, &policy, &spec)).unwrap()
    );
    std::fs::write("typed_bindings.rs", emit_rust(&projection, None).unwrap()).unwrap();
    println!(
        "{}",
        json!({
            "profile": "patamaps-native-typed-consumer-acceptance",
            "typedTreeHydration": true, "templateUnchanged": true, "inputBytesUnchanged": true,
            "budgetBoundary": true, "replayTamperRefusal": true, "unavailableRiskStaysNull": true,
            "projectionDigest": projection.record().digest, "cost": 5,
            "template": tree.record(), "hydrated": hydrated, "unicodePath": unicode_path,
            "acceptedCapture": saved, "rejectedCapture": rejected, "comparison": difference
        })
    );
}
