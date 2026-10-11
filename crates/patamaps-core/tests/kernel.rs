use patamaps_contracts::*;
use patamaps_core::*;
use serde_json::json;

fn doc() -> GraphDocument {
    parse(include_bytes!("../../../fixtures/routing/graph.json")).unwrap()
}
fn policy() -> PolicyDocument {
    parse(include_bytes!("../../../fixtures/routing/policy.json")).unwrap()
}
fn packs() -> Vec<RelationPack> {
    vec![
        parse(include_bytes!("../../../relation-packs/core.json")).unwrap(),
        parse(include_bytes!("../../../relation-packs/routing.json")).unwrap(),
    ]
}
fn checked(doc: GraphDocument) -> CheckedGraph {
    CheckedGraph::check(doc, packs()).unwrap()
}
fn options() -> EvaluationOptions {
    EvaluationOptions {
        context: JsonObject::new(),
        evaluated_at: "2026-10-10T12:00:00Z".into(),
    }
}
fn has(error: CheckError, code: &str) {
    assert!(
        error.0.iter().any(|i| i.code == code),
        "wanted {code}; found {error}"
    );
}

#[test]
fn routing_is_usefully_admitted_with_fact_scoped_authority() {
    let graph = checked(doc());
    let policy = policy();
    let admitted = admit(&graph, &policy, options()).unwrap();
    assert_eq!(admitted.record().active_mappings.len(), 5);
    assert!(matches!(
        graph.resolve_authority("urn:example:command:create-user", "routing-identity"),
        AuthorityResolution::Resolved { .. }
    ));
    assert!(matches!(
        graph.resolve_authority("urn:example:command:create-user", "unowned-fact"),
        AuthorityResolution::Unresolved { .. }
    ));
    assert_eq!(
        graph
            .trace(
                "urn:example:command:create-user",
                Direction::Outgoing,
                1,
                &[]
            )
            .unwrap()
            .len(),
        6
    );
}

#[test]
fn duplicate_identity_dangling_endpoint_and_wrong_role_are_rejected() {
    let mut d = doc();
    d.entities.push(d.entities[0].clone());
    assert!(CheckedGraph::check(d, packs()).is_err());
    let mut d = doc();
    d.mappings[0].targets = vec!["urn:missing:target".into()];
    assert!(CheckedGraph::check(d, packs()).is_err());
    let mut d = doc();
    d.mappings[0].targets = vec![d.entities[0].id.clone()];
    assert!(CheckedGraph::check(d, packs()).is_err());
    let mut d = doc();
    d.mappings[0].sources.push(d.entities[1].id.clone());
    assert!(CheckedGraph::check(d, packs()).is_err());
}

#[test]
fn narrowing_delegation_resolves_but_widening_or_branch_conflict_fails() {
    let mut d = doc();
    d.authorities[0].facts.push("schema".into());
    let mut child = d.authorities[0].clone();
    child.id = "urn:authority:delegate".into();
    child.mode = AuthorityMode::Delegated;
    child.delegated_from = Some(d.authorities[0].id.clone());
    child.facts = vec!["routing-identity".into()];
    child.source = d.entities[1].id.clone();
    d.authorities.push(child.clone());
    let g = checked(d.clone());
    let resolution =
        serde_json::to_value(g.resolve_authority(&d.entities[0].id, "routing-identity")).unwrap();
    assert_eq!(resolution["effective"], child.id);
    let mut widened = d.clone();
    widened.authorities[1].facts.push("unowned".into());
    assert!(CheckedGraph::check(widened, packs()).is_err());
    let mut sibling = child;
    sibling.id = "urn:authority:sibling".into();
    d.authorities.push(sibling);
    assert!(CheckedGraph::check(d, packs()).is_err());
}

#[test]
fn canonical_conflict_candidate_ambiguity_and_delegation_cycle_are_distinct() {
    let mut d = doc();
    let mut a = d.authorities[0].clone();
    a.id = "urn:authority:other".into();
    d.authorities.push(a);
    assert!(CheckedGraph::check(d, packs()).is_err());
    let mut d = doc();
    d.authorities[0].mode = AuthorityMode::Candidate;
    let g = checked(d.clone());
    assert!(matches!(
        g.resolve_authority(&d.entities[0].id, "routing-identity"),
        AuthorityResolution::Ambiguous { .. }
    ));
    let mut a = d.authorities[0].clone();
    a.id = "urn:authority:second".into();
    d.authorities[0].mode = AuthorityMode::Delegated;
    d.authorities[0].delegated_from = Some(a.id.clone());
    a.mode = AuthorityMode::Delegated;
    a.delegated_from = Some(d.authorities[0].id.clone());
    d.authorities.push(a);
    assert!(CheckedGraph::check(d, packs()).is_err());
}

#[test]
fn nary_cycle_detection_does_not_reduce_endpoint_groups_to_one_pair() {
    let mut d = doc();
    d.relation_packs = None;
    d.authorities.clear();
    let mut a = d.mappings[0].clone();
    a.relation = "core:depends_on".into();
    a.cardinality = Cardinality::OneToMany;
    a.targets = vec![d.entities[1].id.clone(), d.entities[2].id.clone()];
    let mut b = a.clone();
    b.id = "urn:mapping:cycle".into();
    b.sources = vec![d.entities[2].id.clone()];
    b.targets = vec![d.entities[0].id.clone()];
    b.cardinality = Cardinality::OneToOne;
    d.mappings = vec![a, b];
    assert!(CheckedGraph::check(d, packs()).is_err());
}

#[test]
fn composition_deduplicates_equal_records_and_refuses_conflict() {
    let a = doc();
    let mut b = a.clone();
    b.id = "urn:graph:second".into();
    let merged = compose(
        &[a.clone(), b.clone()],
        "urn:graph:composed".into(),
        "composed".into(),
    )
    .unwrap();
    assert_eq!(merged.entities.len(), a.entities.len());
    assert!(CheckedGraph::check(merged, packs()).is_ok());
    b.entities[0].label = Some("different".into());
    assert!(compose(&[a, b], "urn:graph:composed".into(), "composed".into()).is_err());
}

#[test]
fn open_kind_names_and_shared_physical_locators_do_not_merge_identities() {
    let mut d = doc();
    d.entities[4].kind = "application endpoint (public)".into();
    d.entities[4].locators = d.entities[1].locators.clone();
    let mut local_packs = packs();
    local_packs[1]
        .relations
        .iter_mut()
        .find(|r| r.id == "routing:exposed_as")
        .unwrap()
        .target_kinds = None;
    let g = CheckedGraph::check(d.clone(), local_packs.clone()).unwrap();
    assert_ne!(g.document().entities[1].id, g.document().entities[4].id);
    let duplicate = d.entities[1].locators.clone().unwrap()[0].clone();
    d.entities[1].locators.as_mut().unwrap().push(duplicate);
    let g = CheckedGraph::check(d, local_packs).unwrap();
    assert!(
        g.issues()
            .iter()
            .any(|i| i.code == "DUPLICATE_LOCATOR" && i.severity == Severity::Warning)
    );
}

#[test]
fn sdk_metadata_cannot_bypass_ingress_resource_limits() {
    let mut d = doc();
    let mut nested = json!(true);
    for _ in 0..70 {
        nested = json!([nested]);
    }
    d.entities[0].attributes = Some([("deep".into(), nested)].into());
    has(
        CheckedGraph::check(d, packs()).unwrap_err(),
        "GRAPH_RESOURCE_LIMIT",
    );
}

#[test]
fn sdk_numeric_metadata_is_normalized_to_the_declared_binary64_domain() {
    let mut d = doc();
    d.entities[0].attributes = Some([("numeric".into(), json!(9_007_199_254_740_993u64))].into());
    let g = checked(d);
    assert_eq!(
        g.document().entities[0].attributes.as_ref().unwrap()["numeric"].as_f64(),
        Some(9_007_199_254_740_992.0)
    );
    assert!(g.document().entities[0].attributes.as_ref().unwrap()["numeric"].is_f64());
}

#[test]
fn duplicate_selector_values_and_deep_policy_metadata_refuse_admission() {
    let g = checked(doc());
    let mut p = policy();
    let id = p.mappings[0].mapping.take().unwrap();
    p.mappings[0].select = Some(MappingSelector {
        ids: Some(vec![id.clone(), id]),
        ..MappingSelector::default()
    });
    has(
        admit(&g, &p, options()).unwrap_err(),
        "INVALID_MAPPING_SELECTOR",
    );
    let mut p = policy();
    let mut nested = json!(true);
    for _ in 0..70 {
        nested = json!([nested]);
    }
    p.metadata = Some([("deep".into(), nested)].into());
    has(
        admit(&g, &p, options()).unwrap_err(),
        "POLICY_RESOURCE_LIMIT",
    );
}

#[test]
fn policy_coverage_unknown_operations_and_stale_graph_cannot_be_waived() {
    let g = checked(doc());
    let mut p = policy();
    p.mappings.pop();
    has(
        admit(&g, &p, options()).unwrap_err(),
        "MAPPING_POLICY_MISSING",
    );
    let mut p = policy();
    p.mappings.push(p.mappings[0].clone());
    has(
        admit(&g, &p, options()).unwrap_err(),
        "DUPLICATE_MAPPING_POLICY",
    );
    let mut p = policy();
    p.graph.revision = Some("stale".into());
    has(
        admit(&g, &p, options()).unwrap_err(),
        "GRAPH_REVISION_MISMATCH",
    );
    let mut p = policy();
    p.constraints[0].kind = "custom:assume_valid".into();
    has(
        admit(&g, &p, options()).unwrap_err(),
        "UNKNOWN_CONSTRAINT_KIND",
    );
    p.waivers = Some(vec![Waiver {
        id: "urn:waiver:unsupported".into(),
        codes: vec!["UNKNOWN_CONSTRAINT_KIND".into()],
        subjects: vec![p.constraints[0].id.clone()],
        reason: "bypass".into(),
        asserted_by: "agent".into(),
        expires_at: "2030-01-01T00:00:00Z".into(),
    }]);
    has(admit(&g, &p, options()).unwrap_err(), "INVALID_WAIVER");
}

#[test]
fn applicability_requires_context_and_preserves_inactive_mapping() {
    let g = checked(doc());
    let mut p = policy();
    p.mappings[4].applicability = Some(Applicability {
        when: Some(
            parse(br#"{"key":"environment","operator":"equals","value":"production"}"#).unwrap(),
        ),
        unless: None,
    });
    has(admit(&g, &p, options()).unwrap_err(), "CONTEXT_KEY_MISSING");
    let mut o = options();
    o.context.insert("environment".into(), json!("development"));
    let a = admit(&g, &p, o).unwrap();
    assert_eq!(a.record().active_mappings.len(), 4);
    assert_eq!(a.record().inactive_mappings.len(), 1);
}

#[test]
fn numeric_context_agrees_between_strict_ingress_and_typed_sdk_values() {
    let g = checked(doc());
    let mut p = policy();
    p.mappings[4].applicability = Some(Applicability {
        when: Some(parse(br#"{"key":"attempt","operator":"equals","value":1}"#).unwrap()),
        unless: None,
    });
    let mut o = options();
    o.context.insert("attempt".into(), json!(1));
    assert!(
        admit(&g, &p, o)
            .unwrap()
            .active(&g.document().mappings[4].id)
    );
}

#[test]
fn impact_preserves_origin_paths_and_reports_missing_information() {
    let g = checked(doc());
    let origin = g.document().entities[0].id.clone();
    let report = impact(&g, std::slice::from_ref(&origin), 64).unwrap();
    assert!(report.visits.iter().any(|v| {
        v.subject == g.document().entities[1].id
            && v.path
                .iter()
                .any(|s| s.mapping == g.document().mappings[0].id)
    }));
    let reverse = impact(&g, &[g.document().entities[1].id.clone()], 64).unwrap();
    assert!(
        !reverse
            .visits
            .iter()
            .any(|v| v.subject == g.document().entities[0].id)
    );
    let missing = impact(&g, &["urn:missing:origin".into()], 64).unwrap();
    assert!(!missing.complete);
    assert_eq!(missing.unavailable_origins.len(), 1);
}

#[test]
fn unknown_evidence_does_not_meet_support_and_waivers_expire_at_boundary() {
    let g = checked(doc());
    let mut p = policy();
    let id = g.document().entities[0].id.clone();
    p.constraints.push(Constraint {
        id: "urn:constraint:evidence".into(),
        kind: "core:requires-evidence".into(),
        subjects: vec![id.clone()],
        parameters: None,
    });
    p.evidence.push(Evidence {
        id: "urn:evidence:unknown".into(),
        kind: "test".into(),
        subjects: vec![id.clone()],
        result: EvidenceResult::Inconclusive,
        producer: "test".into(),
        observed_at: None,
        confidence: Some(1.0),
        locator: None,
        digest: None,
        attributes: None,
    });
    has(
        admit(&g, &p, options()).unwrap_err(),
        "REQUIRED_EVIDENCE_MISSING",
    );
    p.waivers = Some(vec![Waiver {
        id: "urn:waiver:evidence".into(),
        codes: vec!["REQUIRED_EVIDENCE_MISSING".into()],
        subjects: vec![id],
        reason: "bounded exception".into(),
        asserted_by: "owner".into(),
        expires_at: options().evaluated_at,
    }]);
    has(admit(&g, &p, options()).unwrap_err(), "EXPIRED_WAIVER");
    p.waivers.as_mut().unwrap()[0].expires_at = "2026-10-11T00:00:00Z".into();
    assert_eq!(
        admit(&g, &p, options())
            .unwrap()
            .record()
            .waivers_applied
            .len(),
        1
    );
}
