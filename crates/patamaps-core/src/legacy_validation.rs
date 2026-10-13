//! Read-only validation of the legacy graph 2.0 data contract.
//! These reports cannot construct a checked graph or admitted generation.
//! Adapted from MetaMap 0.7.1 validator.ts at
//! 399747a4ad05a37cd8db1cedd53048fad2175be4 (Apache-2.0, Rory Dahl).
use crate::{RelationRegistry, Severity};
use patamaps_contracts::{Cardinality, Relation};
use serde::Serialize;
use serde_json::Value;
use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyValidationIssue {
    pub severity: Severity,
    pub code: String,
    pub message: String,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subject_id: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct LegacyValidationResult {
    pub valid: bool,
    pub issues: Vec<LegacyValidationIssue>,
}

/// Only the registry observations used by legacy document validation. A host
/// can retain live registration keys without rebuilding or admitting a native
/// registry whenever its caller-owned pack objects change.
pub trait LegacyValidationRegistry {
    fn legacy_has_pack(&self, id: &str, version: Option<&str>) -> bool;
    fn legacy_definition(&self, id: &str) -> Option<&Relation>;
    fn legacy_definitions(&self) -> Vec<&Relation>;
}
impl LegacyValidationRegistry for RelationRegistry {
    fn legacy_has_pack(&self, id: &str, version: Option<&str>) -> bool {
        self.has_pack(id, version)
    }
    fn legacy_definition(&self, id: &str) -> Option<&Relation> {
        self.get(id)
    }
    fn legacy_definitions(&self) -> Vec<&Relation> {
        self.all().collect()
    }
}

fn add(
    issues: &mut Vec<LegacyValidationIssue>,
    severity: Severity,
    code: &str,
    message: impl Into<String>,
    path: impl Into<String>,
    subject: Option<&str>,
) {
    issues.push(LegacyValidationIssue {
        severity,
        code: code.into(),
        message: message.into(),
        path: path.into(),
        subject_id: subject.map(str::to_owned),
    });
}
fn error(
    issues: &mut Vec<LegacyValidationIssue>,
    code: &str,
    message: impl Into<String>,
    path: impl Into<String>,
) {
    add(issues, Severity::Error, code, message, path, None);
}
fn nonempty(value: &Value) -> bool {
    value.as_str().is_some_and(|v| !v.is_empty())
}

// JavaScript \S excludes its specified whitespace/line terminators, rather
// than Rust's broader Unicode White_Space property (for example U+0085).
fn reference(value: &Value) -> bool {
    let Some(value) = value.as_str() else {
        return false;
    };
    let Some((scheme, rest)) = value.split_once(':') else {
        return false;
    };
    scheme.starts_with(|c: char| c.is_ascii_alphabetic()) && scheme.bytes().all(|c| c.is_ascii_alphanumeric() || b"+.-".contains(&c))
        && !rest.is_empty() && !value.chars().any(|c| matches!(c, '\u{0009}'..='\u{000d}' | '\u{0020}' | '\u{00a0}' | '\u{1680}' | '\u{2000}'..='\u{200a}' | '\u{2028}' | '\u{2029}' | '\u{202f}' | '\u{205f}' | '\u{3000}' | '\u{feff}'))
}
fn strings(
    value: &Value,
    path: &str,
    issues: &mut Vec<LegacyValidationIssue>,
    non_empty: bool,
    identifiers: bool,
) {
    let Some(values) = value.as_array() else {
        error(issues, "EXPECTED_ARRAY", "Expected an array", path);
        return;
    };
    if non_empty && values.is_empty() {
        error(issues, "EMPTY_ARRAY", "Array must not be empty", path);
    }
    for (index, value) in values.iter().enumerate() {
        let path = format!("{path}[{index}]");
        if !nonempty(value) {
            error(
                issues,
                "EXPECTED_STRING",
                "Expected a non-empty string",
                path,
            );
        } else if identifiers && !reference(value) {
            error(
                issues,
                "INVALID_IDENTIFIER",
                format!(
                    "Expected a URI-like identifier, received {}",
                    value.as_str().unwrap()
                ),
                path,
            );
        }
    }
}
fn provenance(value: &Value, path: &str, issues: &mut Vec<LegacyValidationIssue>) {
    if !value.is_object() {
        error(issues, "INVALID_PROVENANCE", "Expected an object", path);
        return;
    }
    if !value["status"]
        .as_str()
        .is_some_and(|v| ["declared", "observed", "generated", "inferred"].contains(&v))
    {
        error(
            issues,
            "INVALID_PROVENANCE_STATUS",
            "Provenance status must be declared, observed, generated, or inferred",
            format!("{path}.status"),
        );
    }
    if !nonempty(&value["assertedBy"]) {
        error(
            issues,
            "INVALID_ASSERTER",
            "Provenance assertedBy must be a non-empty string",
            format!("{path}.assertedBy"),
        );
    }
    if value.get("confidence").is_some()
        && !value["confidence"]
            .as_f64()
            .is_some_and(|v| (0.0..=1.0).contains(&v))
    {
        error(
            issues,
            "INVALID_CONFIDENCE",
            "Confidence must be between 0 and 1",
            format!("{path}.confidence"),
        );
    }
}

/// Preserve the original shape diagnostic sequence and JSON paths. Open
/// metadata and unrecognized fields remain in the caller's original Value.
pub fn validate_legacy_document_shape(value: &Value) -> Vec<LegacyValidationIssue> {
    let mut issues = Vec::new();
    if !value.is_object() {
        error(
            &mut issues,
            "INVALID_DOCUMENT",
            "Metamap document must be an object",
            "$",
        );
        return issues;
    }
    if value["schemaVersion"] != "2.0.0" {
        error(
            &mut issues,
            "UNSUPPORTED_SCHEMA_VERSION",
            "Expected schemaVersion 2.0.0",
            "$.schemaVersion",
        );
    }
    if !reference(&value["id"]) {
        error(
            &mut issues,
            "INVALID_DOCUMENT_ID",
            "Document id must be URI-like",
            "$.id",
        );
    }
    if !nonempty(&value["namespace"]) {
        error(
            &mut issues,
            "INVALID_NAMESPACE",
            "Namespace must be a non-empty string",
            "$.namespace",
        );
    }
    if let Some(packs) = value.get("relationPacks") {
        if let Some(packs) = packs.as_array() {
            for (index, pack) in packs.iter().enumerate() {
                let path = format!("$.relationPacks[{index}]");
                if !pack.is_object() {
                    error(
                        &mut issues,
                        "INVALID_RELATION_PACK_REFERENCE",
                        "Relation pack reference must be an object",
                        path,
                    );
                    continue;
                }
                if !reference(&pack["id"]) {
                    error(
                        &mut issues,
                        "INVALID_IDENTIFIER",
                        "Relation pack id must be URI-like",
                        format!("{path}.id"),
                    );
                }
                if !nonempty(&pack["version"]) {
                    error(
                        &mut issues,
                        "INVALID_RELATION_PACK_VERSION",
                        "Relation pack version must be a non-empty string",
                        format!("{path}.version"),
                    );
                }
            }
        } else {
            error(
                &mut issues,
                "EXPECTED_ARRAY",
                "Relation packs must be an array",
                "$.relationPacks",
            );
        }
    }
    for (field, code, label) in [
        ("entities", "INVALID_ENTITY", "Entity"),
        ("mappings", "INVALID_MAPPING", "Mapping"),
        ("authorities", "INVALID_AUTHORITY", "Authority"),
    ] {
        let Some(entries) = value[field].as_array() else {
            error(
                &mut issues,
                "EXPECTED_ARRAY",
                "Expected an array",
                format!("$.{field}"),
            );
            continue;
        };
        for (index, entry) in entries.iter().enumerate() {
            let path = format!("$.{field}[{index}]");
            if !entry.is_object() {
                error(
                    &mut issues,
                    code,
                    format!("{label} must be an object"),
                    path,
                );
                continue;
            }
            match field {
                "entities" => {
                    if !reference(&entry["id"]) {
                        error(
                            &mut issues,
                            "INVALID_ENTITY_ID",
                            "Entity id must be URI-like",
                            format!("{path}.id"),
                        );
                    }
                    if !nonempty(&entry["kind"]) {
                        error(
                            &mut issues,
                            "INVALID_ENTITY_KIND",
                            "Entity kind is required",
                            format!("{path}.kind"),
                        );
                    }
                    if let Some(locators) = entry.get("locators") {
                        if let Some(locators) = locators.as_array() {
                            for (i, locator) in locators.iter().enumerate() {
                                if !locator.is_object() || !reference(&locator["uri"]) {
                                    error(
                                        &mut issues,
                                        "INVALID_LOCATOR",
                                        "Locator must have a URI-like uri",
                                        format!("{path}.locators[{i}]"),
                                    );
                                }
                            }
                        } else {
                            error(
                                &mut issues,
                                "EXPECTED_ARRAY",
                                "Locators must be an array",
                                format!("{path}.locators"),
                            );
                        }
                    }
                    if let Some(p) = entry.get("provenance") {
                        provenance(p, &format!("{path}.provenance"), &mut issues);
                    }
                }
                "mappings" => {
                    if !reference(&entry["id"]) {
                        error(
                            &mut issues,
                            "INVALID_MAPPING_ID",
                            "Mapping id must be URI-like",
                            format!("{path}.id"),
                        );
                    }
                    if !entry["relation"]
                        .as_str()
                        .is_some_and(crate::graph::relation_id)
                    {
                        error(
                            &mut issues,
                            "INVALID_RELATION_ID",
                            "Relation must use namespace:name form",
                            format!("{path}.relation"),
                        );
                    }
                    strings(
                        &entry["sources"],
                        &format!("{path}.sources"),
                        &mut issues,
                        true,
                        true,
                    );
                    strings(
                        &entry["targets"],
                        &format!("{path}.targets"),
                        &mut issues,
                        true,
                        true,
                    );
                    if !entry["cardinality"].as_str().is_some_and(|v| {
                        ["one-to-one", "one-to-many", "many-to-one", "many-to-many"].contains(&v)
                    }) {
                        error(
                            &mut issues,
                            "INVALID_CARDINALITY",
                            "Invalid mapping cardinality",
                            format!("{path}.cardinality"),
                        );
                    }
                    if !entry["lossiness"]
                        .as_str()
                        .is_some_and(|v| ["lossless", "lossy", "unknown"].contains(&v))
                    {
                        error(
                            &mut issues,
                            "INVALID_LOSSINESS",
                            "Invalid mapping lossiness",
                            format!("{path}.lossiness"),
                        );
                    }
                    provenance(
                        &entry["provenance"],
                        &format!("{path}.provenance"),
                        &mut issues,
                    );
                }
                _ => {
                    for key in ["id", "concept", "source"] {
                        if !reference(&entry[key]) {
                            error(
                                &mut issues,
                                "INVALID_IDENTIFIER",
                                format!("{key} must be URI-like"),
                                format!("{path}.{key}"),
                            );
                        }
                    }
                    strings(
                        &entry["facts"],
                        &format!("{path}.facts"),
                        &mut issues,
                        true,
                        false,
                    );
                    if !entry["mode"]
                        .as_str()
                        .is_some_and(|v| ["canonical", "delegated", "candidate"].contains(&v))
                    {
                        error(
                            &mut issues,
                            "INVALID_AUTHORITY_MODE",
                            "Invalid authority mode",
                            format!("{path}.mode"),
                        );
                    }
                    if entry["mode"] == "delegated" {
                        if !reference(&entry["delegatedFrom"]) {
                            error(
                                &mut issues,
                                "INVALID_DELEGATION_PARENT",
                                "Delegated authority must reference its parent declaration",
                                format!("{path}.delegatedFrom"),
                            );
                        }
                    } else if entry.get("delegatedFrom").is_some() {
                        error(
                            &mut issues,
                            "UNEXPECTED_DELEGATION_PARENT",
                            "Only delegated authority may declare delegatedFrom",
                            format!("{path}.delegatedFrom"),
                        );
                    }
                    provenance(
                        &entry["provenance"],
                        &format!("{path}.provenance"),
                        &mut issues,
                    );
                }
            }
        }
    }
    issues
}

fn text<'a>(value: &'a Value, key: &str) -> &'a str {
    value[key].as_str().expect("validated legacy shape")
}
fn entries<'a>(value: &'a Value, key: &str) -> &'a [Value] {
    value[key].as_array().expect("validated legacy shape")
}
fn duplicate(values: impl IntoIterator<Item = String>) -> bool {
    let mut seen = HashSet::new();
    values.into_iter().any(|v| !seen.insert(v))
}
fn cardinality(value: Cardinality) -> &'static str {
    match value {
        Cardinality::OneToOne => "one-to-one",
        Cardinality::OneToMany => "one-to-many",
        Cardinality::ManyToOne => "many-to-one",
        Cardinality::ManyToMany => "many-to-many",
    }
}

// Iterative DFS preserves the reference's first cycle and declaration order.
fn first_cycle<'a>(
    order: &[&'a str],
    adjacency: &HashMap<&'a str, Vec<&'a str>>,
) -> Option<Vec<&'a str>> {
    let mut visited = HashSet::new();
    let mut active = HashSet::new();
    for &start in order {
        if !visited.insert(start) {
            continue;
        }
        active.insert(start);
        let mut stack = vec![(start, 0usize)];
        while let Some((node, index)) = stack.last_mut() {
            let next = adjacency
                .get(node)
                .and_then(|targets| targets.get(*index))
                .copied();
            *index += 1;
            if let Some(next) = next {
                if active.contains(next) {
                    let at = stack.iter().position(|(node, _)| *node == next).unwrap();
                    let mut cycle = stack[at..]
                        .iter()
                        .map(|(node, _)| *node)
                        .collect::<Vec<_>>();
                    cycle.push(next);
                    return Some(cycle);
                }
                if visited.insert(next) {
                    active.insert(next);
                    stack.push((next, 0));
                }
            } else {
                active.remove(*node);
                stack.pop();
            }
        }
    }
    None
}

fn ancestor(id: &str, descendant: &str, authorities: &HashMap<&str, &Value>) -> bool {
    let mut current = authorities.get(descendant).copied();
    let mut visited = HashSet::new();
    while let Some(authority) = current {
        if authority["mode"] != "delegated" || !visited.insert(text(authority, "id")) {
            break;
        }
        if text(authority, "delegatedFrom") == id {
            return true;
        }
        current = authorities.get(text(authority, "delegatedFrom")).copied();
    }
    false
}
fn overlap(a: &Value, b: &Value) -> bool {
    entries(a, "facts").contains(&Value::from("*"))
        || entries(b, "facts").contains(&Value::from("*"))
        || entries(a, "facts")
            .iter()
            .any(|v| entries(b, "facts").contains(v))
}

/// Validate all legacy shape and semantic findings. No field, signed payload,
/// graph address or caller-owned data is rewritten by this read-only operation.
pub fn validate_legacy_document<R: LegacyValidationRegistry + ?Sized>(
    value: &Value,
    registry: &R,
) -> LegacyValidationResult {
    let mut issues = validate_legacy_document_shape(value);
    if issues.iter().any(|i| i.severity == Severity::Error) {
        return LegacyValidationResult {
            valid: false,
            issues,
        };
    }
    let mut seen: HashMap<&str, String> = HashMap::new();
    let entities: HashMap<_, _> = entries(value, "entities")
        .iter()
        .map(|v| (text(v, "id"), v))
        .collect();
    fn register<'a>(
        seen: &mut HashMap<&'a str, String>,
        entry: &'a Value,
        path: &str,
        issues: &mut Vec<LegacyValidationIssue>,
    ) {
        let id = text(entry, "id");
        if let Some(previous) = seen.get(id) {
            add(
                issues,
                Severity::Error,
                "DUPLICATE_ID",
                format!("Identifier {id} is already used at {previous}"),
                path,
                Some(id),
            );
        } else {
            seen.insert(id, path.into());
        }
    }
    for (index, entity) in entries(value, "entities").iter().enumerate() {
        let path = format!("$.entities[{index}]");
        register(&mut seen, entity, &format!("{path}.id"), &mut issues);
        if entity.get("locators").is_some_and(|v| {
            duplicate(
                v.as_array()
                    .unwrap()
                    .iter()
                    .map(|v| text(v, "uri").to_owned()),
            )
        }) {
            add(
                &mut issues,
                Severity::Warning,
                "DUPLICATE_LOCATOR",
                "Entity contains duplicate locators",
                format!("{path}.locators"),
                Some(text(entity, "id")),
            );
        }
    }
    for pack in value
        .get("relationPacks")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        if !registry.legacy_has_pack(text(pack, "id"), Some(text(pack, "version"))) {
            add(
                &mut issues,
                Severity::Error,
                "UNAVAILABLE_RELATION_PACK",
                format!(
                    "Relation pack {}@{} is not registered",
                    text(pack, "id"),
                    text(pack, "version")
                ),
                "$.relationPacks",
                Some(text(pack, "id")),
            );
        }
    }
    for (index, mapping) in entries(value, "mappings").iter().enumerate() {
        let path = format!("$.mappings[{index}]");
        let id = text(mapping, "id");
        let relation = text(mapping, "relation");
        register(&mut seen, mapping, &format!("{path}.id"), &mut issues);
        for side in ["sources", "targets"] {
            if duplicate(
                entries(mapping, side)
                    .iter()
                    .map(|v| v.as_str().unwrap().to_owned()),
            ) {
                add(
                    &mut issues,
                    Severity::Error,
                    "DUPLICATE_ENDPOINT",
                    format!("Mapping {side} must be unique"),
                    format!("{path}.{side}"),
                    Some(id),
                );
            }
        }
        let definition = registry.legacy_definition(relation);
        if let Some(definition) = definition {
            let card = text(mapping, "cardinality");
            let sources = entries(mapping, "sources").len();
            let targets = entries(mapping, "targets").len();
            if definition
                .cardinalities
                .as_ref()
                .is_some_and(|values| !values.iter().any(|v| cardinality(*v) == card))
            {
                add(
                    &mut issues,
                    Severity::Error,
                    "UNSUPPORTED_CARDINALITY",
                    format!("{relation} does not allow {card}"),
                    format!("{path}.cardinality"),
                    Some(id),
                );
            }
            let matches = match card {
                "one-to-one" => sources == 1 && targets == 1,
                "one-to-many" => sources == 1,
                "many-to-one" => targets == 1,
                _ => true,
            };
            if !matches {
                add(
                    &mut issues,
                    Severity::Error,
                    "CARDINALITY_MISMATCH",
                    format!("{card} does not match {sources} source(s) and {targets} target(s)"),
                    &path,
                    Some(id),
                );
            }
        } else {
            add(
                &mut issues,
                Severity::Error,
                "UNKNOWN_RELATION",
                format!("Relation {relation} is not registered"),
                format!("{path}.relation"),
                Some(id),
            );
        }
        for side in ["sources", "targets"] {
            for (i, endpoint) in entries(mapping, side).iter().enumerate() {
                let endpoint = endpoint.as_str().unwrap();
                let endpoint_path = format!("{path}.{side}[{i}]");
                if let Some(entity) = entities.get(endpoint) {
                    let kinds = definition.and_then(|d| {
                        if side == "sources" {
                            d.source_kinds.as_ref()
                        } else {
                            d.target_kinds.as_ref()
                        }
                    });
                    let kind = text(entity, "kind");
                    if kinds.is_some_and(|kinds| !kinds.iter().any(|k| k == "*" || k == kind)) {
                        add(
                            &mut issues,
                            Severity::Error,
                            "INVALID_ENDPOINT_KIND",
                            format!("{relation} does not allow {kind} on {side}"),
                            endpoint_path,
                            Some(id),
                        );
                    }
                } else {
                    add(
                        &mut issues,
                        Severity::Error,
                        "UNRESOLVED_ENDPOINT",
                        format!("Mapping endpoint {endpoint} does not resolve"),
                        endpoint_path,
                        Some(id),
                    );
                }
            }
        }
    }
    let authorities = entries(value, "authorities");
    for (index, authority) in authorities.iter().enumerate() {
        let path = format!("$.authorities[{index}]");
        let id = text(authority, "id");
        register(&mut seen, authority, &format!("{path}.id"), &mut issues);
        for (key, code, label) in [
            ("concept", "UNRESOLVED_CONCEPT", "Authority concept"),
            ("source", "UNRESOLVED_AUTHORITY_SOURCE", "Authority source"),
        ] {
            if !entities.contains_key(text(authority, key)) {
                add(
                    &mut issues,
                    Severity::Error,
                    code,
                    format!("{label} {} does not resolve", text(authority, key)),
                    format!("{path}.{key}"),
                    Some(id),
                );
            }
        }
        if duplicate(
            entries(authority, "facts")
                .iter()
                .map(|v| v.as_str().unwrap().to_owned()),
        ) {
            add(
                &mut issues,
                Severity::Error,
                "DUPLICATE_FACT",
                "Authority facts must be unique",
                format!("{path}.facts"),
                Some(id),
            );
        }
        if authority["mode"] == "candidate" {
            add(
                &mut issues,
                Severity::Warning,
                "UNRESOLVED_AUTHORITY",
                format!(
                    "Authority for {} remains a candidate",
                    text(authority, "concept")
                ),
                path,
                Some(id),
            );
        }
    }
    let by_id: HashMap<_, _> = authorities.iter().map(|v| (text(v, "id"), v)).collect();
    let canonical: Vec<_> = authorities
        .iter()
        .filter(|v| v["mode"] == "canonical")
        .collect();
    for (i, a) in canonical.iter().enumerate() {
        for b in &canonical[i + 1..] {
            if a["concept"] == b["concept"] && overlap(a, b) {
                add(
                    &mut issues,
                    Severity::Error,
                    "AUTHORITY_CONFLICT",
                    format!(
                        "Canonical authorities {} and {} overlap for {}",
                        text(a, "id"),
                        text(b, "id"),
                        text(a, "concept")
                    ),
                    "$.authorities",
                    Some(text(a, "concept")),
                );
            }
        }
    }
    let delegated: Vec<_> = authorities
        .iter()
        .filter(|v| v["mode"] == "delegated")
        .collect();
    for delegated in &delegated {
        let id = text(delegated, "id");
        let parent_id = text(delegated, "delegatedFrom");
        let Some(parent) = by_id.get(parent_id) else {
            add(
                &mut issues,
                Severity::Error,
                "UNRESOLVED_DELEGATION_PARENT",
                format!("Delegated authority {id} references missing parent {parent_id}"),
                "$.authorities",
                Some(id),
            );
            continue;
        };
        if parent["mode"] == "candidate" {
            add(
                &mut issues,
                Severity::Error,
                "INVALID_DELEGATION_PARENT",
                format!("Delegated authority {id} cannot descend from candidate {parent_id}"),
                "$.authorities",
                Some(id),
            );
        }
        if parent["concept"] != delegated["concept"] {
            add(
                &mut issues,
                Severity::Error,
                "DELEGATION_CONCEPT_MISMATCH",
                format!(
                    "Delegation {id} changes concept from {} to {}",
                    text(parent, "concept"),
                    text(delegated, "concept")
                ),
                "$.authorities",
                Some(id),
            );
        }
        let covers = entries(parent, "facts").contains(&Value::from("*"))
            || (!entries(delegated, "facts").contains(&Value::from("*"))
                && entries(delegated, "facts")
                    .iter()
                    .all(|v| entries(parent, "facts").contains(v)));
        if !covers {
            add(
                &mut issues,
                Severity::Error,
                "DELEGATION_FACT_WIDENING",
                format!("Delegation {id} contains facts not owned by {parent_id}"),
                "$.authorities",
                Some(id),
            );
        }
    }
    for (i, a) in delegated.iter().enumerate() {
        for b in &delegated[i + 1..] {
            if a["concept"] == b["concept"]
                && overlap(a, b)
                && !ancestor(text(a, "id"), text(b, "id"), &by_id)
                && !ancestor(text(b, "id"), text(a, "id"), &by_id)
            {
                add(
                    &mut issues,
                    Severity::Error,
                    "DELEGATION_BRANCH_CONFLICT",
                    format!(
                        "Delegated authorities {} and {} overlap without an ancestor relationship",
                        text(a, "id"),
                        text(b, "id")
                    ),
                    "$.authorities",
                    Some(text(a, "concept")),
                );
            }
        }
    }
    let order: Vec<_> = authorities.iter().map(|v| text(v, "id")).collect();
    let adjacency: HashMap<_, _> = by_id
        .iter()
        .filter(|(_, v)| v["mode"] == "delegated")
        .map(|(&id, v)| (id, vec![text(v, "delegatedFrom")]))
        .collect();
    if let Some(cycle) = first_cycle(&order, &adjacency) {
        add(
            &mut issues,
            Severity::Error,
            "DELEGATION_CYCLE",
            format!(
                "Authority delegation contains a cycle: {}",
                cycle.join(" -> ")
            ),
            "$.authorities",
            Some(cycle[0]),
        );
    }
    for definition in registry
        .legacy_definitions()
        .into_iter()
        .filter(|v| v.cycle_policy == patamaps_contracts::CyclePolicy::Forbid)
    {
        let mut order = Vec::new();
        let mut adjacency: HashMap<&str, Vec<&str>> = HashMap::new();
        for mapping in entries(value, "mappings")
            .iter()
            .filter(|v| v["relation"] == definition.id)
        {
            for source in entries(mapping, "sources") {
                let source = source.as_str().unwrap();
                if !adjacency.contains_key(source) {
                    order.push(source);
                }
                let targets = adjacency.entry(source).or_default();
                for target in entries(mapping, "targets") {
                    let target = target.as_str().unwrap();
                    if !targets.contains(&target) {
                        targets.push(target);
                    }
                }
            }
        }
        if let Some(cycle) = first_cycle(&order, &adjacency) {
            add(
                &mut issues,
                Severity::Error,
                "FORBIDDEN_RELATION_CYCLE",
                format!("{} contains a cycle: {}", definition.id, cycle.join(" -> ")),
                "$.mappings",
                Some(&definition.id),
            );
        }
    }
    LegacyValidationResult {
        valid: !issues.iter().any(|i| i.severity == Severity::Error),
        issues,
    }
}
