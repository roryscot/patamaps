use crate::{model::*, util::*};
use patamaps_contracts::{ContractError, canonical_bytes};
use serde_json::{Map, Value};
use std::collections::{BTreeMap, BTreeSet};

struct Requirements(BTreeMap<Vec<u16>, GovernanceRequirement>);
impl Requirements {
    fn add(&mut self, action: GovernanceAction, subject: &str, fact: &str) -> Result<()> {
        let requirement = GovernanceRequirement {
            action,
            subject: subject.into(),
            fact: fact.into(),
        };
        let key = String::from_utf8(canonical_bytes(&requirement)?)
            .expect("canonical UTF-8")
            .encode_utf16()
            .collect();
        self.0.insert(key, requirement);
        if self.0.len() > 100_000 {
            return fail(
                "GOVERNANCE_RESOURCE_LIMIT",
                "Computed delta exceeds requirement bound",
            );
        }
        Ok(())
    }
}
fn properties(
    before: Option<&Map<String, Value>>,
    after: Option<&Map<String, Value>>,
) -> Vec<String> {
    before
        .into_iter()
        .flat_map(|o| o.keys())
        .chain(after.into_iter().flat_map(|o| o.keys()))
        .collect::<BTreeSet<_>>()
        .into_iter()
        .filter(|key| before.and_then(|o| o.get(*key)) != after.and_then(|o| o.get(*key)))
        .cloned()
        .collect()
}
fn records<'a>(graph: Option<&'a Value>, kind: &str) -> BTreeMap<&'a str, &'a Value> {
    graph
        .and_then(|g| g[kind].as_array())
        .into_iter()
        .flatten()
        .map(|r| (r["id"].as_str().expect("checked record identity"), r))
        .collect()
}
fn limit_raised(before: &Value, after: &Value, key: &str) -> bool {
    match (before[key].as_f64(), after[key].as_f64()) {
        (Some(a), Some(b)) => b > a,
        (Some(_), None) => true,
        _ => false,
    }
}
fn policy_changes(req: &mut Requirements, before: Option<&Value>, after: &Value) -> Result<()> {
    let id = after["id"].as_str().expect("checked policy identity");
    for key in properties(before.and_then(Value::as_object), after.as_object()) {
        if ["schemaVersion", "documentType", "graph"].contains(&key.as_str()) {
            continue;
        }
        let fact = format!("policy.{key}");
        req.add(GovernanceAction::ChangePolicy, id, &fact)?;
        if ["constraints", "mappings"].contains(&key.as_str()) {
            req.add(GovernanceAction::RelaxPolicy, id, &fact)?;
        }
    }
    for key in properties(
        before.and_then(|p| p["semantics"].as_object()),
        after["semantics"].as_object(),
    ) {
        let fact = format!("policy.{key}");
        req.add(GovernanceAction::ChangePolicy, id, &fact)?;
        if ["uncertaintyRequirements", "derivationLimits"].contains(&key.as_str()) {
            req.add(GovernanceAction::RelaxPolicy, id, &fact)?;
        }
    }
    let old_budgets = records(before.map(|v| &v["semantics"]), "riskBudgets");
    let new_budgets = records(Some(&after["semantics"]), "riskBudgets");
    for id in old_budgets
        .keys()
        .chain(new_budgets.keys())
        .copied()
        .collect::<BTreeSet<_>>()
    {
        let raised = match (old_budgets.get(id), new_budgets.get(id)) {
            (Some(a), Some(b)) => {
                [
                    "maximumTotalCost",
                    "maximumLossyMappings",
                    "maximumInferredMappings",
                ]
                .iter()
                .any(|key| limit_raised(a, b, key))
                    || a["classifications"] != b["classifications"]
                    || a["consumer"] != b["consumer"]
            }
            _ => true,
        };
        if raised {
            req.add(GovernanceAction::RaiseBudget, id, "risk-budget")?;
        }
    }
    let old_waivers = records(before, "waivers");
    let new_waivers = records(Some(after), "waivers");
    for (id, w) in new_waivers {
        if old_waivers.get(id).copied() != Some(w) {
            req.add(GovernanceAction::AddWaiver, id, "waiver")?;
        }
    }
    Ok(())
}
/// Conservative complete delta classification; no grants are inferred here.
pub fn change_requirements(
    before: Option<&GovernedCandidate>,
    after: &GovernedCandidate,
    consumer: &str,
    intent: DeploymentIntent,
) -> Result<Vec<GovernanceRequirement>> {
    // Public callers receive the same admission/bounds as proposal creation.
    let after = crate::artifacts::normalized_candidate(after, consumer)?;
    let before = before
        .map(|b| crate::artifacts::normalized_candidate(b, consumer))
        .transpose()?;
    classified_requirements(before.as_ref(), &after, consumer, intent)
}
pub(crate) fn classified_requirements(
    before: Option<&GovernedCandidate>,
    after: &GovernedCandidate,
    consumer: &str,
    intent: DeploymentIntent,
) -> Result<Vec<GovernanceRequirement>> {
    let mut req = Requirements(BTreeMap::new());
    req.add(GovernanceAction::Activate, consumer, "activation")?;
    if before.is_none() {
        req.add(GovernanceAction::Bootstrap, consumer, "activation")?;
    }
    if intent == DeploymentIntent::Rollback {
        req.add(GovernanceAction::Rollback, consumer, "activation")?;
    }
    let b = before.map(|b| &b.captures[0]);
    let a = &after.captures[0];
    let old_graph = b
        .map(|b| serde_json::to_value(&b.inputs.graph))
        .transpose()
        .map_err(ContractError::from)?;
    let graph = serde_json::to_value(&a.inputs.graph).map_err(ContractError::from)?;
    for (array, kind) in [
        ("entities", "entity"),
        ("mappings", "mapping"),
        ("authorities", "authority"),
    ] {
        let old = records(old_graph.as_ref(), array);
        let new = records(Some(&graph), array);
        for id in old
            .keys()
            .chain(new.keys())
            .copied()
            .collect::<BTreeSet<_>>()
        {
            let (prev, next) = (old.get(id).copied(), new.get(id).copied());
            if prev == next {
                continue;
            }
            if kind == "authority" {
                req.add(GovernanceAction::ChangeAuthority, id, "authority.record")?;
                for r in [prev, next].into_iter().flatten() {
                    for fact in r["facts"].as_array().expect("checked authority scope") {
                        req.add(
                            GovernanceAction::ChangeAuthority,
                            r["concept"].as_str().expect("checked concept"),
                            &format!("ownership:{}", fact.as_str().expect("checked fact")),
                        )?;
                    }
                }
            } else if prev.is_none() || next.is_none() {
                req.add(GovernanceAction::ChangeGraph, id, &format!("{kind}.record"))?;
            } else {
                for key in properties(
                    prev.and_then(Value::as_object),
                    next.and_then(Value::as_object),
                ) {
                    let action = if (kind == "entity" && key == "locators")
                        || (kind == "mapping"
                            && ["sources", "targets", "transform"].contains(&key.as_str()))
                    {
                        GovernanceAction::RebindImplementation
                    } else {
                        GovernanceAction::ChangeGraph
                    };
                    req.add(action, id, &format!("{kind}.{key}"))?;
                }
            }
        }
    }
    for key in properties(
        old_graph.as_ref().and_then(Value::as_object),
        graph.as_object(),
    ) {
        if ![
            "schemaVersion",
            "documentType",
            "entities",
            "mappings",
            "authorities",
        ]
        .contains(&key.as_str())
        {
            req.add(
                GovernanceAction::ChangeGraph,
                &a.inputs.graph.id,
                &format!("graph.{key}"),
            )?;
        }
    }
    let old_policy = b
        .map(|b| serde_json::to_value(&b.inputs.policy))
        .transpose()
        .map_err(ContractError::from)?;
    policy_changes(
        &mut req,
        old_policy.as_ref(),
        &serde_json::to_value(&a.inputs.policy).map_err(ContractError::from)?,
    )?;
    if !equal(&b.map(|b| &b.inputs.packs), &Some(&a.inputs.packs))?
        || !equal(
            &b.and_then(|b| b.inputs.graph.relation_packs.as_ref()),
            &a.inputs.graph.relation_packs,
        )?
    {
        req.add(
            GovernanceAction::ChangeLaw,
            &a.inputs.graph.id,
            "relation-packs",
        )?;
    }
    let old_sources: BTreeMap<_, _> = b
        .into_iter()
        .flat_map(|b| &b.sources)
        .map(|s| (&s.id, s))
        .collect();
    let new_sources: BTreeMap<_, _> = a.sources.iter().map(|s| (&s.id, s)).collect();
    for id in old_sources
        .keys()
        .chain(new_sources.keys())
        .copied()
        .collect::<BTreeSet<_>>()
    {
        if !equal(&old_sources.get(id), &new_sources.get(id))? {
            req.add(GovernanceAction::ChangeSource, id, "source.record")?;
        }
    }
    for (fact, different) in [
        (
            "evaluation-context",
            !equal(&b.map(|b| &b.inputs.context), &Some(&a.inputs.context))?,
        ),
        (
            "evaluation-time",
            b.map(|b| &b.inputs.evaluated_at) != Some(&a.inputs.evaluated_at),
        ),
    ] {
        if different {
            req.add(GovernanceAction::ChangeContext, consumer, fact)?;
        }
    }
    let old_specs = before.map(|b| {
        b.captures
            .iter()
            .map(|c| &c.inputs.projection_spec)
            .collect::<Vec<_>>()
    });
    let specs = after
        .captures
        .iter()
        .map(|c| &c.inputs.projection_spec)
        .collect::<Vec<_>>();
    if !equal(&old_specs, &Some(specs))?
        || !equal(&before.map(|b| &b.emissions), &Some(&after.emissions))?
    {
        req.add(
            GovernanceAction::ChangeProjection,
            consumer,
            "projection-specifications",
        )?;
    }
    Ok(req.0.into_values().collect())
}
