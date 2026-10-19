use patamaps_contracts::*;
use patamaps_core::*;
use patamaps_projection::*;
use serde_json::json;
use std::time::Duration;

#[test]
fn native_extension_projects_but_serialized_results_cannot_install_code_or_bypass_replay() {
    let mut inputs = CaptureInputs {
        graph: parse(include_bytes!(
            "../package-inputs/fixtures/routing/graph.json"
        ))
        .unwrap(),
        policy: parse(include_bytes!(
            "../package-inputs/fixtures/routing/policy.json"
        ))
        .unwrap(),
        packs: vec![
            parse(include_bytes!("../package-inputs/relation-packs/core.json")).unwrap(),
            parse(include_bytes!(
                "../package-inputs/relation-packs/routing.json"
            ))
            .unwrap(),
        ],
        context: JsonObject::new(),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
        projection_spec: Some(
            parse(include_bytes!(
                "../package-inputs/fixtures/routing/projection-spec.json"
            ))
            .unwrap(),
        ),
        projection_specs: vec![],
    };
    let subject = "urn:example:handler:create-user";
    inputs
        .graph
        .entities
        .iter_mut()
        .find(|e| e.id == subject)
        .unwrap()
        .locators = Some(vec![
        parse(&canonical_bytes(&json!({"uri":"rust:crate::service::greet"})).unwrap()).unwrap(),
    ]);
    let kind = "consumer:requires-rust-locator";
    inputs.policy.constraints.push(Constraint {
        id: "urn:constraint:native-rust-locator".into(),
        kind: kind.into(),
        subjects: vec![subject.into()],
        parameters: None,
    });
    let graph = CheckedGraph::check(inputs.graph.clone(), inputs.packs.clone()).unwrap();
    let mut registry = ConstraintRegistry::new();
    registry
        .register(
            kind,
            ContentBinding {
                id: "urn:evaluator:rust-locator".into(),
                digest: canonical_digest(&"native-locator-check-1").unwrap(),
            },
            |c: &Constraint, context: &ConstraintEvaluationContext<'_>| {
                context.poll()?;
                let present = context
                    .graph()
                    .entity(&c.subjects[0])
                    .unwrap()
                    .locators
                    .as_ref()
                    .unwrap()
                    .iter()
                    .any(|l| l.uri.starts_with("rust:"));
                Ok(if present {
                    vec![]
                } else {
                    vec![Issue::error(
                        &format!("{}:MISSING", c.kind),
                        "Required native locator absent",
                        &c.subjects[0],
                    )]
                })
            },
        )
        .unwrap();
    let control = WorkControl::new(
        CancellationToken::default(),
        Duration::from_secs(60),
        100_000,
    );
    let generation = admit_with_constraints(
        &graph,
        &inputs.policy,
        EvaluationOptions {
            context: inputs.context.clone(),
            evaluated_at: inputs.evaluated_at.clone(),
        },
        &registry,
        &control,
    )
    .unwrap();
    let projection = project(&generation, inputs.projection_spec.as_ref().unwrap()).unwrap();
    assert!(
        emit_rust(&projection, Some("handler"))
            .unwrap()
            .contains("crate::service::greet")
    );
    let untrusted_result = json!({"status":"viable","generation":generation.record(),"projection":projection.record(),"pathTree":null,"issues":[]});
    drop(generation);

    // Wire data carries no evaluator. The ordinary executor captures and verifies
    // a refusal, rather than restoring the checked native generation above.
    let mut captured = capture(inputs, vec![]).unwrap();
    assert_eq!(captured.result["status"], "rejected");
    assert!(
        captured.result["issues"]
            .as_array()
            .unwrap()
            .iter()
            .any(|i| i["code"] == "UNKNOWN_CONSTRAINT_KIND")
    );
    assert_eq!(replay(&captured).unwrap().result()["status"], "rejected");

    // Even a correctly readdressed viable result cannot launder the callback
    // through the default replay executor.
    captured.result = untrusted_result;
    let mut wire = serde_json::to_value(&captured).unwrap();
    wire.as_object_mut().unwrap().remove("id");
    wire.as_object_mut().unwrap().remove("digest");
    captured.digest = canonical_digest(&wire).unwrap();
    captured.id = format!("urn:patamaps:capture:{}", &captured.digest[7..]);
    let refused = replay(&captured).unwrap_err();
    assert!(
        refused.0.iter().any(|i| i.code == "REPLAY_RESULT_MISMATCH"),
        "{refused:?}"
    );
}
