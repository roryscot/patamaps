use crate::admission::selector_matches;
use crate::graph::{finish, identifier};
use crate::uncertainty::selector_valid;
use crate::{AdmittedGeneration, CheckError, CheckedGraph, Issue};
use patamaps_contracts::*;
use std::collections::{BTreeMap, BTreeSet, HashMap};

pub(crate) fn budget_issues(graph: &CheckedGraph, budgets: &[ConsumerRiskBudget]) -> Vec<Issue> {
    let rules: usize = budgets.iter().map(|b| b.classifications.len()).sum();
    if budgets.len() > 10_000 || rules.saturating_mul(graph.document().mappings.len()) > 2_000_000 {
        return vec![Issue::error(
            "RISK_WORK_LIMIT",
            "Budget rule selection exceeds declared limits",
            "budgets",
        )];
    }
    let mut issues = Vec::new();
    let mut ids = BTreeSet::new();
    for b in budgets {
        if !identifier(&b.id)
            || !ids.insert(&b.id)
            || !identifier(&b.consumer)
            || !b.require_complete_classification
            || !b.require_complete_dependencies
        {
            issues.push(Issue::error(
                "INVALID_CONSUMER_BUDGET",
                "Budget identity/consumer is invalid or complete accounting is disabled",
                &b.id,
            ));
        }
        let mut rule_ids = BTreeSet::new();
        for r in &b.classifications {
            if !identifier(&r.id)
                || !rule_ids.insert(&r.id)
                || r.classification.is_empty()
                || !selector_valid(&r.select)
            {
                issues.push(Issue::error(
                    "INVALID_RISK_CLASSIFICATION",
                    "Invalid classification identity, label or selector",
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
                    "UNKNOWN_RISK_SELECTOR_MAPPING",
                    "Risk selector references an unavailable mapping",
                    &r.id,
                ));
            }
            if !graph
                .document()
                .mappings
                .iter()
                .any(|m| selector_matches(graph, m, &r.select))
            {
                issues.push(Issue::error(
                    "STALE_RISK_CLASSIFICATION",
                    "Risk selector matches no graph mapping",
                    &r.id,
                ));
            }
        }
    }
    issues
}

/// Projection receives an admitted capability; saved reports cannot invoke
/// consumer accounting without complete admission and proof recomputation.
pub fn project_semantics(
    generation: &AdmittedGeneration<'_>,
    spec: &ProjectionSpec,
    direct_mappings: &BTreeSet<String>,
) -> Result<Option<ProjectionSemantics>, CheckError> {
    let Some(semantic) = generation.record().semantics.as_ref() else {
        if spec.semantics.is_some() {
            return Err(CheckError(vec![Issue::error(
                "SEMANTIC_POLICY_REQUIRED",
                "Consumer requirements need an admitted semantic policy",
                &spec.id,
            )]));
        }
        return Ok(None);
    };
    let request = spec.semantics.as_ref().ok_or_else(|| {
        CheckError(vec![Issue::error(
            "SEMANTIC_CONSUMER_REQUIRED",
            "Semantic projection requires an explicit consumer and budget selection",
            &spec.id,
        )])
    })?;
    if !identifier(&request.consumer) || request.budget.as_ref().is_some_and(|id| !identifier(id)) {
        return Err(CheckError(vec![Issue::error(
            "INVALID_SEMANTIC_CONSUMER",
            "Consumer and selected budget must be stable identifiers",
            &spec.id,
        )]));
    }
    let graph = generation.graph();
    let budgets = &generation
        .policy()
        .semantics
        .as_ref()
        .expect("admitted semantics")
        .risk_budgets;
    let deps: HashMap<_, _> = semantic
        .dependencies
        .iter()
        .map(|d| (d.mapping.as_str(), d))
        .collect();
    let mut used = direct_mappings.clone();
    let mut queue: Vec<_> = used.iter().cloned().collect();
    let mut cursor = 0;
    let mut work = 0usize;
    while cursor < queue.len() {
        let id = &queue[cursor];
        let d = deps.get(id.as_str()).ok_or_else(|| {
            CheckError(vec![Issue::error(
                "INCOMPLETE_PROJECTION_DEPENDENCIES",
                "Used mapping lacks admitted dependency information",
                id,
            )])
        })?;
        for premise in &d.premises {
            work += 1;
            if work > 2_000_000 {
                return Err(CheckError(vec![Issue::error(
                    "RISK_WORK_LIMIT",
                    "Projection closure exceeds declared work limits",
                    &spec.id,
                )]));
            }
            if used.insert(premise.clone()) {
                queue.push(premise.clone());
            }
        }
        cursor += 1;
    }
    let summaries: HashMap<_, _> = semantic
        .uncertainty
        .iter()
        .map(|s| (s.mapping.as_str(), s))
        .collect();
    let mut dependencies = Vec::new();
    let mut derivations = BTreeMap::new();
    let mut uncertainty = Vec::new();
    let mut lossy = Vec::new();
    let mut inferred = Vec::new();
    for id in &used {
        let m = graph.mapping(id).ok_or_else(|| {
            CheckError(vec![Issue::error(
                "INCOMPLETE_PROJECTION_RISK_INPUT",
                "Used graph mapping is unavailable",
                id,
            )])
        })?;
        let d = *deps.get(id.as_str()).ok_or_else(|| {
            CheckError(vec![Issue::error(
                "INCOMPLETE_PROJECTION_DEPENDENCIES",
                "Closure mapping lacks dependency information",
                id,
            )])
        })?;
        dependencies.push(d.clone());
        if let Some(p) = &d.derivation {
            derivations.insert(p.id.clone(), p.clone());
        }
        uncertainty.push(
            (*summaries.get(id.as_str()).ok_or_else(|| {
                CheckError(vec![Issue::error(
                    "INCOMPLETE_PROJECTION_RISK_INPUT",
                    "Used uncertainty summary is unavailable",
                    id,
                )])
            })?)
            .clone(),
        );
        if m.lossiness == Lossiness::Lossy {
            lossy.push(id.clone());
        }
        if m.provenance.status == ProvenanceStatus::Inferred {
            inferred.push(id.clone());
        }
    }
    let mut risk = ProjectionRisk {
        status: "not-evaluated",
        budget: None,
        classifications: vec![],
        total_cost: None,
        lossy_mappings: lossy,
        inferred_mappings: inferred,
        uncertainty,
    };
    let mut issues = Vec::new();
    match &request.budget {
        None => {
            if budgets.iter().any(|b| b.consumer == request.consumer) {
                issues.push(Issue::error(
                    "CONSUMER_BUDGET_REQUIRED",
                    "Consumer has a budget and cannot opt out",
                    &request.consumer,
                ));
            }
        }
        Some(id) => {
            let b = budgets.iter().find(|b| b.id == *id).ok_or_else(|| {
                CheckError(vec![Issue::error(
                    "MISSING_CONSUMER_BUDGET",
                    "Requested budget is unavailable",
                    id,
                )])
            })?;
            if b.consumer != request.consumer {
                return Err(CheckError(vec![Issue::error(
                    "CONSUMER_BUDGET_MISMATCH",
                    "Selected budget belongs to another consumer",
                    &request.consumer,
                )]));
            }
            if b.classifications.len().saturating_mul(used.len()) > 2_000_000 {
                return Err(CheckError(vec![Issue::error(
                    "RISK_WORK_LIMIT",
                    "Unique mapping classification exceeds profile limits",
                    &b.id,
                )]));
            }
            let mut total = Some(SafeInteger::new(0).expect("zero"));
            for id in &used {
                let m = graph.mapping(id).expect("complete closure");
                let rules: Vec<_> = b
                    .classifications
                    .iter()
                    .filter(|r| selector_matches(graph, m, &r.select))
                    .collect();
                if rules.len() != 1 {
                    issues.push(Issue::error(if rules.is_empty(){"MISSING_RISK_CLASSIFICATION"}else{"AMBIGUOUS_RISK_CLASSIFICATION"},"Every unique used mapping needs exactly one classification, including zero cost",id));
                    continue;
                }
                let r = rules[0];
                total = total.and_then(|t| t.checked_add(r.cost));
                risk.classifications.push(ProjectionClassification {
                    mapping: id.clone(),
                    classification: r.classification.clone(),
                    cost: r.cost,
                });
            }
            match total {
                None => issues.push(Issue::error(
                    "RISK_COST_OVERFLOW",
                    "Unique costs exceed interoperable integer bounds",
                    &b.id,
                )),
                Some(t) if t > b.maximum_total_cost => issues.push(Issue::error(
                    "CONSUMER_RISK_BUDGET_EXCEEDED",
                    format!(
                        "Unique cost {} exceeds maximum {}",
                        t.get(),
                        b.maximum_total_cost.get()
                    ),
                    &b.id,
                )),
                _ => {}
            }
            if b.maximum_lossy_mappings
                .is_some_and(|n| risk.lossy_mappings.len() as u64 > n.get())
            {
                issues.push(Issue::error(
                    "CONSUMER_LOSSY_LIMIT_EXCEEDED",
                    "Unique lossy mapping count exceeds consumer limit",
                    &b.id,
                ));
            }
            if b.maximum_inferred_mappings
                .is_some_and(|n| risk.inferred_mappings.len() as u64 > n.get())
            {
                issues.push(Issue::error(
                    "CONSUMER_INFERRED_LIMIT_EXCEEDED",
                    "Unique inferred mapping count exceeds consumer limit",
                    &b.id,
                ));
            }
            if issues.is_empty() {
                risk.status = "evaluated";
                risk.budget = Some(ContentBinding {
                    id: b.id.clone(),
                    digest: canonical_digest(b)?,
                });
                risk.total_cost = total;
            }
        }
    }
    finish(issues)?;
    Ok(Some(ProjectionSemantics {
        consumer: request.consumer.clone(),
        used_mappings: used.into_iter().collect(),
        dependencies,
        derivations: derivations.into_values().collect(),
        risk,
    }))
}
