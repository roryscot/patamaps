use patamaps_contracts::*;
use patamaps_core::*;
use serde_json::{Value, json};

fn graph() -> GraphDocument {
    parse(include_bytes!("../../../fixtures/laws/graph.json")).unwrap()
}
fn pack() -> RelationPack {
    parse(include_bytes!("../../../fixtures/laws/pack.json")).unwrap()
}
fn request() -> CompositionRequest {
    parse(include_bytes!("../../../fixtures/laws/request.json")).unwrap()
}
fn policy() -> PolicyDocument {
    parse(include_bytes!("../../../fixtures/laws/policy.json")).unwrap()
}
fn checked(g: GraphDocument, p: RelationPack) -> CheckedGraph {
    CheckedGraph::check(g, vec![p]).unwrap()
}
fn options() -> EvaluationOptions {
    EvaluationOptions {
        context: request().context,
        evaluated_at: "2026-10-10T12:00:00Z".into(),
    }
}
fn issue(e: CheckError, code: &str) {
    assert!(
        e.0.iter().any(|i| i.code == code),
        "wanted {code}; found {:?}",
        e.0
    );
}
fn readdress(p: &mut CorrespondenceDerivation) {
    let mut v = serde_json::to_value(&*p).unwrap();
    let o = v.as_object_mut().unwrap();
    o.remove("id");
    o.remove("digest");
    p.digest = canonical_digest(&v).unwrap();
    p.id = format!("urn:patamaps:derivation:{}", &p.digest[7..]);
}
fn admitted_fixture() -> (GraphDocument, PolicyDocument, CorrespondenceDerivation) {
    let mut g = graph();
    let before = canonical_digest(&g).unwrap();
    let checked = checked(g.clone(), pack());
    let result = derive(&checked, &request());
    assert_eq!(
        result.status,
        DerivationStatus::Proposed,
        "{:?}",
        result.issues
    );
    assert_eq!(before, checked.digest());
    let proof = result.derivation.unwrap();
    g.mappings.push(result.mapping.unwrap());
    let mut p = policy();
    p.semantics
        .as_mut()
        .unwrap()
        .derivations
        .push(proof.clone());
    (g, p, proof)
}

#[test]
fn explicit_chain_proposes_without_mutating_or_transferring_authority() {
    let g = checked(graph(), pack());
    let result = derive(&g, &request());
    assert_eq!(result.status, DerivationStatus::Proposed);
    let m = result.mapping.unwrap();
    assert_eq!(
        (
            m.relation.as_str(),
            m.sources.as_slice(),
            m.targets.as_slice()
        ),
        (
            "example:t",
            ["urn:a".to_owned()].as_slice(),
            ["urn:c".to_owned()].as_slice()
        )
    );
    assert_eq!(m.provenance.status, ProvenanceStatus::Inferred);
    assert_eq!(m.provenance.asserted_by, "urn:example:law:chain");
    assert_eq!(m.provenance.confidence, None);
    let proof = result.derivation.unwrap();
    assert_eq!(proof.depth.get(), 1);
    assert_eq!(proof.derivation_count.get(), 1);
    assert_eq!(proof.dependencies.len(), 2);
    assert!(
        proof
            .uncertainty
            .iter()
            .all(|u| u.status == UncertaintyStatus::Unknown)
    );
    assert_eq!(g.document().mappings.len(), 2);
    assert!(g.document().authorities.is_empty());
    let (g, p, _) = admitted_fixture();
    let g = checked(g, pack());
    let generation = admit(&g, &p, options()).unwrap();
    assert_eq!(generation.record().profile, SEMANTIC_PROFILE);
    assert!(generation.active("urn:m:ac"));
    assert_eq!(
        generation
            .record()
            .semantics
            .as_ref()
            .unwrap()
            .dependencies
            .iter()
            .find(|d| d.mapping == "urn:m:ac")
            .unwrap()
            .premises,
        ["urn:m:ab", "urn:m:bc"]
    );
}

#[test]
fn unknown_law_missing_premise_wrong_roles_and_nary_stay_distinct() {
    let g = checked(graph(), pack());
    let mut r = request();
    r.law = "urn:example:law:close-chain".into();
    assert_eq!(derive(&g, &r).status, DerivationStatus::Unsupported);
    r = request();
    r.premises[1] = "urn:missing".into();
    assert_eq!(derive(&g, &r).status, DerivationStatus::Unknown);
    r = request();
    r.premises.reverse();
    assert_eq!(derive(&g, &r).issues[0].code, "LAW_OPERAND_MISMATCH");
    let mut doc = graph();
    doc.mappings[1].sources = vec!["urn:d".into()];
    assert_eq!(
        derive(&checked(doc, pack()), &request()).issues[0].code,
        "LAW_MIDDLE_IDENTITY_MISMATCH"
    );
    let mut doc = graph();
    doc.mappings[0].targets.push("urn:c".into());
    doc.mappings[0].cardinality = Cardinality::OneToMany;
    assert_eq!(
        derive(&checked(doc, pack()), &request()).issues[0].code,
        "UNSUPPORTED_NARY_DERIVATION"
    );
    let mut r = request();
    r.result_id = Some("urn:m:ab".into());
    assert_eq!(derive(&g, &r).issues[0].code, "DERIVATION_SELF_REFERENCE");
}

#[test]
fn missing_proof_changed_premise_context_or_forged_readdressed_content_refuse() {
    let (doc, p, proof) = admitted_fixture();
    let g = checked(doc.clone(), pack());
    let bounds = request().bounds;
    assert_eq!(
        check_derivations(&g, &[], &request().context, bounds)
            .unwrap_err()
            .status,
        DerivationStatus::Unknown
    );
    let mut doc = doc;
    doc.mappings[0].lossiness = Lossiness::Lossy;
    let g = checked(doc, pack());
    let err = check_derivations(&g, std::slice::from_ref(&proof), &request().context, bounds)
        .unwrap_err();
    assert_eq!(err.issues[0].code, "DERIVATION_PREMISE_OR_RULE_MISMATCH");
    let g = checked(graph(), pack());
    let mut forged = proof;
    forged.rule.pack.version = "changed".into();
    readdress(&mut forged);
    let mut doc = g.document().clone();
    let mut m = forged.result.clone();
    m.attributes = Some(JsonObject::from([(
        DERIVATION_ATTRIBUTE.into(),
        Value::String(forged.id.clone()),
    )]));
    doc.mappings.push(m);
    let g = checked(doc, pack());
    assert_eq!(
        check_derivations(&g, &[forged], &request().context, bounds)
            .unwrap_err()
            .issues[0]
            .code,
        "DERIVATION_PREMISE_OR_RULE_MISMATCH"
    );
    let (doc, _, proof) = admitted_fixture();
    let g = checked(doc, pack());
    let mut context = request().context;
    context.insert("environment".into(), "prod".into());
    assert_eq!(
        check_derivations(&g, &[proof], &context, bounds)
            .unwrap_err()
            .issues[0]
            .code,
        "DERIVATION_CONTEXT_MISMATCH"
    );
    let mut p = p;
    p.semantics = None;
    issue(
        admit(&g, &p, options()).unwrap_err(),
        "EXECUTABLE_POLICY_REQUIRED",
    );
}

#[test]
fn declared_law_limits_are_incomplete_and_loss_is_conservative() {
    let g = checked(graph(), pack());
    let mut r = request();
    r.bounds.max_depth = SafeInteger::new(0).unwrap();
    assert_eq!(derive(&g, &r).status, DerivationStatus::Incomplete);
    r = request();
    r.bounds.max_derivations = SafeInteger::new(0).unwrap();
    assert_eq!(derive(&g, &r).status, DerivationStatus::Incomplete);
    r = request();
    r.bounds.max_depth = SafeInteger::new(129).unwrap();
    assert_eq!(derive(&g, &r).status, DerivationStatus::Rejected);
    for loss in [Lossiness::Lossy, Lossiness::Unknown] {
        let mut doc = graph();
        doc.mappings[1].lossiness = loss;
        assert_eq!(
            derive(&checked(doc, pack()), &request())
                .mapping
                .unwrap()
                .lossiness,
            loss
        );
    }
    let mut r = request();
    r.law = "urn:example:law:reverse".into();
    r.premises.truncate(1);
    let m = derive(&g, &r).mapping.unwrap();
    assert_eq!(
        (m.sources, m.targets),
        (vec!["urn:b".to_owned()], vec!["urn:a".to_owned()])
    );
}

#[test]
fn law_context_and_declared_kind_conditions_are_checked() {
    let mut p = pack();
    p.laws.as_mut().unwrap()[0].conditions=Some(parse_value(&canonical_bytes(&json!({"context":{"key":"tenant","operator":"equals","value":"approved"},"middleKinds":["concept"]})).unwrap()).and_then(|v|serde_json::from_value(v).map_err(ContractError::from)).unwrap());
    let g = checked(graph(), p);
    let mut r = request();
    assert_eq!(derive(&g, &r).status, DerivationStatus::Unknown);
    r.context.insert("tenant".into(), "other".into());
    assert_eq!(derive(&g, &r).issues[0].code, "LAW_CONTEXT_NOT_SATISFIED");
    r.context.insert("tenant".into(), "approved".into());
    assert_eq!(derive(&g, &r).status, DerivationStatus::Proposed);
    let mut p = pack();
    p.laws.as_mut().unwrap()[0].conditions = Some(LawConditions {
        middle_kinds: Some(vec!["other-kind".into()]),
        ..Default::default()
    });
    p.relations[0].target_kinds = None;
    let g = checked(graph(), p);
    assert_eq!(derive(&g, &request()).issues[0].code, "LAW_KIND_MISMATCH");
}

#[test]
fn inactive_partial_nondeterministic_irreversible_premises_cannot_be_upgraded() {
    let (doc, mut p, _) = admitted_fixture();
    let g = checked(doc, pack());
    p.mappings[0].select.as_mut().unwrap().relations =
        Some(vec!["example:s".into(), "example:t".into()]);
    let mut source = p.mappings[0].clone();
    source.select = None;
    source.mapping = Some("urn:m:ab".into());
    p.mappings.push(source);
    p.mappings[1].coverage = Coverage::Partial;
    issue(
        admit(&g, &p, options()).unwrap_err(),
        "DERIVATION_SEMANTICS_STRENGTHENED",
    );
    p.mappings[1].coverage = Coverage::Total;
    p.mappings[1].applicability = Some(Applicability {
        when: Some(ContextExpression::Comparison {
            key: "environment".into(),
            operator: ComparisonOperator::Equals,
            value: "prod".into(),
        }),
        unless: None,
    });
    issue(
        admit(&g, &p, options()).unwrap_err(),
        "INACTIVE_DERIVATION_PREMISE",
    );
    let mut doc = graph();
    let mut r = request();
    r.law = "urn:example:law:reverse".into();
    r.premises.truncate(1);
    let result = derive(&checked(doc.clone(), pack()), &r);
    doc.mappings.push(result.mapping.unwrap());
    let mut p = policy();
    p.mappings[0].reversibility = Reversibility::Irreversible;
    p.semantics
        .as_mut()
        .unwrap()
        .derivations
        .push(result.derivation.unwrap());
    issue(
        admit(&checked(doc, pack()), &p, options()).unwrap_err(),
        "IRREVERSIBLE_DERIVATION_PREMISE",
    );
}

#[test]
fn forbidden_close_chain_inconsistent_kinds_and_exact_import_drift_reject() {
    let mut p = pack();
    let mut law = p.laws.as_ref().unwrap()[0].clone();
    law.id = "urn:close:chain".into();
    law.operands = vec!["example:close".into(); 2];
    law.result_relation = "example:close".into();
    p.laws.as_mut().unwrap().push(law);
    issue(
        CheckedGraph::check(graph(), vec![p]).unwrap_err(),
        "INCONSISTENT_RELATION_LAW",
    );
    let mut p = pack();
    p.laws.as_mut().unwrap()[0].conditions = Some(LawConditions {
        source_kinds: Some(vec!["incompatible".into()]),
        ..Default::default()
    });
    issue(
        CheckedGraph::check(graph(), vec![p]).unwrap_err(),
        "INCONSISTENT_RELATION_LAW",
    );
    let original = pack();
    let mut importer:RelationPack=parse(&canonical_bytes(&json!({"schemaVersion":"0.1.0","documentType":"relation-pack","id":"urn:importer","version":"1","relations":[],"imports":[{"id":original.id,"version":original.version,"digest":canonical_digest(&original).unwrap()}],"laws":[]})).unwrap()).unwrap();
    CheckedGraph::check(graph(), vec![importer.clone(), original.clone()]).unwrap();
    importer.imports.as_mut().unwrap()[0].digest =
        "sha256:0000000000000000000000000000000000000000000000000000000000000000".into();
    issue(
        CheckedGraph::check(graph(), vec![original, importer.clone()]).unwrap_err(),
        "PACK_IMPORT_BINDING_MISMATCH",
    );
    issue(
        CheckedGraph::check(graph(), vec![importer]).unwrap_err(),
        "MISSING_EXACT_PACK_IMPORT",
    );
}

#[test]
fn disjointness_applies_to_active_facts_and_cannot_be_waived() {
    let (mut doc, mut p, _) = admitted_fixture();
    let mut m = doc.mappings[2].clone();
    m.id = "urn:m:excluded".into();
    m.relation = "example:excluded".into();
    m.attributes = None;
    doc.mappings.push(m);
    let g = checked(doc, pack());
    issue(
        admit(&g, &p, options()).unwrap_err(),
        "DISJOINT_RELATION_CONFLICT",
    );
    p.mappings[0]
        .select
        .as_mut()
        .unwrap()
        .relations
        .as_mut()
        .unwrap()
        .retain(|r| r != "example:excluded");
    let mut d = p.mappings[0].clone();
    d.select = None;
    d.mapping = Some("urn:m:excluded".into());
    d.applicability = Some(Applicability {
        when: Some(ContextExpression::Comparison {
            key: "environment".into(),
            operator: ComparisonOperator::Equals,
            value: "prod".into(),
        }),
        unless: None,
    });
    p.mappings.push(d);
    assert!(admit(&g, &p, options()).is_ok());
}
