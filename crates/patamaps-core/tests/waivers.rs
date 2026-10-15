use patamaps_contracts::*;
use patamaps_core::*;

const CODES: [&str; 4] = [
    "UNDECLARED_LOSSINESS",
    "UNDECLARED_IMPACT_DIRECTION",
    "UNVERIFIED_DETERMINISM",
    "UNVERIFIED_REVERSIBILITY",
];

fn options() -> EvaluationOptions {
    EvaluationOptions {
        context: JsonObject::new(),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
    }
}

fn fixture(code: &str) -> (CheckedGraph, PolicyDocument, String) {
    let mut graph: GraphDocument =
        parse(include_bytes!("../../../fixtures/routing/graph.json")).unwrap();
    let mut policy: PolicyDocument =
        parse(include_bytes!("../../../fixtures/routing/policy.json")).unwrap();
    let mut packs: Vec<RelationPack> = vec![
        parse(include_bytes!("../../../relation-packs/core.json")).unwrap(),
        parse(include_bytes!("../../../relation-packs/routing.json")).unwrap(),
    ];
    let subject = graph.mappings[0].id.clone();
    match code {
        "UNDECLARED_LOSSINESS" => graph.mappings[0].lossiness = Lossiness::Unknown,
        "UNDECLARED_IMPACT_DIRECTION" => {
            packs[1]
                .relations
                .iter_mut()
                .find(|r| r.id == graph.mappings[0].relation)
                .unwrap()
                .impact_direction = None;
        }
        "UNVERIFIED_DETERMINISM" => {
            graph.mappings[0].transform = Some(
                parse(br#"{"adapter":"fixture","version":"1","deterministic":false}"#).unwrap(),
            );
        }
        "UNVERIFIED_REVERSIBILITY" => {
            policy.mappings[0].reversibility = Reversibility::Reversible;
            graph.mappings[0].transform = Some(parse(
                br#"{"adapter":"fixture","version":"1","deterministic":true,"reversible":false}"#
            ).unwrap());
        }
        _ => unreachable!(),
    }
    (CheckedGraph::check(graph, packs).unwrap(), policy, subject)
}

fn waiver(code: &str, subject: &str) -> Waiver {
    Waiver {
        id: "urn:waiver:bounded-migration".into(),
        codes: vec![code.into()],
        subjects: vec![subject.into()],
        reason: "Explicit temporary migration exception".into(),
        asserted_by: "team:architecture".into(),
        expires_at: "2026-10-11T12:00:00Z".into(),
    }
}

fn has(error: CheckError, code: &str) {
    assert!(error.0.iter().any(|i| i.code == code), "{code}: {error}");
}

#[test]
fn exact_ordinary_waivers_preserve_findings_and_original_graph_bytes() {
    for code in CODES {
        let (graph, mut policy, subject) = fixture(code);
        let original = canonical_bytes(graph.document()).unwrap();
        has(admit(&graph, &policy, options()).unwrap_err(), code);
        policy.waivers = Some(vec![waiver(code, &subject)]);
        let admitted = admit(&graph, &policy, options()).unwrap();
        let finding = admitted.issues().iter().find(|i| i.code == code).unwrap();
        assert_eq!(finding.severity, Severity::Warning, "{code}");
        assert_eq!(
            finding.subject_id.as_deref(),
            Some(subject.as_str()),
            "{code}"
        );
        assert_eq!(
            finding.waived_by.as_deref(),
            Some("urn:waiver:bounded-migration"),
            "{code}"
        );
        assert_eq!(
            admitted.record().waivers_applied,
            ["urn:waiver:bounded-migration"],
            "{code}"
        );
        assert_eq!(
            admitted.record().policy.digest,
            Some(canonical_digest(&policy).unwrap())
        );
        assert_eq!(
            canonical_bytes(graph.document()).unwrap(),
            original,
            "{code}"
        );
        assert_eq!(admitted.record().active_mappings.len(), 5, "{code}");
    }
}

#[test]
fn waiver_scope_and_expiry_cannot_cover_another_mapping_or_boundary_time() {
    for code in CODES {
        let (graph, mut policy, subject) = fixture(code);
        let other = &graph.document().mappings[1].id;
        policy.waivers = Some(vec![waiver(code, other)]);
        has(admit(&graph, &policy, options()).unwrap_err(), code);
        let mut expired = waiver(code, &subject);
        expired.expires_at = options().evaluated_at;
        policy.waivers = Some(vec![expired]);
        has(
            admit(&graph, &policy, options()).unwrap_err(),
            "EXPIRED_WAIVER",
        );
    }
}

#[test]
fn an_allowed_waiver_never_covers_missing_policy_or_protected_codes() {
    let (graph, mut policy, subject) = fixture("UNDECLARED_LOSSINESS");
    policy.waivers = Some(vec![waiver("UNDECLARED_LOSSINESS", &subject)]);
    policy.mappings.pop();
    has(
        admit(&graph, &policy, options()).unwrap_err(),
        "MAPPING_POLICY_MISSING",
    );
    let (graph, mut policy, subject) = fixture("UNDECLARED_LOSSINESS");
    let mut mixed = waiver("UNDECLARED_LOSSINESS", &subject);
    mixed.codes.push("UNKNOWN_CONSTRAINT_KIND".into());
    policy.waivers = Some(vec![mixed]);
    has(
        admit(&graph, &policy, options()).unwrap_err(),
        "INVALID_WAIVER",
    );
}
