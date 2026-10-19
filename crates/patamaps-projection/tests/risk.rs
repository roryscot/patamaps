use patamaps_contracts::*;
use patamaps_core::*;
use patamaps_projection::*;
use serde_json::json;

fn initial() -> (GraphDocument, RelationPack, PolicyDocument, ProjectionSpec) {
    let mut g: GraphDocument =
        parse(include_bytes!("../package-inputs/fixtures/laws/graph.json")).unwrap();
    let pack: RelationPack =
        parse(include_bytes!("../package-inputs/fixtures/laws/pack.json")).unwrap();
    let r: CompositionRequest = parse(include_bytes!(
        "../package-inputs/fixtures/laws/request.json"
    ))
    .unwrap();
    let result = derive(
        &CheckedGraph::check(g.clone(), vec![pack.clone()]).unwrap(),
        &r,
    );
    assert_eq!(result.status, DerivationStatus::Proposed);
    g.mappings.push(result.mapping.unwrap());
    let mut p: PolicyDocument = parse(include_bytes!(
        "../package-inputs/fixtures/laws/policy.json"
    ))
    .unwrap();
    let s = p.semantics.as_mut().unwrap();
    s.derivations.push(result.derivation.unwrap());
    let budget:ConsumerRiskBudget=parse(&canonical_bytes(&json!({"id":"urn:budget:example","consumer":"urn:consumer:example","maximumTotalCost":5,"requireCompleteClassification":true,"requireCompleteDependencies":true,"classifications":[{"id":"urn:cost:ab","select":{"ids":["urn:m:ab"]},"classification":"recorded-source","cost":2},{"id":"urn:cost:bc","select":{"ids":["urn:m:bc"]},"classification":"recorded-source","cost":3},{"id":"urn:cost:ac","select":{"ids":["urn:m:ac"]},"classification":"explicit-inference","cost":0}]})).unwrap()).unwrap();
    s.risk_budgets.push(budget);
    let mut spec: ProjectionSpec = parse(include_bytes!(
        "../package-inputs/fixtures/laws/projection-spec.json"
    ))
    .unwrap();
    spec.semantics.as_mut().unwrap().budget = Some("urn:budget:example".into());
    (g, pack, p, spec)
}
fn options() -> EvaluationOptions {
    EvaluationOptions {
        context: JsonObject::from([("environment".into(), "test".into())]),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
    }
}
fn link(
    g: GraphDocument,
    pack: RelationPack,
    p: &PolicyDocument,
    spec: &ProjectionSpec,
) -> Result<CheckedProjection, CheckError> {
    let g = CheckedGraph::check(g, vec![pack]).unwrap();
    let generation = admit(&g, p, options())?;
    project(&generation, spec)
}
fn code(e: CheckError, code: &str) {
    assert!(
        e.0.iter().any(|i| i.code == code),
        "wanted {code}; found {:?}",
        e.0
    );
}

#[test]
fn exact_unique_budget_boundaries_and_repeated_slots_cost_once() {
    let (g, pack, mut p, mut spec) = initial();
    for limit in [4, 5, 6] {
        p.semantics.as_mut().unwrap().risk_budgets[0].maximum_total_cost =
            SafeInteger::new(limit).unwrap();
        let result = link(g.clone(), pack.clone(), &p, &spec);
        if limit == 4 {
            code(result.unwrap_err(), "CONSUMER_RISK_BUDGET_EXCEEDED");
        } else {
            let result = result.unwrap();
            let semantic = result.record().semantics.as_ref().unwrap();
            assert_eq!(semantic.used_mappings, ["urn:m:ab", "urn:m:ac", "urn:m:bc"]);
            assert_eq!(semantic.risk.total_cost.unwrap().get(), 5);
            assert_eq!(semantic.risk.classifications.len(), 3);
            assert_eq!(semantic.derivations.len(), 1);
        }
    }
    spec.slots.push(SlotSpec {
        name: "second-name".into(),
        ..spec.slots[0].clone()
    });
    let result = link(g, pack, &p, &spec).unwrap();
    let risk = &result.record().semantics.as_ref().unwrap().risk;
    assert_eq!(risk.total_cost.unwrap().get(), 5);
    assert_eq!(risk.classifications.len(), 3);
}

#[test]
fn branching_proofs_reuse_a_shared_proof_and_mapping_closure_once() {
    let (mut g, mut pack, mut p, mut spec) = initial();
    g.mappings.truncate(2);
    let mut law = pack.laws.as_ref().unwrap()[0].clone();
    law.id = "urn:law:follow-t".into();
    law.operands = vec!["example:t".into(), "example:s".into()];
    pack.laws.as_mut().unwrap().push(law);
    let mut request: CompositionRequest = parse(include_bytes!(
        "../package-inputs/fixtures/laws/request.json"
    ))
    .unwrap();
    let first = derive(
        &CheckedGraph::check(g.clone(), vec![pack.clone()]).unwrap(),
        &request,
    );
    assert_eq!(first.status, DerivationStatus::Proposed);
    g.mappings.push(first.mapping.unwrap());
    let mut proofs = vec![first.derivation.unwrap()];
    for (id, target) in [("urn:m:cd", "urn:d"), ("urn:m:cb", "urn:b")] {
        let mut m = g.mappings[1].clone();
        m.id = id.into();
        m.sources = vec!["urn:c".into()];
        m.targets = vec![target.into()];
        g.mappings.push(m);
    }
    for (premise, result_id) in [("urn:m:cd", "urn:m:ad"), ("urn:m:cb", "urn:m:ab-derived")] {
        request.law = "urn:law:follow-t".into();
        request.premises = vec!["urn:m:ac".into(), premise.into()];
        request.result_id = Some(result_id.into());
        request.derivations = proofs.clone();
        let result = derive(
            &CheckedGraph::check(g.clone(), vec![pack.clone()]).unwrap(),
            &request,
        );
        assert_eq!(
            result.status,
            DerivationStatus::Proposed,
            "{:?}",
            result.issues
        );
        let proof = result.derivation.unwrap();
        assert_eq!(proof.depth.get(), 2);
        assert_eq!(proof.derivation_count.get(), 2);
        g.mappings.push(result.mapping.unwrap());
        proofs.push(proof);
    }
    let s = p.semantics.as_mut().unwrap();
    s.derivations = proofs;
    let b = &mut s.risk_budgets[0];
    b.maximum_total_cost = SafeInteger::new(14).unwrap();
    b.classifications = g
        .mappings
        .iter()
        .map(|m| RiskClassification {
            id: format!("urn:cost:{}", m.id),
            select: MappingSelector {
                ids: Some(vec![m.id.clone()]),
                ..Default::default()
            },
            classification: "explicit".into(),
            cost: SafeInteger::new(match m.id.as_str() {
                "urn:m:ab" => 2,
                "urn:m:bc" => 3,
                "urn:m:cd" => 4,
                "urn:m:cb" => 5,
                _ => 0,
            })
            .unwrap(),
        })
        .collect();
    spec.slots[0].cardinality = SlotCardinality::Many;
    let result = link(g.clone(), pack.clone(), &p, &spec).unwrap();
    let semantics = result.record().semantics.as_ref().unwrap();
    assert_eq!(semantics.used_mappings.len(), 7);
    assert_eq!(semantics.derivations.len(), 3);
    assert_eq!(semantics.risk.total_cost.unwrap().get(), 14);
    p.semantics.as_mut().unwrap().derivation_limits.max_depth = SafeInteger::new(1).unwrap();
    code(link(g, pack, &p, &spec).unwrap_err(), "DERIVATION_LIMIT");
}

#[test]
fn missing_overlapping_and_overflowing_classifications_refuse() {
    let (g, pack, p, spec) = initial();
    let mut missing = p.clone();
    missing.semantics.as_mut().unwrap().risk_budgets[0]
        .classifications
        .pop();
    code(
        link(g.clone(), pack.clone(), &missing, &spec).unwrap_err(),
        "MISSING_RISK_CLASSIFICATION",
    );
    let mut overlap = p.clone();
    let b = &mut overlap.semantics.as_mut().unwrap().risk_budgets[0];
    let mut rule = b.classifications[0].clone();
    rule.id = "urn:cost:overlap".into();
    b.classifications.push(rule);
    code(
        link(g.clone(), pack.clone(), &overlap, &spec).unwrap_err(),
        "AMBIGUOUS_RISK_CLASSIFICATION",
    );
    let mut overflow = p;
    let b = &mut overflow.semantics.as_mut().unwrap().risk_budgets[0];
    b.maximum_total_cost = SafeInteger::new(MAX_SAFE_INTEGER).unwrap();
    b.classifications[0].cost = SafeInteger::new(MAX_SAFE_INTEGER).unwrap();
    code(
        link(g, pack, &overflow, &spec).unwrap_err(),
        "RISK_COST_OVERFLOW",
    );
}

#[test]
fn a_consumer_cannot_disable_choose_another_budget_or_hide_unknown_cost() {
    let (g, pack, p, mut spec) = initial();
    let b = spec.semantics.as_ref().unwrap().budget.clone();
    spec.semantics.as_mut().unwrap().budget = None;
    code(
        link(g.clone(), pack.clone(), &p, &spec).unwrap_err(),
        "CONSUMER_BUDGET_REQUIRED",
    );
    spec.semantics.as_mut().unwrap().budget = b;
    spec.semantics.as_mut().unwrap().consumer = "urn:consumer:other".into();
    code(
        link(g.clone(), pack.clone(), &p, &spec).unwrap_err(),
        "CONSUMER_BUDGET_MISMATCH",
    );
    spec.semantics = None;
    code(
        link(g.clone(), pack.clone(), &p, &spec).unwrap_err(),
        "SEMANTIC_CONSUMER_REQUIRED",
    );
    let mut p = p;
    p.semantics.as_mut().unwrap().risk_budgets.clear();
    spec.semantics = Some(ProjectionRequirements {
        consumer: "urn:consumer:example".into(),
        budget: None,
    });
    let result = link(g, pack, &p, &spec).unwrap();
    let risk = &result.record().semantics.as_ref().unwrap().risk;
    assert_eq!(risk.status, "not-evaluated");
    assert!(risk.total_cost.is_none() && risk.budget.is_none());
}

#[test]
fn incomplete_opt_out_is_refused_and_unused_sources_are_not_charged() {
    let (mut g, pack, mut p, spec) = initial();
    let mut unused = g.mappings[1].clone();
    unused.id = "urn:m:unused".into();
    unused.sources = vec!["urn:d".into()];
    g.mappings.push(unused);
    let result = link(g.clone(), pack.clone(), &p, &spec).unwrap();
    assert_eq!(
        result
            .record()
            .semantics
            .as_ref()
            .unwrap()
            .risk
            .total_cost
            .unwrap()
            .get(),
        5
    );
    p.semantics.as_mut().unwrap().risk_budgets[0].require_complete_dependencies = false;
    code(
        link(g, pack, &p, &spec).unwrap_err(),
        "INVALID_CONSUMER_BUDGET",
    );
}

#[test]
fn unique_lossy_and_inferred_limits_include_the_premise_closure() {
    let (mut g, pack, mut p, mut spec) = initial();
    g.mappings.pop();
    g.mappings[0].lossiness = Lossiness::Lossy;
    p.mappings[0].reversibility = Reversibility::Irreversible;
    let r: CompositionRequest = parse(include_bytes!(
        "../package-inputs/fixtures/laws/request.json"
    ))
    .unwrap();
    let result = derive(
        &CheckedGraph::check(g.clone(), vec![pack.clone()]).unwrap(),
        &r,
    );
    g.mappings.push(result.mapping.unwrap());
    p.semantics.as_mut().unwrap().derivations = vec![result.derivation.unwrap()];
    spec.slots[0].allow_lossy = Some(true);
    p.semantics.as_mut().unwrap().risk_budgets[0].maximum_lossy_mappings =
        Some(SafeInteger::new(1).unwrap());
    code(
        link(g.clone(), pack.clone(), &p, &spec).unwrap_err(),
        "CONSUMER_LOSSY_LIMIT_EXCEEDED",
    );
    p.semantics.as_mut().unwrap().risk_budgets[0].maximum_lossy_mappings =
        Some(SafeInteger::new(2).unwrap());
    p.semantics.as_mut().unwrap().risk_budgets[0].maximum_inferred_mappings =
        Some(SafeInteger::new(0).unwrap());
    code(
        link(g.clone(), pack.clone(), &p, &spec).unwrap_err(),
        "CONSUMER_INFERRED_LIMIT_EXCEEDED",
    );
    p.semantics.as_mut().unwrap().risk_budgets[0].maximum_inferred_mappings =
        Some(SafeInteger::new(1).unwrap());
    assert!(link(g, pack, &p, &spec).is_ok());
}

fn captured(
    g: GraphDocument,
    pack: RelationPack,
    p: PolicyDocument,
    spec: ProjectionSpec,
) -> CaptureRecord {
    capture(
        CaptureInputs {
            projection_specs: vec![],
            graph: g,
            packs: vec![pack],
            policy: p,
            context: options().context,
            evaluated_at: options().evaluated_at,
            projection_spec: Some(spec),
        },
        vec![],
    )
    .unwrap()
}
#[test]
fn semantic_success_rejection_and_risk_delta_replay_offline() {
    let (g, pack, mut p, spec) = initial();
    let before = captured(g.clone(), pack.clone(), p.clone(), spec.clone());
    assert_eq!(before.result["status"], "viable");
    let decoded: CaptureRecord = parse(&canonical_bytes(&before).unwrap()).unwrap();
    replay(&decoded).unwrap();
    p.semantics.as_mut().unwrap().risk_budgets[0].classifications[0].cost =
        SafeInteger::new(1).unwrap();
    let after = captured(g.clone(), pack.clone(), p.clone(), spec.clone());
    let report = compare(&replay(&before).unwrap(), &replay(&after).unwrap()).unwrap();
    assert_eq!(report["riskDelta"]["totalCostChange"], -1);
    p.semantics.as_mut().unwrap().risk_budgets[0].maximum_total_cost = SafeInteger::new(3).unwrap();
    let rejected = captured(g, pack, p, spec);
    assert_eq!(rejected.result["status"], "rejected");
    replay(&rejected).unwrap();
    let report = compare(&replay(&after).unwrap(), &replay(&rejected).unwrap()).unwrap();
    assert!(report["riskDelta"].is_null());
    assert!(report["projectionChanged"].is_null());
}
