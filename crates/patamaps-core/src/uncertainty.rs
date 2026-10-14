use crate::admission::selector_matches;
use crate::graph::{finish, identifier, object_bounds};
use crate::{CheckError, CheckedGraph, Issue};
use patamaps_contracts::*;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

pub(crate) fn selector_valid(s: &MappingSelector) -> bool {
    let values = [&s.ids, &s.relations, &s.source_kinds, &s.target_kinds];
    let present = values.iter().any(|v| v.is_some()) || s.provenance_statuses.is_some();
    present
        && values.into_iter().flatten().all(|v| {
            !v.is_empty()
                && v.iter().all(|s| !s.is_empty())
                && v.iter().collect::<HashSet<_>>().len() == v.len()
        })
        && s.provenance_statuses
            .as_ref()
            .is_none_or(|v| !v.is_empty() && v.iter().enumerate().all(|(i, s)| !v[..i].contains(s)))
}
fn uniq(values: impl IntoIterator<Item = String>) -> Vec<String> {
    values
        .into_iter()
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect()
}
pub(crate) fn unknown(dimension: UncertaintyDimension) -> DerivationUncertainty {
    DerivationUncertainty {
        dimension,
        status: UncertaintyStatus::Unknown,
        evidence: vec![],
        assessments: vec![],
        measurement_models: vec![],
        source_revisions: vec![],
    }
}
/// Shared qualitative meet; record validation and ordering stay with their callers.
pub(crate) fn qualitative_meet_status(
    contradicted: bool,
    unknown: bool,
    models: usize,
    all_not_applicable: bool,
) -> UncertaintyStatus {
    if contradicted {
        UncertaintyStatus::Contradicted
    } else if unknown || models > 1 {
        UncertaintyStatus::Unknown
    } else if all_not_applicable {
        UncertaintyStatus::NotApplicable
    } else {
        UncertaintyStatus::Supported
    }
}
/// A qualitative meet. No scalar confidence averaging or probabilistic claim.
fn combine(
    dimension: UncertaintyDimension,
    values: &[DerivationUncertainty],
) -> DerivationUncertainty {
    if values.is_empty() {
        return unknown(dimension);
    }
    let models = uniq(values.iter().flat_map(|v| v.measurement_models.clone()));
    let status = qualitative_meet_status(
        values
            .iter()
            .any(|v| v.status == UncertaintyStatus::Contradicted),
        values
            .iter()
            .any(|v| v.status == UncertaintyStatus::Unknown),
        models.len(),
        values
            .iter()
            .all(|v| v.status == UncertaintyStatus::NotApplicable),
    );
    DerivationUncertainty {
        dimension,
        status,
        evidence: uniq(values.iter().flat_map(|v| v.evidence.clone())),
        assessments: uniq(values.iter().flat_map(|v| v.assessments.clone())),
        measurement_models: models,
        source_revisions: uniq(values.iter().flat_map(|v| v.source_revisions.clone())),
    }
}

pub(crate) struct CheckedUncertainty {
    pub(crate) assessments: Vec<UncertaintyAssessment>,
    evidence: BTreeMap<String, Evidence>,
    by_subject: HashMap<String, Vec<usize>>,
    by_id: HashMap<String, usize>,
    authorities: HashMap<String, Vec<String>>,
    work: usize,
}
impl CheckedUncertainty {
    pub(crate) fn new(
        graph: &CheckedGraph,
        assessments: &[UncertaintyAssessment],
        evidence: &[Evidence],
        proofs: &[CorrespondenceDerivation],
        prospective: Option<&str>,
    ) -> Result<Self, CheckError> {
        if assessments.len() > 100_000 || evidence.len() > 100_000 {
            return Err(CheckError(vec![Issue::error(
                "UNCERTAINTY_RESOURCE_LIMIT",
                "Too many uncertainty records",
                "uncertainty",
            )]));
        }
        object_bounds(
            evidence
                .iter()
                .filter_map(|e| e.attributes.as_ref())
                .map(|a| (a, 4)),
            "evidence",
            "UNCERTAINTY_RESOURCE_LIMIT",
        )?;
        let assessments: Vec<UncertaintyAssessment> = parse(&canonical_bytes(&assessments)?)?;
        let evidence: Vec<Evidence> = parse(&canonical_bytes(&evidence)?)?;
        let g = graph.document();
        let mut subjects: HashMap<&str, Option<&str>> = g
            .entities
            .iter()
            .map(|e| {
                (
                    e.id.as_str(),
                    e.provenance
                        .as_ref()
                        .and_then(|p| p.source_revision.as_deref())
                        .or(g.revision.as_deref()),
                )
            })
            .chain(g.mappings.iter().map(|m| {
                (
                    m.id.as_str(),
                    m.provenance
                        .source_revision
                        .as_deref()
                        .or(g.revision.as_deref()),
                )
            }))
            .chain(g.authorities.iter().map(|a| {
                (
                    a.id.as_str(),
                    a.provenance
                        .source_revision
                        .as_deref()
                        .or(g.revision.as_deref()),
                )
            }))
            .collect();
        if let Some(id) = prospective {
            subjects.insert(id, g.revision.as_deref());
        }
        let mut identities: HashSet<&str> = subjects.keys().copied().collect();
        let mut issues = Vec::new();
        for p in proofs {
            if !identities.insert(&p.id) {
                issues.push(Issue::error(
                    "DUPLICATE_DERIVATION_ID",
                    "Proof identity collides with a graph or proof identity",
                    &p.id,
                ));
            }
        }
        for id in assessments
            .iter()
            .map(|a| a.id.as_str())
            .chain(evidence.iter().map(|e| e.id.as_str()))
        {
            if !identifier(id) || !identities.insert(id) {
                issues.push(Issue::error(
                    "DUPLICATE_UNCERTAINTY_ID",
                    "Record identity is invalid or collides with another input",
                    id,
                ));
            }
        }
        let evidence_map: BTreeMap<_, _> = evidence.iter().map(|e| (e.id.as_str(), e)).collect();
        let mut refs = 0usize;
        for e in &evidence {
            refs = refs.saturating_add(e.subjects.len());
            if e.subjects.is_empty()
                || e.subjects.iter().collect::<HashSet<_>>().len() != e.subjects.len()
                || e.producer.is_empty()
                || e.kind.is_empty()
                || e.observed_at
                    .as_ref()
                    .is_some_and(|t| crate::admission::timestamp(t).is_err())
                || e.confidence
                    .is_some_and(|n| !n.is_finite() || !(0.0..=1.0).contains(&n))
                || e.locator.as_ref().is_some_and(|l| !identifier(&l.uri))
            {
                issues.push(Issue::error(
                    "INVALID_UNCERTAINTY_EVIDENCE",
                    "Invalid evidence scope, attribution or metadata",
                    &e.id,
                ));
            }
            if e.subjects
                .iter()
                .any(|s| !subjects.contains_key(s.as_str()))
            {
                issues.push(Issue::error(
                    "UNKNOWN_UNCERTAINTY_EVIDENCE_SUBJECT",
                    "Evidence subject is unavailable",
                    &e.id,
                ));
            }
        }
        for a in &assessments {
            refs = refs.saturating_add(a.evidence.len());
            if refs > 2_000_000 {
                return Err(CheckError(vec![Issue::error(
                    "UNCERTAINTY_RESOURCE_LIMIT",
                    "Evidence references exceed the profile limit",
                    "uncertainty",
                )]));
            }
            if a.assessor.is_empty()
                || a.source_revision.is_empty()
                || a.measurement_model.as_ref().is_some_and(|m| !identifier(m))
                || a.evidence.iter().collect::<HashSet<_>>().len() != a.evidence.len()
                || (a.status == UncertaintyStatus::NotApplicable
                    && a.not_applicable_reason
                        .as_ref()
                        .is_none_or(String::is_empty))
                || (a.status != UncertaintyStatus::NotApplicable
                    && a.not_applicable_reason.is_some())
            {
                issues.push(Issue::error(
                    "INVALID_UNCERTAINTY_ASSESSMENT",
                    "Assessment metadata or not-applicable reason is invalid",
                    &a.id,
                ));
            }
            match subjects.get(a.subject.as_str()) {
                None => issues.push(Issue::error(
                    "UNKNOWN_ASSESSMENT_SUBJECT",
                    "Assessed subject is unavailable",
                    &a.id,
                )),
                Some(Some(revision)) if a.source_revision != *revision => {
                    issues.push(Issue::error(
                        "ASSESSMENT_REVISION_MISMATCH",
                        "Assessment does not bind the declared subject revision",
                        &a.id,
                    ))
                }
                _ => {}
            }
            for id in &a.evidence {
                match evidence_map.get(id.as_str()) {
                    None => issues.push(Issue::error(
                        "MISSING_UNCERTAINTY_EVIDENCE",
                        "Referenced evidence is unavailable",
                        &a.id,
                    )),
                    Some(e) if !e.subjects.contains(&a.subject) => issues.push(Issue::error(
                        "UNCERTAINTY_EVIDENCE_SCOPE_MISMATCH",
                        "Evidence does not cover the assessed subject",
                        &a.id,
                    )),
                    Some(e) if e.kind != format!("uncertainty:{}", a.dimension.as_str()) => issues
                        .push(Issue::error(
                            "UNCERTAINTY_EVIDENCE_DIMENSION_MISMATCH",
                            "Evidence kind does not name this dimension",
                            &a.id,
                        )),
                    _ => {}
                }
            }
        }
        finish(issues)?;
        let mut by_subject: HashMap<String, Vec<usize>> = HashMap::new();
        for (i, a) in assessments.iter().enumerate() {
            by_subject.entry(a.subject.clone()).or_default().push(i);
        }
        let mut authorities: HashMap<String, Vec<String>> = HashMap::new();
        for a in &g.authorities {
            authorities
                .entry(a.concept.clone())
                .or_default()
                .push(a.id.clone());
        }
        let by_id = assessments
            .iter()
            .enumerate()
            .map(|(i, a)| (a.id.clone(), i))
            .collect();
        Ok(Self {
            assessments,
            evidence: evidence.into_iter().map(|e| (e.id.clone(), e)).collect(),
            by_subject,
            by_id,
            authorities,
            work: 0,
        })
    }
    pub(crate) fn handled_evidence(&self) -> HashSet<String> {
        self.assessments
            .iter()
            .flat_map(|a| a.evidence.clone())
            .collect()
    }
    pub(crate) fn mapping(
        &mut self,
        m: &Mapping,
        premises: &[Vec<DerivationUncertainty>],
    ) -> Result<Vec<DerivationUncertainty>, CheckError> {
        let mut subjects: BTreeSet<&str> = m
            .sources
            .iter()
            .chain(&m.targets)
            .map(String::as_str)
            .collect();
        subjects.insert(&m.id);
        let extra: Vec<_> = subjects
            .iter()
            .flat_map(|id| {
                self.authorities
                    .get(*id)
                    .into_iter()
                    .flatten()
                    .map(String::as_str)
            })
            .collect();
        subjects.extend(extra);
        let assessments: Vec<_> = subjects
            .iter()
            .flat_map(|id| self.by_subject.get(*id).into_iter().flatten())
            .map(|&i| &self.assessments[i])
            .collect();
        self.work = self.work.saturating_add(
            assessments.len()
                + premises
                    .iter()
                    .flatten()
                    .map(|d| 1 + d.assessments.len() + d.evidence.len())
                    .sum::<usize>(),
        );
        if self.work > 2_000_000 {
            return Err(CheckError(vec![Issue::error(
                "UNCERTAINTY_WORK_LIMIT",
                "Summary work exceeds the declared bound",
                &m.id,
            )]));
        }
        Ok(UNCERTAINTY_DIMENSIONS
            .into_iter()
            .map(|dimension| {
                let mut values: Vec<_> = premises
                    .iter()
                    .map(|p| {
                        p.iter()
                            .find(|v| v.dimension == dimension)
                            .cloned()
                            .unwrap_or_else(|| unknown(dimension))
                    })
                    .collect();
                for a in assessments.iter().filter(|a| a.dimension == dimension) {
                    let contradicts = a
                        .evidence
                        .iter()
                        .any(|id| self.evidence[id].result == EvidenceResult::Contradicts);
                    let inconclusive = a
                        .evidence
                        .iter()
                        .any(|id| self.evidence[id].result == EvidenceResult::Inconclusive);
                    values.push(DerivationUncertainty {
                        dimension,
                        status: if contradicts {
                            UncertaintyStatus::Contradicted
                        } else if inconclusive && a.status == UncertaintyStatus::Supported {
                            UncertaintyStatus::Unknown
                        } else {
                            a.status
                        },
                        evidence: a.evidence.clone(),
                        assessments: vec![a.id.clone()],
                        measurement_models: a.measurement_model.iter().cloned().collect(),
                        source_revisions: vec![a.source_revision.clone()],
                    });
                }
                combine(dimension, &values)
            })
            .collect())
    }
    pub(crate) fn dependencies(
        &self,
        summary: &[DerivationUncertainty],
    ) -> Result<Vec<ContentBinding>, ContractError> {
        let ids: BTreeSet<_> = summary
            .iter()
            .flat_map(|d| d.evidence.iter().chain(&d.assessments))
            .collect();
        ids.into_iter()
            .map(|id| {
                let digest = if let Some(e) = self.evidence.get(id) {
                    canonical_digest(e)?
                } else {
                    canonical_digest(&self.assessments[self.by_id[id]])?
                };
                Ok(ContentBinding {
                    id: id.clone(),
                    digest,
                })
            })
            .collect()
    }
    pub(crate) fn graph_summaries(
        &mut self,
        graph: &CheckedGraph,
        proofs: &[CorrespondenceDerivation],
    ) -> Result<Vec<MappingUncertainty>, CheckError> {
        let by_result: HashMap<_, _> = proofs.iter().map(|p| (p.result.id.as_str(), p)).collect();
        graph
            .document()
            .mappings
            .iter()
            .map(|m| {
                Ok(MappingUncertainty {
                    mapping: m.id.clone(),
                    dimensions: match by_result.get(m.id.as_str()) {
                        Some(p) => p.uncertainty.clone(),
                        None => self.mapping(m, &[])?,
                    },
                })
            })
            .collect()
    }
}

pub(crate) fn requirement_issues(
    graph: &CheckedGraph,
    active: &HashSet<String>,
    summaries: &[MappingUncertainty],
    requirements: &[UncertaintyRequirement],
    inputs: &CheckedUncertainty,
) -> Vec<Issue> {
    if requirements
        .len()
        .saturating_mul(graph.document().mappings.len())
        > 2_000_000
    {
        return vec![Issue::error(
            "UNCERTAINTY_WORK_LIMIT",
            "Requirement selection exceeds profile bounds",
            "requirements",
        )];
    }
    let summaries: HashMap<_, _> = summaries
        .iter()
        .map(|s| (s.mapping.as_str(), &s.dimensions))
        .collect();
    let assessments: HashMap<_, _> = inputs
        .assessments
        .iter()
        .map(|a| (a.id.as_str(), a))
        .collect();
    let mut issues = Vec::new();
    let mut ids = HashSet::new();
    for r in requirements {
        if !identifier(&r.id)
            || !ids.insert(&r.id)
            || !selector_valid(&r.select)
            || r.allowed_states.is_empty()
            || r.allowed_states
                .iter()
                .enumerate()
                .any(|(i, v)| r.allowed_states[..i].contains(v))
        {
            issues.push(Issue::error(
                "INVALID_UNCERTAINTY_REQUIREMENT",
                "Invalid identity, selector or state list",
                &r.id,
            ));
            continue;
        }
        if r.select
            .ids
            .iter()
            .flatten()
            .any(|id| graph.mapping(id).is_none())
        {
            issues.push(Issue::error(
                "UNKNOWN_UNCERTAINTY_SELECTOR_MAPPING",
                "Selector names an unavailable mapping",
                &r.id,
            ));
        }
        let matches: Vec<_> = graph
            .document()
            .mappings
            .iter()
            .filter(|m| selector_matches(graph, m, &r.select))
            .collect();
        if matches.is_empty() {
            issues.push(Issue::error(
                "STALE_UNCERTAINTY_REQUIREMENT",
                "Selector no longer matches any mapping",
                &r.id,
            ));
        }
        for m in matches.iter().filter(|m| active.contains(&m.id)) {
            let d = summaries[m.id.as_str()]
                .iter()
                .find(|d| d.dimension == r.dimension)
                .expect("complete summary");
            if !r.allowed_states.contains(&d.status) {
                issues.push(Issue::error(
                    "UNCERTAINTY_STATE_NOT_ALLOWED",
                    "Consumer requirement refuses the recorded state",
                    &m.id,
                ));
            }
            if !r.allowed_states.contains(&UncertaintyStatus::NotApplicable)
                && d.assessments
                    .iter()
                    .any(|id| assessments[id.as_str()].status == UncertaintyStatus::NotApplicable)
            {
                issues.push(Issue::error(
                    "UNCERTAINTY_NOT_APPLICABLE_NOT_ALLOWED",
                    "Contributing not-applicable assessment is not permitted",
                    &m.id,
                ));
            }
            if r.require_evidence
                && (d.evidence.is_empty()
                    || d.assessments.is_empty()
                    || d.assessments
                        .iter()
                        .any(|id| assessments[id.as_str()].evidence.is_empty()))
            {
                issues.push(Issue::error(
                    "UNCERTAINTY_EVIDENCE_REQUIRED",
                    "Every contributing assessment needs evidence",
                    &m.id,
                ));
            }
        }
    }
    issues
}
