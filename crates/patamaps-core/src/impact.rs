use crate::{CheckError, CheckedGraph, Issue};
use patamaps_contracts::ImpactDirection;
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet, HashSet, VecDeque};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ImpactStep {
    pub mapping: String,
    pub from: String,
    pub to: String,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ImpactVisit {
    pub origin: String,
    pub subject: String,
    pub path: Vec<ImpactStep>,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ImpactReport {
    pub complete: bool,
    pub visits: Vec<ImpactVisit>,
    pub unavailable_origins: Vec<String>,
    pub undeclared_directions: Vec<String>,
    pub interpretation: &'static str,
}

/// Follow authored impact directions only. Exhaustion remains incomplete and
/// unknown directions never become a assertion of no downstream influence.
pub fn impact(
    graph: &CheckedGraph,
    origins: &[String],
    max_depth: usize,
) -> Result<ImpactReport, CheckError> {
    if origins.len() > 256 || max_depth > 64 {
        return Err(CheckError(vec![Issue::error(
            "IMPACT_RESOURCE_LIMIT",
            "Impact permits 256 origins and depth 64",
            "impact",
        )]));
    }
    let mut report = ImpactReport {
        complete: true,
        visits: Vec::new(),
        unavailable_origins: Vec::new(),
        undeclared_directions: Vec::new(),
        interpretation: "Declared dependency paths; no assertion of unique causal responsibility",
    };
    let mut directions = BTreeSet::new();
    let mut work = 0usize;
    for origin in origins.iter().collect::<BTreeSet<_>>() {
        let seeds: BTreeSet<_> = if graph.entity(origin).is_some() {
            BTreeSet::from([origin.clone()])
        } else if let Some(m) = graph.mapping(origin) {
            m.sources.iter().chain(&m.targets).cloned().collect()
        } else if let Some(a) = graph
            .document()
            .authorities
            .iter()
            .find(|a| &a.id == origin)
        {
            BTreeSet::from([a.concept.clone(), a.source.clone()])
        } else {
            report.unavailable_origins.push(origin.clone());
            continue;
        };
        let mut visited = HashSet::new();
        let mut expanded = HashSet::new();
        let mut queue: VecDeque<_> = seeds
            .into_iter()
            .map(|id| (id, Vec::<ImpactStep>::new()))
            .collect();
        while let Some((id, path)) = queue.pop_front() {
            if !visited.insert(id.clone()) {
                continue;
            }
            if report.visits.len() >= 10_000 {
                report.complete = false;
                break;
            }
            report.visits.push(ImpactVisit {
                origin: origin.clone(),
                subject: id.clone(),
                path: path.clone(),
            });
            if path.len() == max_depth {
                if graph.incident(&id).next().is_some() {
                    report.complete = false;
                }
                continue;
            }
            let mut next = BTreeMap::new();
            for m in graph.incident(&id) {
                let direction = graph.relation(&m.relation).and_then(|r| r.impact_direction);
                let Some(direction) = direction else {
                    directions.insert(m.id.clone());
                    continue;
                };
                for (from, to, enabled, role) in [
                    (
                        &m.sources,
                        &m.targets,
                        matches!(
                            direction,
                            ImpactDirection::SourceToTarget | ImpactDirection::Both
                        ),
                        0,
                    ),
                    (
                        &m.targets,
                        &m.sources,
                        matches!(
                            direction,
                            ImpactDirection::TargetToSource | ImpactDirection::Both
                        ),
                        1,
                    ),
                ] {
                    work = work.saturating_add(from.len()).saturating_add(1);
                    if work > 2_000_000 {
                        report.complete = false;
                        break;
                    }
                    if !enabled || !from.contains(&id) || !expanded.insert((m.id.clone(), role)) {
                        continue;
                    }
                    for target in to {
                        work += 1;
                        if work > 2_000_000 {
                            report.complete = false;
                            break;
                        }
                        if !visited.contains(target) {
                            next.entry(target.clone()).or_insert_with(|| ImpactStep {
                                mapping: m.id.clone(),
                                from: id.clone(),
                                to: target.clone(),
                            });
                        }
                    }
                }
            }
            if work > 2_000_000 {
                break;
            }
            for (target, step) in next {
                let mut steps = path.clone();
                steps.push(step);
                queue.push_back((target, steps));
            }
        }
        if work > 2_000_000 || report.visits.len() >= 10_000 {
            report.complete = false;
            break;
        }
    }
    report.undeclared_directions = directions.into_iter().collect();
    if !report.unavailable_origins.is_empty() || !report.undeclared_directions.is_empty() {
        report.complete = false;
    }
    report
        .visits
        .sort_by(|a, b| (&a.origin, &a.subject).cmp(&(&b.origin, &b.subject)));
    Ok(report)
}
