use crate::admission::expr_valid;
use crate::graph::{finish, identifier};
use crate::{CheckError, Issue};
use patamaps_contracts::*;
use std::collections::{HashMap, HashSet};

pub(crate) fn preflight(packs: &[RelationPack]) -> Result<(), CheckError> {
    if packs
        .iter()
        .filter_map(|p| p.laws.as_ref())
        .map(Vec::len)
        .sum::<usize>()
        > 10_000
    {
        return Err(CheckError(vec![Issue::error(
            "LAW_RESOURCE_LIMIT",
            "At most 10,000 executable laws are supported",
            "packs",
        )]));
    }
    for p in packs {
        for law in p.laws.iter().flatten() {
            if law
                .conditions
                .as_ref()
                .and_then(|c| c.context.as_ref())
                .is_some_and(|c| !expr_valid(c, 0))
            {
                return Err(CheckError(vec![Issue::error(
                    "INVALID_LAW_CONTEXT",
                    "Invalid or excessively nested context expression",
                    &law.id,
                )]));
            }
        }
    }
    Ok(())
}

fn compatible(sets: &[Option<&Vec<String>>]) -> bool {
    let restricted: Vec<_> = sets.iter().flatten().collect();
    restricted.first().is_none_or(|first| {
        first
            .iter()
            .any(|k| restricted.iter().all(|s| s.contains(k)))
    })
}
fn unconditional(law: &RelationLaw) -> bool {
    law.conditions.as_ref().is_none_or(|c| {
        c.context.is_none()
            && c.source_kinds.is_none()
            && c.middle_kinds.is_none()
            && c.target_kinds.is_none()
    })
}

/// Registration is order independent, but exact imports form an acyclic graph.
pub(crate) fn validate(
    packs: &[RelationPack],
) -> Result<HashMap<String, (usize, usize)>, CheckError> {
    validate_with_digests(packs, |index| Ok(canonical_digest(&packs[index])?))
}

/// Legacy imports use their preserved original document addresses. The law
/// policy and dependency checks are shared with modern native registration.
pub(crate) fn validate_with_digests(
    packs: &[RelationPack],
    digest: impl Fn(usize) -> Result<String, CheckError>,
) -> Result<HashMap<String, (usize, usize)>, CheckError> {
    preflight(packs)?;
    let by_id: HashMap<_, _> = packs
        .iter()
        .enumerate()
        .map(|(i, p)| (p.id.as_str(), i))
        .collect();
    let mut issues = Vec::new();
    let mut laws = HashMap::new();
    let mut edges = vec![Vec::new(); packs.len()];
    let mut operations = 0usize;
    for (pi, p) in packs.iter().enumerate() {
        if p.laws.is_none() {
            if p.imports.is_some() || p.relations.iter().any(|r| r.disjoint_with.is_some()) {
                issues.push(Issue::error(
                    "EXECUTABLE_PACK_REQUIRED",
                    "Imports and disjointness require a pack with explicit laws",
                    &p.id,
                ));
            }
            continue;
        }
        let mut defs = HashMap::new();
        let mut imports = HashSet::new();
        for i in p.imports.iter().flatten() {
            if !imports.insert(&i.id) || i.id == p.id {
                issues.push(Issue::error(
                    "INVALID_PACK_IMPORT",
                    "Duplicate or self import",
                    &i.id,
                ));
                continue;
            }
            let Some(&dep) = by_id.get(i.id.as_str()) else {
                issues.push(Issue::error(
                    "MISSING_EXACT_PACK_IMPORT",
                    "Imported pack was not supplied",
                    &i.id,
                ));
                continue;
            };
            if i.version != packs[dep].version || i.digest != digest(dep)? {
                issues.push(Issue::error(
                    "PACK_IMPORT_BINDING_MISMATCH",
                    "Imported version/digest differs from exact supplied bytes",
                    &i.id,
                ));
            }
            edges[pi].push(dep);
            for r in &packs[dep].relations {
                if defs.insert(r.id.as_str(), r).is_some() {
                    issues.push(Issue::error(
                        "DUPLICATE_IMPORTED_RELATION",
                        "Imports must not duplicate relation definitions",
                        &r.id,
                    ));
                }
            }
        }
        for r in &p.relations {
            if defs.insert(r.id.as_str(), r).is_some() {
                issues.push(Issue::error(
                    "DUPLICATE_IMPORTED_RELATION",
                    "Owned definition conflicts with an import",
                    &r.id,
                ));
            }
        }
        let plaws = p.laws.as_ref().expect("executable pack");
        for (li, law) in plaws.iter().enumerate() {
            operations = operations.saturating_add(1 + defs.len());
            if operations > 20_000_000 {
                return Err(CheckError(vec![Issue::error(
                    "LAW_RESOURCE_LIMIT",
                    "Executable law registration work exceeds the declared limit",
                    &p.id,
                )]));
            }
            if !identifier(&law.id) || laws.insert(law.id.clone(), (pi, li)).is_some() {
                issues.push(Issue::error(
                    "DUPLICATE_OR_INVALID_LAW",
                    "Law identity must be valid and globally unique",
                    &law.id,
                ));
            }
            let arity = if law.operation == LawOperation::Reverse {
                1
            } else {
                2
            };
            if law.operands.len() != arity {
                issues.push(Issue::error(
                    "LAW_ARITY_MISMATCH",
                    "Reverse has one operand and chain has two ordered operands",
                    &law.id,
                ));
                continue;
            }
            let operands: Option<Vec<_>> = law
                .operands
                .iter()
                .map(|id| defs.get(id.as_str()).copied())
                .collect();
            let Some(result) = defs.get(law.result_relation.as_str()).copied() else {
                issues.push(Issue::error(
                    "LAW_RELATION_OUTSIDE_PACK",
                    "Result must belong to this pack or an exact direct import",
                    &law.id,
                ));
                continue;
            };
            let Some(operands) = operands else {
                issues.push(Issue::error(
                    "LAW_RELATION_OUTSIDE_PACK",
                    "Operands must belong to this pack or exact direct imports",
                    &law.id,
                ));
                continue;
            };
            let first = operands[0];
            let c = law.conditions.clone().unwrap_or_default();
            let mut bad = false;
            for list in [&c.source_kinds, &c.middle_kinds, &c.target_kinds]
                .into_iter()
                .flatten()
            {
                bad |= list.is_empty()
                    || list.iter().any(String::is_empty)
                    || list.iter().collect::<HashSet<_>>().len() != list.len();
            }
            if law.operation == LawOperation::Reverse {
                bad |= c.middle_kinds.is_some()
                    || !compatible(&[
                        first.target_kinds.as_ref(),
                        result.source_kinds.as_ref(),
                        c.source_kinds.as_ref(),
                    ])
                    || !compatible(&[
                        first.source_kinds.as_ref(),
                        result.target_kinds.as_ref(),
                        c.target_kinds.as_ref(),
                    ]);
                bad |= first.inverse.as_ref().is_some_and(|i| i != &result.id)
                    || (first.id == result.id && first.symmetric == Some(false));
            } else {
                let second = operands[1];
                bad |= !compatible(&[
                    first.target_kinds.as_ref(),
                    second.source_kinds.as_ref(),
                    c.middle_kinds.as_ref(),
                ]) || !compatible(&[
                    first.source_kinds.as_ref(),
                    result.source_kinds.as_ref(),
                    c.source_kinds.as_ref(),
                ]) || !compatible(&[
                    second.target_kinds.as_ref(),
                    result.target_kinds.as_ref(),
                    c.target_kinds.as_ref(),
                ]);
                bad |= first.id == second.id
                    && first.id == result.id
                    && first.transitive == Some(false);
            }
            if bad {
                issues.push(Issue::error(
                    "INCONSISTENT_RELATION_LAW",
                    "Law conditions, endpoint kinds or declared relation flags conflict",
                    &law.id,
                ));
            }
        }
        for r in &p.relations {
            let reverse = |target: &str| {
                plaws.iter().any(|l| {
                    unconditional(l)
                        && l.operation == LawOperation::Reverse
                        && l.operands == [r.id.clone()]
                        && l.result_relation == target
                })
            };
            if r.symmetric == Some(true) && !reverse(&r.id)
                || r.inverse
                    .as_ref()
                    .is_some_and(|i| !defs.contains_key(i.as_str()) || !reverse(i))
                || r.transitive == Some(true)
                    && !plaws.iter().any(|l| {
                        unconditional(l)
                            && l.operation == LawOperation::Chain
                            && l.operands == [r.id.clone(), r.id.clone()]
                            && l.result_relation == r.id
                    })
                || r.composes_with.iter().flatten().any(|other| {
                    !plaws.iter().any(|l| {
                        l.operation == LawOperation::Chain
                            && l.operands == [r.id.clone(), other.clone()]
                    })
                })
            {
                issues.push(Issue::error(
                    "MISSING_DECLARED_RELATION_LAW",
                    "Executable flags require matching declared laws",
                    &r.id,
                ));
            }
            if let Some(list) = &r.disjoint_with
                && (list.is_empty()
                    || list.iter().collect::<HashSet<_>>().len() != list.len()
                    || list
                        .iter()
                        .any(|i| i == &r.id || !defs.contains_key(i.as_str())))
            {
                issues.push(Issue::error(
                    "INVALID_DISJOINT_RELATION",
                    "Disjointness must reference unique other owned or imported relations",
                    &r.id,
                ));
            }
        }
    }
    // Kahn traversal avoids recursion on hostile pack-import cycles.
    let mut indegree = vec![0usize; packs.len()];
    let mut children = vec![Vec::new(); packs.len()];
    for (i, deps) in edges.iter().enumerate() {
        for &j in deps {
            indegree[i] += 1;
            children[j].push(i);
        }
    }
    let mut ready: Vec<_> = indegree
        .iter()
        .enumerate()
        .filter_map(|(i, &d)| (d == 0).then_some(i))
        .collect();
    let mut seen = 0;
    while let Some(i) = ready.pop() {
        seen += 1;
        for &j in &children[i] {
            indegree[j] -= 1;
            if indegree[j] == 0 {
                ready.push(j);
            }
        }
    }
    if seen != packs.len() {
        issues.push(Issue::error(
            "PACK_IMPORT_CYCLE",
            "Exact imports cannot contain a cycle",
            "packs",
        ));
    }
    finish(issues)?;
    Ok(laws)
}
