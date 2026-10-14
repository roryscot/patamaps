use patamaps_contracts::*;
use patamaps_core::*;
use std::{cell::Cell, time::Duration};

const KIND: &str = "consumer:requires-locator";
const SUBJECT: &str = "urn:example:handler:create-user";

fn fixture() -> (CheckedGraph, PolicyDocument) {
    let graph = parse(include_bytes!("../../../fixtures/routing/graph.json")).unwrap();
    let packs = vec![
        parse(include_bytes!("../../../relation-packs/core.json")).unwrap(),
        parse(include_bytes!("../../../relation-packs/routing.json")).unwrap(),
    ];
    let graph = CheckedGraph::check(graph, packs).unwrap();
    let mut policy: PolicyDocument =
        parse(include_bytes!("../../../fixtures/routing/policy.json")).unwrap();
    policy.constraints.push(Constraint {
        id: "urn:constraint:native-locator".into(),
        kind: KIND.into(),
        subjects: vec![SUBJECT.into()],
        parameters: None,
    });
    (graph, policy)
}
fn options() -> EvaluationOptions {
    EvaluationOptions {
        context: JsonObject::from_iter([("environment".into(), "test".into())]),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
    }
}
fn control() -> WorkControl {
    WorkControl::new(
        CancellationToken::default(),
        Duration::from_secs(60),
        100_000,
    )
}
fn binding(version: &str) -> ContentBinding {
    ContentBinding {
        id: "urn:evaluator:consumer-locator".into(),
        digest: canonical_digest(&version).unwrap(),
    }
}
fn pass(_: &Constraint, _: &ConstraintEvaluationContext<'_>) -> Result<Vec<Issue>, CheckError> {
    Ok(vec![])
}
fn refuse(error: CheckError, code: &str) {
    assert!(error.0.iter().any(|i| i.code == code), "{error:?}");
}

#[test]
fn native_evaluator_reads_immutable_inputs_and_controls_real_policy_outcomes() {
    let (graph, policy) = fixture();
    let before = canonical_digest(&(graph.document(), &policy)).unwrap();
    let called = Cell::new(0);
    let mut registry = ConstraintRegistry::new();
    registry
        .register(
            KIND,
            binding("1"),
            |c: &Constraint, context: &ConstraintEvaluationContext<'_>| {
                called.set(called.get() + 1);
                context.poll()?;
                assert_eq!(context.context()["environment"], "test");
                assert_eq!(context.evaluated_at(), "2026-10-10T12:00:00Z");
                assert_eq!(context.policy().id, policy.id);
                assert_eq!(context.evidence().len(), policy.evidence.len());
                assert!(context.active("urn:example:mapping:create-user-handler"));
                let entity = context.graph().entity(&c.subjects[0]).unwrap();
                Ok(if entity.locators.as_ref().is_some_and(|v| !v.is_empty()) {
                    vec![]
                } else {
                    vec![Issue::error(
                        &format!("{KIND}:MISSING_LOCATOR"),
                        "A handler needs an owned locator",
                        &entity.id,
                    )]
                })
            },
        )
        .unwrap();
    let generation =
        admit_with_constraints(&graph, &policy, options(), &registry, &control()).unwrap();
    assert_eq!(called.get(), 1);
    assert_eq!(
        before,
        canonical_digest(&(graph.document(), &policy)).unwrap()
    );
    assert_eq!(
        generation.record().custom_constraint_evaluators,
        [ConstraintEvaluatorBinding {
            kind: KIND.into(),
            evaluator: binding("1")
        }]
    );

    let mut document = graph.document().clone();
    document
        .entities
        .iter_mut()
        .find(|e| e.id == SUBJECT)
        .unwrap()
        .locators = None;
    let changed = CheckedGraph::check(document, graph.packs().to_vec()).unwrap();
    refuse(
        admit_with_constraints(&changed, &policy, options(), &registry, &control()).unwrap_err(),
        &format!("{KIND}:MISSING_LOCATOR"),
    );
}

#[test]
fn missing_registration_cannot_create_admission_and_unused_extensions_do_not_change_it() {
    let (graph, mut policy) = fixture();
    refuse(
        admit(&graph, &policy, options()).unwrap_err(),
        "UNKNOWN_CONSTRAINT_KIND",
    );
    refuse(
        admit_with_constraints(
            &graph,
            &policy,
            options(),
            &ConstraintRegistry::new(),
            &control(),
        )
        .unwrap_err(),
        "UNKNOWN_CONSTRAINT_KIND",
    );
    policy.constraints.pop();
    let ordinary = admit(&graph, &policy, options()).unwrap();
    let mut registry = ConstraintRegistry::new();
    registry.register(KIND, binding("unused"), pass).unwrap();
    let extended =
        admit_with_constraints(&graph, &policy, options(), &registry, &control()).unwrap();
    assert_eq!(
        canonical_bytes(ordinary.record()).unwrap(),
        canonical_bytes(extended.record()).unwrap()
    );
    assert!(
        serde_json::to_value(extended.record())
            .unwrap()
            .get("customConstraintEvaluators")
            .is_none()
    );
}

#[test]
fn registration_refuses_builtin_replacement_duplicates_and_invalid_bindings() {
    let mut registry = ConstraintRegistry::new();
    for kind in [
        "core:requires-mapping",
        "core:requires-evidence",
        "core:requires-authority",
        "topology:reachable",
        "topology:relation-totality",
        "topology:context-satisfied",
    ] {
        assert_eq!(
            registry.register(kind, binding("1"), pass),
            Err(ConstraintRegistryError::BuiltinKind)
        );
    }
    assert_eq!(
        registry.register("", binding("1"), pass),
        Err(ConstraintRegistryError::InvalidKind)
    );
    for (id, digest) in [
        ("", binding("1").digest),
        ("urn:evaluator:x", "sha256:bad".into()),
        ("urn:evaluator:x", format!("sha256:{}", "A".repeat(64))),
    ] {
        assert_eq!(
            registry.register(
                KIND,
                ContentBinding {
                    id: id.into(),
                    digest
                },
                pass
            ),
            Err(ConstraintRegistryError::InvalidBinding)
        );
    }
    registry.register(KIND, binding("1"), pass).unwrap();
    assert_eq!(
        registry.register(KIND, binding("2"), pass),
        Err(ConstraintRegistryError::DuplicateKind)
    );
    assert_eq!(registry.binding(KIND).unwrap().evaluator, binding("1"));
    for i in 1..128 {
        registry
            .register(format!("consumer:kind-{i}"), binding("1"), pass)
            .unwrap();
    }
    assert_eq!(
        registry.register("consumer:overflow", binding("1"), pass),
        Err(ConstraintRegistryError::ResourceLimit)
    );
}

#[test]
fn used_implementation_binding_changes_the_address_and_order_is_canonical() {
    let (graph, mut policy) = fixture();
    let mut original = ConstraintRegistry::new();
    original.register(KIND, binding("1"), pass).unwrap();
    let mut revised = ConstraintRegistry::new();
    revised.register(KIND, binding("2"), pass).unwrap();
    let first = admit_with_constraints(&graph, &policy, options(), &original, &control()).unwrap();
    let second = admit_with_constraints(&graph, &policy, options(), &revised, &control()).unwrap();
    assert_ne!(first.record().digest, second.record().digest);
    let other = "consumer:another";
    policy.constraints.push(Constraint {
        id: "urn:constraint:another".into(),
        kind: other.into(),
        subjects: vec![SUBJECT.into()],
        parameters: None,
    });
    revised.register(other, binding("another"), pass).unwrap();
    let generation =
        admit_with_constraints(&graph, &policy, options(), &revised, &control()).unwrap();
    assert_eq!(
        generation
            .record()
            .custom_constraint_evaluators
            .iter()
            .map(|v| v.kind.as_str())
            .collect::<Vec<_>>(),
        [other, KIND]
    );
}

#[test]
fn callbacks_cannot_override_stale_bindings_or_missing_declarations() {
    let (graph, mut policy) = fixture();
    let called = Cell::new(false);
    let mut registry = ConstraintRegistry::new();
    registry
        .register(
            KIND,
            binding("1"),
            |_: &Constraint, _: &ConstraintEvaluationContext<'_>| {
                called.set(true);
                Ok(vec![])
            },
        )
        .unwrap();
    policy.graph.revision = Some("stale".into());
    refuse(
        admit_with_constraints(&graph, &policy, options(), &registry, &control()).unwrap_err(),
        "GRAPH_REVISION_MISMATCH",
    );
    assert!(!called.get());
    policy.graph.revision = Some("1".into());
    policy.mappings.pop();
    refuse(
        admit_with_constraints(&graph, &policy, options(), &registry, &control()).unwrap_err(),
        "MAPPING_POLICY_MISSING",
    );
}

#[test]
fn invalid_findings_and_pretended_waivers_never_become_admission() {
    let (graph, policy) = fixture();
    let ordinary = Issue::error(&format!("{KIND}:REFUSED"), "Custom refusal", SUBJECT);
    let mut spoof = ordinary.clone();
    spoof.code = "REQUIRED_MAPPING_MISSING".into();
    let mut waived = ordinary.clone();
    waived.waived_by = Some("urn:waiver:fake".into());
    let mut unknown = ordinary.clone();
    unknown.subject_id = Some("urn:missing".into());
    let mut huge = ordinary.clone();
    huge.message = "x".repeat(8193);
    for finding in [spoof, waived, unknown, huge] {
        let mut registry = ConstraintRegistry::new();
        registry
            .register(
                KIND,
                binding("1"),
                move |_: &Constraint, _: &ConstraintEvaluationContext<'_>| {
                    Ok(vec![finding.clone()])
                },
            )
            .unwrap();
        refuse(
            admit_with_constraints(&graph, &policy, options(), &registry, &control()).unwrap_err(),
            "CUSTOM_CONSTRAINT_INVALID_FINDING",
        );
    }
    let mut registry = ConstraintRegistry::new();
    registry
        .register(
            KIND,
            binding("1"),
            move |_: &Constraint, _: &ConstraintEvaluationContext<'_>| Ok(vec![ordinary.clone()]),
        )
        .unwrap();
    let mut waived_policy = policy.clone();
    waived_policy.waivers = Some(vec![parse(&canonical_bytes(&serde_json::json!({"id":"urn:waiver:attempt","codes":[format!("{KIND}:REFUSED")],"subjects":[SUBJECT],"reason":"Attempt to suppress a custom finding","assertedBy":"caller","expiresAt":"2099-01-01T00:00:00Z"})).unwrap()).unwrap()]);
    let error = admit_with_constraints(&graph, &waived_policy, options(), &registry, &control())
        .unwrap_err();
    assert!(
        error
            .0
            .iter()
            .any(|i| i.code == format!("{KIND}:REFUSED") && i.waived_by.is_none())
    );
    refuse(error, "INVALID_WAIVER");
}

#[test]
fn failures_panics_and_over_limit_warnings_refuse_instead_of_minting_checked_state() {
    let (graph, policy) = fixture();
    let mut registry = ConstraintRegistry::new();
    registry
        .register(
            KIND,
            binding("1"),
            |_: &Constraint, _: &ConstraintEvaluationContext<'_>| Err(CheckError(vec![])),
        )
        .unwrap();
    refuse(
        admit_with_constraints(&graph, &policy, options(), &registry, &control()).unwrap_err(),
        "CUSTOM_CONSTRAINT_EVALUATION_FAILED",
    );
    let mut registry = ConstraintRegistry::new();
    registry
        .register(
            KIND,
            binding("1"),
            |_: &Constraint,
             _: &ConstraintEvaluationContext<'_>|
             -> Result<Vec<Issue>, CheckError> {
                panic!("Host evaluator fixture panic")
            },
        )
        .unwrap();
    refuse(
        admit_with_constraints(&graph, &policy, options(), &registry, &control()).unwrap_err(),
        "CUSTOM_CONSTRAINT_EVALUATION_PANICKED",
    );
    let mut registry = ConstraintRegistry::new();
    registry
        .register(
            KIND,
            binding("1"),
            |_: &Constraint, _: &ConstraintEvaluationContext<'_>| {
                let mut warning = Issue::error(&format!("{KIND}:WARNING"), "A warning", SUBJECT);
                warning.severity = Severity::Warning;
                Ok(vec![warning; 129])
            },
        )
        .unwrap();
    refuse(
        admit_with_constraints(&graph, &policy, options(), &registry, &control()).unwrap_err(),
        "CUSTOM_CONSTRAINT_FINDING_LIMIT",
    );
}

#[test]
fn cancellation_before_and_during_callback_and_late_return_cannot_admit() {
    let (graph, policy) = fixture();
    let token = CancellationToken::default();
    let controls = WorkControl::new(token.clone(), Duration::from_secs(60), 100_000);
    let called = Cell::new(false);
    let mut registry = ConstraintRegistry::new();
    registry
        .register(
            KIND,
            binding("1"),
            |_: &Constraint, _: &ConstraintEvaluationContext<'_>| {
                called.set(true);
                token.cancel();
                Ok(vec![])
            },
        )
        .unwrap();
    refuse(
        admit_with_constraints(&graph, &policy, options(), &registry, &controls).unwrap_err(),
        "WORK_CANCELLED",
    );
    assert!(called.get());
    called.set(false);
    refuse(
        admit_with_constraints(&graph, &policy, options(), &registry, &controls).unwrap_err(),
        "WORK_CANCELLED",
    );
    assert!(!called.get());
    let mut registry = ConstraintRegistry::new();
    registry
        .register(
            KIND,
            binding("1"),
            |_: &Constraint, _: &ConstraintEvaluationContext<'_>| {
                std::thread::sleep(Duration::from_millis(150));
                Ok(vec![])
            },
        )
        .unwrap();
    let controls = WorkControl::new(
        CancellationToken::default(),
        Duration::from_millis(100),
        100_000,
    );
    refuse(
        admit_with_constraints(&graph, &policy, options(), &registry, &controls).unwrap_err(),
        "WORK_ELAPSED_LIMIT",
    );
}
