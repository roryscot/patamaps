use crate::admission::{context_valid, matches_context, required};
use crate::graph::{identifier, object_bounds};
use crate::uncertainty::CheckedUncertainty;
use crate::{CheckError, CheckedGraph, Issue};
use patamaps_contracts::*;
use serde::Serialize;
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

#[derive(Clone, Copy, Default)]
pub struct UncertaintyInputs<'a> {
    pub assessments: &'a [UncertaintyAssessment],
    pub evidence: &'a [Evidence],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum DerivationStatus {
    Proposed,
    Rejected,
    Unsupported,
    Unknown,
    Incomplete,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DerivationFailure {
    pub status: DerivationStatus,
    pub issues: Vec<Issue>,
}
impl From<CheckError> for DerivationFailure {
    fn from(e: CheckError) -> Self {
        Self {
            status: DerivationStatus::Rejected,
            issues: e.0,
        }
    }
}
impl From<ContractError> for DerivationFailure {
    fn from(e: ContractError) -> Self {
        CheckError::from(e).into()
    }
}
impl From<DerivationFailure> for CheckError {
    fn from(e: DerivationFailure) -> Self {
        Self(e.issues)
    }
}
fn fail(status: DerivationStatus, code: &str, message: &str, id: &str) -> DerivationFailure {
    DerivationFailure {
        status,
        issues: vec![Issue::error(code, message, id)],
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompositionOutcome {
    pub schema_version: ProtocolVersion,
    pub document_type: &'static str,
    pub status: DerivationStatus,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mapping: Option<Mapping>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub derivation: Option<CorrespondenceDerivation>,
    pub issues: Vec<Issue>,
}

/// Proof records are untrusted until every supplied claim and graph reference
/// has been recomputed against an immutable checked graph.
/// ```compile_fail
/// use patamaps_core::CheckedDerivations;
/// let forged: CheckedDerivations = serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug)]
pub struct CheckedDerivations {
    records: Vec<CorrespondenceDerivation>,
}
impl CheckedDerivations {
    pub fn records(&self) -> &[CorrespondenceDerivation] {
        &self.records
    }
}

pub fn mapping_with_proof(proof: &CorrespondenceDerivation) -> Mapping {
    let mut mapping = proof.result.clone();
    mapping
        .attributes
        .get_or_insert_with(JsonObject::new)
        .insert(DERIVATION_ATTRIBUTE.into(), proof.id.clone().into());
    mapping
}
fn address(proof: &CorrespondenceDerivation) -> Result<String, ContractError> {
    let mut v = serde_json::to_value(proof)?;
    let o = v.as_object_mut().expect("proof object");
    o.remove("id");
    o.remove("digest");
    canonical_digest(&v)
}
fn bounds_valid(bounds: DerivationBounds) -> Result<(), DerivationFailure> {
    if bounds.max_depth.get() > 128 || bounds.max_derivations.get() > 10_000 {
        return Err(fail(
            DerivationStatus::Rejected,
            "INVALID_DERIVATION_BOUNDS",
            "Depth must be 0–128 and derivation count 0–10,000",
            "bounds",
        ));
    }
    Ok(())
}
fn context_checked(context: &JsonObject) -> Result<JsonObject, DerivationFailure> {
    if !context_valid(context) {
        return Err(fail(
            DerivationStatus::Rejected,
            "INVALID_CONTEXT",
            "Context must contain primitives or primitive arrays",
            "context",
        ));
    }
    Ok(parse(&canonical_bytes(context)?)?)
}
pub(crate) fn proof_preflight(records: &[CorrespondenceDerivation]) -> Result<(), CheckError> {
    if records.len() > 10_000 {
        return Err(CheckError(vec![Issue::error(
            "DERIVATION_LIMIT",
            "At most 10,000 input proofs",
            "derivations",
        )]));
    }
    for r in records {
        object_bounds(
            r.result.attributes.iter().map(|o| (o, 4)).chain(
                r.result
                    .transform
                    .iter()
                    .filter_map(|t| t.configuration.as_ref())
                    .map(|o| (o, 5)),
            ),
            &r.id,
            "DERIVATION_RESOURCE_LIMIT",
        )?;
        if !context_valid(&r.context) {
            return Err(CheckError(vec![Issue::error(
                "INVALID_CONTEXT",
                "Proof context is not a primitive context",
                &r.id,
            )]));
        }
        if r.premises.len() > 2 || r.dependencies.len() > 110_000 || r.uncertainty.len() != 6 {
            return Err(CheckError(vec![Issue::error(
                "INVALID_DERIVATION_INPUT",
                "Invalid or excessive proof fields",
                &r.id,
            )]));
        }
    }
    Ok(())
}

#[derive(Clone)]
struct CheckedProof {
    proof: CorrespondenceDerivation,
    closure: BTreeSet<String>,
}
struct Engine<'a> {
    graph: &'a CheckedGraph,
    context: JsonObject,
    bounds: DerivationBounds,
    proofs: HashMap<&'a str, &'a CorrespondenceDerivation>,
    checked: HashMap<String, CheckedProof>,
    visiting: HashSet<String>,
    work: HashSet<String>,
    uncertainty: CheckedUncertainty,
}
impl<'a> Engine<'a> {
    fn new(
        graph: &'a CheckedGraph,
        context: &JsonObject,
        bounds: DerivationBounds,
        records: &'a [CorrespondenceDerivation],
        inputs: UncertaintyInputs<'_>,
        prospective: Option<&str>,
    ) -> Result<Self, DerivationFailure> {
        bounds_valid(bounds)?;
        proof_preflight(records)?;
        parse_value(&canonical_bytes(&records)?)?;
        let mut proofs = HashMap::new();
        for p in records {
            let digest = address(p)?;
            if p.digest != digest || p.id != format!("urn:patamaps:derivation:{}", &digest[7..]) {
                return Err(fail(
                    DerivationStatus::Rejected,
                    "DERIVATION_DIGEST_MISMATCH",
                    "Proof identity does not bind its complete value",
                    &p.id,
                ));
            }
            if proofs.insert(p.id.as_str(), p).is_some() {
                return Err(fail(
                    DerivationStatus::Rejected,
                    "DUPLICATE_DERIVATION",
                    "Duplicate proof record",
                    &p.id,
                ));
            }
        }
        Ok(Self {
            graph,
            context: context_checked(context)?,
            bounds,
            proofs,
            checked: HashMap::new(),
            visiting: HashSet::new(),
            work: HashSet::new(),
            uncertainty: CheckedUncertainty::new(
                graph,
                inputs.assessments,
                inputs.evidence,
                records,
                prospective,
            )?,
        })
    }
    fn check(&mut self, id: &str) -> Result<CheckedProof, DerivationFailure> {
        if self.visiting.contains(id) {
            return Err(fail(
                DerivationStatus::Rejected,
                "DERIVATION_CYCLE",
                "Proof dependencies contain a cycle",
                id,
            ));
        }
        if let Some(c) = self.checked.get(id) {
            return Ok(c.clone());
        }
        let proof = *self.proofs.get(id).ok_or_else(|| {
            fail(
                DerivationStatus::Unknown,
                "MISSING_DERIVATION",
                "Required proof is unavailable",
                id,
            )
        })?;
        self.work.insert(id.into());
        if self.work.len() as u64 > self.bounds.max_derivations.get()
            || self.visiting.len() as u64 + 1 > self.bounds.max_depth.get()
        {
            return Err(fail(
                DerivationStatus::Incomplete,
                "DERIVATION_LIMIT",
                "Proof validation exceeds declared bounds",
                id,
            ));
        }
        self.visiting.insert(id.into());
        let checked = (|| {
            if proof.context_digest != canonical_digest(&self.context)?
                || canonical_digest(&proof.context)? != canonical_digest(&self.context)?
            {
                return Err(fail(
                    DerivationStatus::Rejected,
                    "DERIVATION_CONTEXT_MISMATCH",
                    "Proof belongs to another context",
                    id,
                ));
            }
            let current = self.graph.mapping(&proof.result.id).ok_or_else(|| {
                fail(
                    DerivationStatus::Rejected,
                    "DERIVATION_RESULT_MISMATCH",
                    "Proof result is absent from the graph",
                    &proof.result.id,
                )
            })?;
            if canonical_digest(current)? != canonical_digest(&mapping_with_proof(proof))? {
                return Err(fail(
                    DerivationStatus::Rejected,
                    "DERIVATION_RESULT_MISMATCH",
                    "Graph result differs from proof back-reference and result",
                    &proof.result.id,
                ));
            }
            let expected = self.build(
                &proof.rule.id,
                &proof
                    .premises
                    .iter()
                    .map(|p| p.mapping.clone())
                    .collect::<Vec<_>>(),
                Some(&proof.result.id),
            )?;
            if canonical_bytes(&expected.proof)? != canonical_bytes(proof)? {
                return Err(fail(
                    DerivationStatus::Rejected,
                    "DERIVATION_PREMISE_OR_RULE_MISMATCH",
                    "Premises, packs, rule, closure or propagated values changed",
                    id,
                ));
            }
            Ok(expected)
        })();
        self.visiting.remove(id);
        if let Ok(c) = &checked {
            self.checked.insert(id.into(), c.clone());
        }
        checked
    }
    fn build(
        &mut self,
        law_id: &str,
        premise_ids: &[String],
        result_id: Option<&str>,
    ) -> Result<CheckedProof, DerivationFailure> {
        let (pack, law) = self.graph.law(law_id).ok_or_else(|| {
            fail(
                DerivationStatus::Unsupported,
                "UNSUPPORTED_RELATION_LAW",
                "No declared executable law exists",
                law_id,
            )
        })?;
        if premise_ids.len() != law.operands.len() {
            return Err(fail(
                DerivationStatus::Rejected,
                "LAW_ARITY_MISMATCH",
                "Ordered premises do not match law arity",
                law_id,
            ));
        }
        let mut mappings = Vec::new();
        for (id, relation) in premise_ids.iter().zip(&law.operands) {
            let m = self.graph.mapping(id).ok_or_else(|| {
                fail(
                    DerivationStatus::Unknown,
                    "MISSING_DERIVATION_PREMISE",
                    "Premise is unavailable",
                    id,
                )
            })?;
            if &m.relation != relation {
                return Err(fail(
                    DerivationStatus::Rejected,
                    "LAW_OPERAND_MISMATCH",
                    "Ordered premise relation differs from operand",
                    id,
                ));
            }
            if m.sources.len() != 1
                || m.targets.len() != 1
                || m.cardinality != Cardinality::OneToOne
            {
                return Err(fail(
                    DerivationStatus::Unsupported,
                    "UNSUPPORTED_NARY_DERIVATION",
                    "Binary laws cannot flatten a hyperedge",
                    id,
                ));
            }
            if m.transform.is_some() || m.invariants.as_ref().is_some_and(|v| !v.is_empty()) {
                return Err(fail(
                    DerivationStatus::Unsupported,
                    "UNSUPPORTED_DERIVATION_SEMANTICS",
                    "Transform and invariant composition need an explicit contract",
                    id,
                ));
            }
            mappings.push(m);
        }
        let c = law.conditions.clone().unwrap_or_default();
        if let Some(expr) = &c.context {
            let mut keys = BTreeSet::new();
            required(expr, &mut keys);
            if keys.iter().any(|k| !self.context.contains_key(*k)) {
                return Err(fail(
                    DerivationStatus::Unknown,
                    "MISSING_LAW_CONTEXT",
                    "Required context key is absent",
                    law_id,
                ));
            }
            if !matches_context(expr, &self.context) {
                return Err(fail(
                    DerivationStatus::Rejected,
                    "LAW_CONTEXT_NOT_SATISFIED",
                    "Context condition does not hold",
                    law_id,
                ));
            }
        }
        let (source, target) = if law.operation == LawOperation::Reverse {
            (&mappings[0].targets[0], &mappings[0].sources[0])
        } else {
            if mappings[0].targets[0] != mappings[1].sources[0] {
                return Err(fail(
                    DerivationStatus::Rejected,
                    "LAW_MIDDLE_IDENTITY_MISMATCH",
                    "Ordered premises do not share the same stable middle entity",
                    law_id,
                ));
            }
            (&mappings[0].sources[0], &mappings[1].targets[0])
        };
        let definition = self
            .graph
            .relation(&law.result_relation)
            .expect("checked law result");
        for (id, lists) in [
            (
                source,
                vec![c.source_kinds.as_ref(), definition.source_kinds.as_ref()],
            ),
            (
                target,
                vec![c.target_kinds.as_ref(), definition.target_kinds.as_ref()],
            ),
        ] {
            if lists
                .into_iter()
                .flatten()
                .any(|l| !l.contains(&self.graph.entity(id).expect("checked endpoint").kind))
            {
                return Err(fail(
                    DerivationStatus::Rejected,
                    "LAW_KIND_MISMATCH",
                    "Endpoint does not satisfy law/result kinds",
                    id,
                ));
            }
        }
        if law.operation == LawOperation::Chain
            && c.middle_kinds.as_ref().is_some_and(|l| {
                !l.contains(
                    &self
                        .graph
                        .entity(&mappings[0].targets[0])
                        .expect("middle entity")
                        .kind,
                )
            })
        {
            return Err(fail(
                DerivationStatus::Rejected,
                "LAW_KIND_MISMATCH",
                "Middle kind does not satisfy law",
                &mappings[0].targets[0],
            ));
        }
        if definition
            .cardinalities
            .as_ref()
            .is_some_and(|v| !v.contains(&Cardinality::OneToOne))
        {
            return Err(fail(
                DerivationStatus::Unsupported,
                "UNSUPPORTED_RESULT_CARDINALITY",
                "Result relation forbids binary results",
                law_id,
            ));
        }
        let mut premises = Vec::new();
        let mut premise_uncertainty = Vec::new();
        let mut dependencies = BTreeMap::new();
        let mut closure = BTreeSet::new();
        let mut depth = 1;
        for m in &mappings {
            let digest = canonical_digest(m)?;
            dependencies.insert(m.id.clone(), digest.clone());
            let mut premise = DerivationPremise {
                mapping: m.id.clone(),
                digest,
                derivation: None,
            };
            if let Some(v) = m
                .attributes
                .as_ref()
                .and_then(|a| a.get(DERIVATION_ATTRIBUTE))
            {
                let id = v.as_str().ok_or_else(|| {
                    fail(
                        DerivationStatus::Rejected,
                        "INVALID_DERIVATION_REFERENCE",
                        "Proof reference must be a string",
                        &m.id,
                    )
                })?;
                let child = self.check(id)?;
                premise_uncertainty.push(child.proof.uncertainty.clone());
                premise.derivation = Some(ContentBinding {
                    id: child.proof.id.clone(),
                    digest: child.proof.digest.clone(),
                });
                dependencies.insert(child.proof.id.clone(), child.proof.digest.clone());
                for d in &child.proof.dependencies {
                    dependencies.insert(d.id.clone(), d.digest.clone());
                }
                closure.extend(child.closure);
                depth = depth.max(child.proof.depth.get() + 1);
            } else {
                premise_uncertainty.push(self.uncertainty.mapping(m, &[])?);
            }
            premises.push(premise);
        }
        if depth > self.bounds.max_depth.get()
            || closure.len() as u64 + 1 > self.bounds.max_derivations.get()
        {
            return Err(fail(
                DerivationStatus::Incomplete,
                "DERIVATION_LIMIT",
                "Proposed depth or unique proof count exceeds declared bounds",
                law_id,
            ));
        }
        let pack_binding = PackContentBinding {
            id: pack.id.clone(),
            version: pack.version.clone(),
            digest: canonical_digest(pack)?,
        };
        let id = match result_id {
            Some(id) => id.to_owned(),
            None => format!(
                "urn:patamaps:mapping:derived:{}",
                &canonical_digest(
                    &json!({"law":law.id,"pack":pack_binding,"premises":premises,"context":self.context})
                )?[7..]
            ),
        };
        if !identifier(&id) {
            return Err(fail(
                DerivationStatus::Rejected,
                "INVALID_MAPPING_ID",
                "Result ID must be a stable identifier",
                &id,
            ));
        }
        if premise_ids.contains(&id) {
            return Err(fail(
                DerivationStatus::Rejected,
                "DERIVATION_SELF_REFERENCE",
                "Result cannot be its own premise",
                &id,
            ));
        }
        let result = Mapping {
            id: id.clone(),
            relation: law.result_relation.clone(),
            sources: vec![source.clone()],
            targets: vec![target.clone()],
            cardinality: Cardinality::OneToOne,
            lossiness: if mappings.iter().any(|m| m.lossiness == Lossiness::Lossy) {
                Lossiness::Lossy
            } else if mappings.iter().any(|m| m.lossiness == Lossiness::Unknown) {
                Lossiness::Unknown
            } else {
                Lossiness::Lossless
            },
            provenance: Provenance {
                status: ProvenanceStatus::Inferred,
                asserted_by: law.id.clone(),
                confidence: None,
                observed_at: None,
                source_revision: None,
            },
            transform: None,
            invariants: None,
            attributes: None,
        };
        let mut imports = pack.imports.clone().unwrap_or_default();
        imports.sort_by(|a, b| a.id.cmp(&b.id));
        let uncertainty = self.uncertainty.mapping(&result, &premise_uncertainty)?;
        for binding in self.uncertainty.dependencies(&uncertainty)? {
            dependencies.insert(binding.id, binding.digest);
        }
        let mut proof = CorrespondenceDerivation {
            schema_version: ProtocolVersion::Draft1,
            document_type: DerivationType::Derivation,
            id: String::new(),
            digest: String::new(),
            interpretation: Interpretation::DeclaredLawApplication,
            rule: DerivationRule {
                id: law.id.clone(),
                pack: pack_binding,
                imports,
            },
            premises,
            result,
            context: self.context.clone(),
            context_digest: canonical_digest(&self.context)?,
            dependencies: dependencies
                .into_iter()
                .map(|(id, digest)| ContentBinding { id, digest })
                .collect(),
            depth: SafeInteger::new(depth).expect("bounded"),
            derivation_count: SafeInteger::new(closure.len() as u64 + 1).expect("bounded"),
            uncertainty,
        };
        proof.digest = address(&proof)?;
        proof.id = format!("urn:patamaps:derivation:{}", &proof.digest[7..]);
        parse_value(&canonical_bytes(&proof)?)?;
        closure.insert(proof.id.clone());
        Ok(CheckedProof { proof, closure })
    }
}

/// Read-only inference proposal. This function neither mutates nor admits it.
pub fn derive(graph: &CheckedGraph, request: &CompositionRequest) -> CompositionOutcome {
    let result = (|| {
        if request.premises.len() > 2 {
            return Err(fail(
                DerivationStatus::Rejected,
                "LAW_ARITY_MISMATCH",
                "Only unary reverse and binary chain laws are supported",
                &request.law,
            ));
        }
        let mut engine = Engine::new(
            graph,
            &request.context,
            request.bounds,
            &request.derivations,
            UncertaintyInputs {
                assessments: &request.assessments,
                evidence: &request.evidence,
            },
            request.result_id.as_deref(),
        )?;
        parse_value(&canonical_bytes(request)?)?;
        let checked = engine.build(
            &request.law,
            &request.premises,
            request.result_id.as_deref(),
        )?;
        let mapping = mapping_with_proof(&checked.proof);
        if graph.document().entities.iter().any(|e| e.id == mapping.id)
            || graph
                .document()
                .authorities
                .iter()
                .any(|a| a.id == mapping.id)
            || graph
                .mapping(&mapping.id)
                .is_some_and(|m| canonical_digest(m).ok() != canonical_digest(&mapping).ok())
        {
            return Err(fail(
                DerivationStatus::Rejected,
                "DERIVATION_RESULT_ID_CONFLICT",
                "Result ID already denotes another graph value",
                &mapping.id,
            ));
        }
        Ok((mapping, checked.proof))
    })();
    match result {
        Ok((mapping, proof)) => CompositionOutcome {
            schema_version: ProtocolVersion::Draft1,
            document_type: "composition-result",
            status: DerivationStatus::Proposed,
            mapping: Some(mapping),
            derivation: Some(proof),
            issues: vec![],
        },
        Err(e) => CompositionOutcome {
            schema_version: ProtocolVersion::Draft1,
            document_type: "composition-result",
            status: e.status,
            mapping: None,
            derivation: None,
            issues: e.issues,
        },
    }
}
pub fn check_derivations(
    graph: &CheckedGraph,
    records: &[CorrespondenceDerivation],
    context: &JsonObject,
    bounds: DerivationBounds,
) -> Result<CheckedDerivations, DerivationFailure> {
    check_derivations_with_inputs(
        graph,
        records,
        context,
        bounds,
        UncertaintyInputs::default(),
    )
}
pub fn check_derivations_with_inputs(
    graph: &CheckedGraph,
    records: &[CorrespondenceDerivation],
    context: &JsonObject,
    bounds: DerivationBounds,
    inputs: UncertaintyInputs<'_>,
) -> Result<CheckedDerivations, DerivationFailure> {
    let mut engine = Engine::new(graph, context, bounds, records, inputs, None)?;
    let mut ids: BTreeSet<String> = records.iter().map(|p| p.id.clone()).collect();
    for m in &graph.document().mappings {
        if let Some(v) = m
            .attributes
            .as_ref()
            .and_then(|a| a.get(DERIVATION_ATTRIBUTE))
        {
            ids.insert(
                v.as_str()
                    .ok_or_else(|| {
                        fail(
                            DerivationStatus::Rejected,
                            "INVALID_DERIVATION_REFERENCE",
                            "Proof reference must be a string",
                            &m.id,
                        )
                    })?
                    .into(),
            );
        }
    }
    let checked = ids
        .iter()
        .map(|id| engine.check(id).map(|p| p.proof))
        .collect::<Result<Vec<_>, _>>()?;
    Ok(CheckedDerivations { records: checked })
}

pub(crate) fn disjointness_issues(graph: &CheckedGraph, active: &HashSet<String>) -> Vec<Issue> {
    let mut index: HashMap<(&str, &str, &str), Vec<&Mapping>> = HashMap::new();
    let mut nary: HashMap<&str, Vec<&Mapping>> = HashMap::new();
    let mut issues = Vec::new();
    for m in &graph.document().mappings {
        if active.contains(&m.id) {
            if m.sources.len() == 1 && m.targets.len() == 1 {
                index
                    .entry((&m.relation, &m.sources[0], &m.targets[0]))
                    .or_default()
                    .push(m);
            } else {
                nary.entry(&m.relation).or_default().push(m);
            }
        }
    }
    let mut work = 0usize;
    for m in &graph.document().mappings {
        if !active.contains(&m.id) {
            continue;
        }
        let r = graph.relation(&m.relation).expect("checked relation");
        for other in r.disjoint_with.iter().flatten() {
            work += 1;
            if work > 2_000_000 {
                return vec![Issue::error(
                    "DISJOINTNESS_WORK_LIMIT",
                    "Disjointness work exceeded the profile limit",
                    &m.id,
                )];
            }
            if m.sources.len() != 1 || m.targets.len() != 1 {
                issues.push(Issue::error(
                    "UNSUPPORTED_NARY_DISJOINTNESS",
                    "Disjointness requires binary assertions",
                    &m.id,
                ));
                continue;
            }
            for n in nary.get(other.as_str()).into_iter().flatten() {
                issues.push(Issue::error(
                    "UNSUPPORTED_NARY_DISJOINTNESS",
                    "Disjointness cannot flatten a hyperedge",
                    &n.id,
                ));
            }
            let same =
                index.contains_key(&(other.as_str(), m.sources[0].as_str(), m.targets[0].as_str()));
            let symmetric = (r.symmetric == Some(true)
                || graph
                    .relation(other)
                    .is_some_and(|r| r.symmetric == Some(true)))
                && index.contains_key(&(
                    other.as_str(),
                    m.targets[0].as_str(),
                    m.sources[0].as_str(),
                ));
            if same || symmetric {
                issues.push(Issue::error(
                    "DISJOINT_RELATION_CONFLICT",
                    "Active endpoint pair asserts disjoint relations",
                    &m.id,
                ));
            }
        }
    }
    issues
}
