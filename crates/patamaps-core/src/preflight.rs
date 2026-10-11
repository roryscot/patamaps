use crate::{CheckError, Issue};
use patamaps_contracts::*;

/// Resource and recursion guard before SDK inputs are cloned or encoded.
/// This returns no validated capability and does not replace admission.
pub fn check_input_bounds(
    graph: &GraphDocument,
    packs: &[RelationPack],
    policy: &PolicyDocument,
    context: &JsonObject,
) -> Result<(), CheckError> {
    if graph.entities.len() > crate::graph::MAX_ENTITIES
        || graph.mappings.len() > crate::graph::MAX_MAPPINGS
        || graph.authorities.len() > crate::graph::MAX_AUTHORITIES
        || packs.len() > 64
        || graph
            .mappings
            .iter()
            .map(|m| m.sources.len().saturating_add(m.targets.len()))
            .sum::<usize>()
            > crate::graph::MAX_ENDPOINTS
    {
        return Err(CheckError(vec![Issue::error(
            "GRAPH_RESOURCE_LIMIT",
            "SDK input exceeds graph inventory limits before cloning",
            &graph.id,
        )]));
    }
    if policy.mappings.len() > 100_000
        || policy.constraints.len() > 10_000
        || policy.evidence.len() > 100_000
        || policy.waivers.as_ref().is_some_and(|w| w.len() > 1_000)
        || policy
            .semantics
            .as_ref()
            .is_some_and(|s| s.derivations.len() > 10_000)
    {
        return Err(CheckError(vec![Issue::error(
            "POLICY_RESOURCE_LIMIT",
            "SDK input exceeds policy inventory limits before cloning",
            &policy.id,
        )]));
    }
    crate::graph::metadata_bounds(graph)?;
    for pack in packs {
        for law in pack.laws.iter().flatten() {
            if let Some(context) = law.conditions.as_ref().and_then(|c| c.context.as_ref()) {
                expression_bounds(context, &law.id)?;
            }
        }
    }
    crate::graph::object_bounds(
        std::iter::once((context, 2)),
        &policy.id,
        "POLICY_RESOURCE_LIMIT",
    )?;
    crate::graph::object_bounds(
        policy
            .metadata
            .iter()
            .map(|v| (v, 2))
            .chain(
                policy
                    .evidence
                    .iter()
                    .filter_map(|e| e.attributes.as_ref())
                    .map(|v| (v, 4)),
            )
            .chain(
                policy
                    .constraints
                    .iter()
                    .filter_map(|c| c.parameters.as_ref())
                    .map(|v| (v, 4)),
            ),
        &policy.id,
        "POLICY_RESOURCE_LIMIT",
    )?;
    if let Some(semantics) = &policy.semantics {
        for proof in &semantics.derivations {
            crate::graph::object_bounds(
                std::iter::once((&proof.context, 3))
                    .chain(proof.result.attributes.iter().map(|v| (v, 5)))
                    .chain(
                        proof
                            .result
                            .transform
                            .iter()
                            .filter_map(|t| t.configuration.as_ref())
                            .map(|v| (v, 6)),
                    ),
                &proof.id,
                "DERIVATION_RESOURCE_LIMIT",
            )?;
        }
    }
    for declaration in &policy.mappings {
        if let Some(applicability) = &declaration.applicability {
            for expr in [&applicability.when, &applicability.unless]
                .into_iter()
                .flatten()
            {
                expression_bounds(expr, &policy.id)?;
            }
        }
    }
    Ok(())
}

fn expression_bounds(expr: &ContextExpression, subject: &str) -> Result<(), CheckError> {
    let mut stack = vec![(expr, 0usize)];
    let mut nodes = 0usize;
    while let Some((expr, depth)) = stack.pop() {
        nodes += 1;
        if depth > MAX_JSON_DEPTH || nodes > MAX_JSON_VALUES {
            return Err(CheckError(vec![Issue::error(
                "POLICY_RESOURCE_LIMIT",
                "Context expression exceeds depth/value bounds",
                subject,
            )]));
        }
        match expr {
            ContextExpression::All { all } => stack.extend(all.iter().map(|e| (e, depth + 1))),
            ContextExpression::Any { any } => stack.extend(any.iter().map(|e| (e, depth + 1))),
            ContextExpression::Not { not } => stack.push((not, depth + 1)),
            ContextExpression::Comparison { value, .. } => value_bounds(value, subject)?,
            ContextExpression::Membership { values, .. } => {
                for v in values {
                    value_bounds(v, subject)?;
                }
            }
            ContextExpression::Exists { .. } => {}
        }
    }
    Ok(())
}
fn value_bounds(value: &serde_json::Value, subject: &str) -> Result<(), CheckError> {
    let mut stack = vec![(value, 0usize)];
    let mut nodes = 0usize;
    while let Some((v, depth)) = stack.pop() {
        nodes += 1;
        if depth > MAX_JSON_DEPTH || nodes > MAX_JSON_VALUES {
            return Err(CheckError(vec![Issue::error(
                "POLICY_RESOURCE_LIMIT",
                "Expression value exceeds depth/value bounds",
                subject,
            )]));
        }
        match v {
            serde_json::Value::Object(o) => stack.extend(o.values().map(|v| (v, depth + 1))),
            serde_json::Value::Array(a) => stack.extend(a.iter().map(|v| (v, depth + 1))),
            _ => {}
        }
    }
    Ok(())
}

/// Iterative resource check before cloning or encoding untrusted result data.
pub fn check_value_bounds(
    value: &serde_json::Value,
    subject: &str,
    code: &str,
) -> Result<(), CheckError> {
    let mut stack = vec![(value, 0usize)];
    let (mut nodes, mut bytes) = (0usize, 0usize);
    while let Some((v, depth)) = stack.pop() {
        nodes += 1;
        bytes = bytes.saturating_add(1);
        if depth > MAX_JSON_DEPTH || nodes > MAX_JSON_VALUES || bytes > MAX_INPUT_BYTES {
            return Err(CheckError(vec![Issue::error(
                code,
                "JSON value exceeds depth/value/byte bounds",
                subject,
            )]));
        }
        match v {
            serde_json::Value::Object(o) => {
                for (k, v) in o {
                    bytes = bytes.saturating_add(k.len());
                    stack.push((v, depth + 1));
                }
            }
            serde_json::Value::Array(a) => stack.extend(a.iter().map(|v| (v, depth + 1))),
            serde_json::Value::String(s) => bytes = bytes.saturating_add(s.len()),
            _ => (),
        }
    }
    if bytes > MAX_INPUT_BYTES {
        return Err(CheckError(vec![Issue::error(
            code,
            "JSON value exceeds byte bound",
            subject,
        )]));
    }
    Ok(())
}
