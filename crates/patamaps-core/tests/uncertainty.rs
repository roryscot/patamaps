use patamaps_contracts::*;
use patamaps_core::*;
use serde_json::json;

fn fixture() -> (
    GraphDocument,
    RelationPack,
    CompositionRequest,
    PolicyDocument,
) {
    (
        parse(include_bytes!("../package-inputs/fixtures/laws/graph.json")).unwrap(),
        parse(include_bytes!("../package-inputs/fixtures/laws/pack.json")).unwrap(),
        parse(include_bytes!(
            "../package-inputs/fixtures/laws/request.json"
        ))
        .unwrap(),
        parse(include_bytes!(
            "../package-inputs/fixtures/laws/policy.json"
        ))
        .unwrap(),
    )
}
fn assess(
    r: &mut CompositionRequest,
    subject: &str,
    d: UncertaintyDimension,
    status: UncertaintyStatus,
    result: EvidenceResult,
    model: Option<&str>,
) {
    let n = r.assessments.len();
    let eid = format!("urn:evidence:{n}");
    r.evidence.push(parse(&canonical_bytes(&json!({"id":eid,"subjects":[subject],"kind":format!("uncertainty:{}",d.as_str()),"result":result,"producer":"source-owner","confidence":0.99})).unwrap()).unwrap());
    r.assessments.push(UncertaintyAssessment {
        id: format!("urn:assessment:{n}"),
        subject: subject.into(),
        dimension: d,
        status,
        evidence: vec![eid],
        assessor: "recorded-assessor".into(),
        source_revision: "1".into(),
        measurement_model: model.map(str::to_owned),
        not_applicable_reason: (status == UncertaintyStatus::NotApplicable)
            .then(|| "This dimension does not apply to this declared subject".into()),
    });
}
fn install(
    g: &mut GraphDocument,
    p: &mut PolicyDocument,
    r: &CompositionRequest,
    pack: &RelationPack,
) -> CorrespondenceDerivation {
    let checked = CheckedGraph::check(g.clone(), vec![pack.clone()]).unwrap();
    let proposed = derive(&checked, r);
    assert_eq!(
        proposed.status,
        DerivationStatus::Proposed,
        "{:?}",
        proposed.issues
    );
    let proof = proposed.derivation.unwrap();
    g.mappings.push(proposed.mapping.unwrap());
    let s = p.semantics.as_mut().unwrap();
    s.derivations = vec![proof.clone()];
    s.assessments = r.assessments.clone();
    p.evidence = r.evidence.clone();
    proof
}
fn requirement(p: &mut PolicyDocument, states: Vec<UncertaintyStatus>, evidence: bool) {
    p.semantics
        .as_mut()
        .unwrap()
        .uncertainty_requirements
        .push(UncertaintyRequirement {
            id: "urn:requirement:identity".into(),
            select: MappingSelector {
                ids: Some(vec!["urn:m:ac".into()]),
                ..Default::default()
            },
            dimension: UncertaintyDimension::Identity,
            allowed_states: states,
            require_evidence: evidence,
        });
}
fn compile(g: GraphDocument, p: &PolicyDocument, pack: RelationPack) -> Result<(), CheckError> {
    let g = CheckedGraph::check(g, vec![pack]).unwrap();
    admit(
        &g,
        p,
        EvaluationOptions {
            context: fixture().2.context,
            evaluated_at: "2026-10-10T12:00:00Z".into(),
        },
    )
    .map(|_| ())
}

#[test]
fn six_dimensions_propagate_independently_without_scalar_confidence_upgrades() {
    for dimension in UNCERTAINTY_DIMENSIONS {
        let (mut g, pack, mut r, mut p) = fixture();
        for id in ["urn:m:ab", "urn:m:bc"] {
            assess(
                &mut r,
                id,
                dimension,
                UncertaintyStatus::Supported,
                EvidenceResult::Supports,
                None,
            );
        }
        let proof = install(&mut g, &mut p, &r, &pack);
        assert_eq!(
            proof
                .uncertainty
                .iter()
                .find(|d| d.dimension == dimension)
                .unwrap()
                .status,
            UncertaintyStatus::Supported
        );
        assert!(
            proof
                .uncertainty
                .iter()
                .filter(|d| d.dimension != dimension)
                .all(|d| d.status == UncertaintyStatus::Unknown)
        );
        assert!(compile(g, &p, pack).is_ok());
    }
    let (mut g, pack, r, mut p) = fixture();
    g.mappings[0].provenance.confidence = Some(1.0);
    let proof = install(&mut g, &mut p, &r, &pack);
    assert!(
        proof
            .uncertainty
            .iter()
            .all(|d| d.status == UncertaintyStatus::Unknown)
    );
}

#[test]
fn shared_evidence_is_deduplicated_and_full_values_bind_the_proof() {
    let (mut g, pack, mut r, mut p) = fixture();
    assess(
        &mut r,
        "urn:b",
        UncertaintyDimension::Identity,
        UncertaintyStatus::Supported,
        EvidenceResult::Supports,
        None,
    );
    r.evidence[0].digest = Some(format!("sha256:{}", "a".repeat(64)));
    let proof = install(&mut g, &mut p, &r, &pack);
    let u = &proof.uncertainty[0];
    assert_eq!(u.evidence, ["urn:evidence:0"]);
    assert_eq!(u.assessments, ["urn:assessment:0"]);
    let binding = proof
        .dependencies
        .iter()
        .find(|d| d.id == "urn:evidence:0")
        .unwrap();
    assert_eq!(binding.digest, canonical_digest(&r.evidence[0]).unwrap());
    assert_ne!(Some(binding.digest.clone()), r.evidence[0].digest);
    p.evidence[0].producer = "changed-producer".into();
    let e = compile(g, &p, pack).unwrap_err();
    assert!(
        e.0.iter()
            .any(|i| i.code == "DERIVATION_PREMISE_OR_RULE_MISMATCH")
    );
}

#[test]
fn tolerant_and_strict_requirements_differ_and_direct_support_cannot_erase_unknown() {
    let (mut g, pack, mut r, mut p) = fixture();
    assess(
        &mut r,
        "urn:m:ab",
        UncertaintyDimension::Identity,
        UncertaintyStatus::Supported,
        EvidenceResult::Supports,
        None,
    );
    assess(
        &mut r,
        "urn:m:ac",
        UncertaintyDimension::Identity,
        UncertaintyStatus::Supported,
        EvidenceResult::Supports,
        None,
    );
    let proof = install(&mut g, &mut p, &r, &pack);
    assert_eq!(proof.uncertainty[0].status, UncertaintyStatus::Unknown);
    requirement(
        &mut p,
        vec![UncertaintyStatus::Supported, UncertaintyStatus::Unknown],
        false,
    );
    assert!(compile(g.clone(), &p, pack.clone()).is_ok());
    p.semantics.as_mut().unwrap().uncertainty_requirements[0].allowed_states =
        vec![UncertaintyStatus::Supported];
    let e = compile(g, &p, pack).unwrap_err();
    assert!(e.0.iter().any(|i| i.code == "UNCERTAINTY_STATE_NOT_ALLOWED"
        && i.subject_id.as_deref() == Some("urn:m:ac")));
}

#[test]
fn typed_contradiction_and_inconclusive_evidence_remain_visible() {
    for (result, state) in [
        (EvidenceResult::Contradicts, UncertaintyStatus::Contradicted),
        (EvidenceResult::Inconclusive, UncertaintyStatus::Unknown),
    ] {
        let (mut g, pack, mut r, mut p) = fixture();
        assess(
            &mut r,
            "urn:m:ab",
            UncertaintyDimension::Identity,
            UncertaintyStatus::Supported,
            result,
            None,
        );
        assess(
            &mut r,
            "urn:m:bc",
            UncertaintyDimension::Identity,
            UncertaintyStatus::Supported,
            EvidenceResult::Supports,
            None,
        );
        assess(
            &mut r,
            "urn:m:ac",
            UncertaintyDimension::Identity,
            UncertaintyStatus::Supported,
            EvidenceResult::Supports,
            None,
        );
        let proof = install(&mut g, &mut p, &r, &pack);
        assert_eq!(proof.uncertainty[0].status, state);
        requirement(&mut p, vec![state], true);
        assert!(compile(g, &p, pack).is_ok());
    }
}

#[test]
fn incompatible_models_and_not_applicable_contributors_cannot_be_hidden() {
    let (mut g, pack, mut r, mut p) = fixture();
    assess(
        &mut r,
        "urn:m:ab",
        UncertaintyDimension::Identity,
        UncertaintyStatus::Supported,
        EvidenceResult::Supports,
        Some("urn:model:first"),
    );
    assess(
        &mut r,
        "urn:m:bc",
        UncertaintyDimension::Identity,
        UncertaintyStatus::Supported,
        EvidenceResult::Supports,
        Some("urn:model:second"),
    );
    let proof = install(&mut g, &mut p, &r, &pack);
    assert_eq!(proof.uncertainty[0].status, UncertaintyStatus::Unknown);
    assert_eq!(proof.uncertainty[0].measurement_models.len(), 2);
    let (mut g, pack, mut r, mut p) = fixture();
    assess(
        &mut r,
        "urn:m:ab",
        UncertaintyDimension::Identity,
        UncertaintyStatus::NotApplicable,
        EvidenceResult::Supports,
        None,
    );
    assess(
        &mut r,
        "urn:m:bc",
        UncertaintyDimension::Identity,
        UncertaintyStatus::Supported,
        EvidenceResult::Supports,
        None,
    );
    install(&mut g, &mut p, &r, &pack);
    requirement(&mut p, vec![UncertaintyStatus::Supported], true);
    assert!(
        compile(g, &p, pack)
            .unwrap_err()
            .0
            .iter()
            .any(|i| i.code == "UNCERTAINTY_NOT_APPLICABLE_NOT_ALLOWED")
    );
}

#[test]
fn stale_scope_missing_evidence_and_unreasoned_not_applicable_refuse() {
    for mutation in 0..4 {
        let (g, pack, mut r, _) = fixture();
        assess(
            &mut r,
            "urn:m:ab",
            UncertaintyDimension::Identity,
            UncertaintyStatus::Supported,
            EvidenceResult::Supports,
            None,
        );
        let code = match mutation {
            0 => {
                r.assessments[0].source_revision = "stale".into();
                "ASSESSMENT_REVISION_MISMATCH"
            }
            1 => {
                r.evidence.clear();
                "MISSING_UNCERTAINTY_EVIDENCE"
            }
            2 => {
                r.evidence[0].subjects = vec!["urn:m:bc".into()];
                "UNCERTAINTY_EVIDENCE_SCOPE_MISMATCH"
            }
            _ => {
                r.assessments[0].status = UncertaintyStatus::NotApplicable;
                "INVALID_UNCERTAINTY_ASSESSMENT"
            }
        };
        let outcome = derive(&CheckedGraph::check(g, vec![pack]).unwrap(), &r);
        assert_eq!(outcome.status, DerivationStatus::Rejected);
        assert!(
            outcome.issues.iter().any(|i| i.code == code),
            "{:?}",
            outcome.issues
        );
    }
}
