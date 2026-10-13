use patamaps_contracts::*;
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet, VecDeque};

pub const MAX_ENTITIES: usize = 200_000;
pub const MAX_MAPPINGS: usize = 100_000;
pub const MAX_AUTHORITIES: usize = 1_024;
pub const MAX_ENDPOINTS: usize = 1_000_000;
pub const MAX_RELATIONS: usize = 4_096;
pub const MAX_ISSUES: usize = 1_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Severity {
    Error,
    Warning,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Issue {
    pub severity: Severity,
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subject_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub waived_by: Option<String>,
}

impl Issue {
    pub fn error(code: &str, message: impl Into<String>, subject: impl Into<String>) -> Self {
        Self {
            severity: Severity::Error,
            code: code.into(),
            message: message.into(),
            subject_id: Some(subject.into()),
            waived_by: None,
        }
    }
}

#[derive(Debug, thiserror::Error)]
#[error("candidate rejected with {} issue(s)", .0.len())]
pub struct CheckError(pub Vec<Issue>);

impl From<ContractError> for CheckError {
    fn from(error: ContractError) -> Self {
        Self(vec![Issue::error(
            "INVALID_CANONICAL_VALUE",
            error.to_string(),
            "input",
        )])
    }
}

pub(crate) fn finish(mut issues: Vec<Issue>) -> Result<Vec<Issue>, CheckError> {
    issues.sort_by(|a, b| {
        (&a.severity, &a.code, &a.subject_id, &a.message).cmp(&(
            &b.severity,
            &b.code,
            &b.subject_id,
            &b.message,
        ))
    });
    issues.dedup();
    if issues.len() > MAX_ISSUES {
        issues.truncate(MAX_ISSUES);
        issues.push(Issue::error(
            "DIAGNOSTIC_LIMIT",
            "Diagnostics truncated; candidate remains rejected",
            "input",
        ));
    }
    if issues.iter().any(|i| i.severity == Severity::Error) {
        Err(CheckError(issues))
    } else {
        Ok(issues)
    }
}

pub fn identifier(value: &str) -> bool {
    let Some((scheme, rest)) = value.split_once(':') else {
        return false;
    };
    scheme.starts_with(|c: char| c.is_ascii_alphabetic())
        && scheme
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"+.-".contains(&c))
        && !rest.is_empty()
        && !value.chars().any(|c| c.is_whitespace() || c == '\u{feff}')
}

fn token(value: &str, punctuation: &[u8]) -> bool {
    value.starts_with(|c: char| c.is_ascii_alphabetic())
        && value
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || punctuation.contains(&c))
}

pub(crate) fn relation_id(value: &str) -> bool {
    let Some((a, b)) = value.split_once(':') else {
        return false;
    };
    [a, b].into_iter().all(|s| {
        s.starts_with(|c: char| c.is_ascii_lowercase())
            && s.bytes()
                .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || b"._-".contains(&c))
    })
}

fn duplicates(values: &[String]) -> bool {
    values.iter().collect::<HashSet<_>>().len() != values.len()
}

fn overlap(a: &[String], b: &[String]) -> bool {
    a.iter().any(|x| x == "*") || b.iter().any(|x| x == "*") || a.iter().any(|x| b.contains(x))
}

fn covers(a: &[String], b: &[String]) -> bool {
    a.iter().any(|x| x == "*") || (!b.iter().any(|x| x == "*") && b.iter().all(|x| a.contains(x)))
}

fn provenance(value: &Provenance, subject: &str, issues: &mut Vec<Issue>) {
    if value.asserted_by.is_empty() || value.source_revision.as_ref().is_some_and(String::is_empty)
    {
        issues.push(Issue::error(
            "INVALID_ASSERTER",
            "Attribution and present revision must be nonempty",
            subject,
        ));
    }
    if value
        .confidence
        .is_some_and(|n| !n.is_finite() || !(0.0..=1.0).contains(&n))
    {
        issues.push(Issue::error(
            "INVALID_CONFIDENCE",
            "Confidence must be finite and between zero and one",
            subject,
        ));
    }
    if value
        .observed_at
        .as_ref()
        .is_some_and(|s| crate::admission::timestamp(s).is_err())
    {
        issues.push(Issue::error(
            "INVALID_PROVENANCE_TIME",
            "Invalid observedAt timestamp",
            subject,
        ));
    }
}

pub(crate) fn metadata_bounds(document: &GraphDocument) -> Result<(), CheckError> {
    // SDK callers can construct Value trees without using strict JSON ingress.
    // Walk arbitrary metadata iteratively before any recursive serializer.
    let objects = document
        .metadata
        .iter()
        .map(|v| (v, 2))
        .chain(document.extensions.iter().map(|v| (v, 2)))
        .chain(
            document
                .entities
                .iter()
                .filter_map(|e| e.attributes.as_ref())
                .map(|v| (v, 4)),
        )
        .chain(
            document
                .mappings
                .iter()
                .filter_map(|m| m.attributes.as_ref())
                .map(|v| (v, 4)),
        )
        .chain(
            document
                .mappings
                .iter()
                .filter_map(|m| m.transform.as_ref())
                .filter_map(|t| t.configuration.as_ref())
                .map(|v| (v, 5)),
        );
    object_bounds(objects, &document.id, "GRAPH_RESOURCE_LIMIT")
}

pub fn object_bounds<'a>(
    objects: impl IntoIterator<Item = (&'a JsonObject, usize)>,
    subject: &str,
    code: &str,
) -> Result<(), CheckError> {
    object_bounds_with_limits(objects, subject, code, STRICT_JSON_LIMITS)
}

/// A structural guard for an explicitly selected ingress profile. It grants no
/// admitted capability; downstream graph/policy checks retain their own limits.
pub fn object_bounds_with_limits<'a>(
    objects: impl IntoIterator<Item = (&'a JsonObject, usize)>,
    subject: &str,
    code: &str,
    limits: JsonLimits,
) -> Result<(), CheckError> {
    let mut count = 0usize;
    for (object, initial_depth) in objects {
        let mut stack: Vec<_> = object.values().map(|v| (v, initial_depth)).collect();
        while let Some((value, depth)) = stack.pop() {
            count = count.saturating_add(1);
            if depth > limits.max_depth || count > limits.max_values {
                return Err(CheckError(vec![Issue::error(
                    code,
                    "Metadata exceeds JSON depth or value limits",
                    subject,
                )]));
            }
            match value {
                serde_json::Value::Object(o) => stack.extend(o.values().map(|v| (v, depth + 1))),
                serde_json::Value::Array(a) => stack.extend(a.iter().map(|v| (v, depth + 1))),
                _ => {}
            }
        }
    }
    Ok(())
}

/// Immutable graph and exact relation-pack context, constructed only by checking.
///
/// ```compile_fail
/// use patamaps_core::CheckedGraph;
/// let forged: CheckedGraph = serde_json::from_str("{}").unwrap();
/// ```
///
/// ```compile_fail
/// fn change(graph: &mut patamaps_core::CheckedGraph) {
///     graph.document().entities.clear();
/// }
/// ```
#[derive(Debug)]
pub struct CheckedGraph {
    document: GraphDocument,
    packs: Vec<RelationPack>,
    digest: String,
    entities: HashMap<String, usize>,
    mappings: HashMap<String, usize>,
    authorities: HashMap<String, usize>,
    incident: HashMap<String, Vec<usize>>,
    by_relation: HashMap<String, Vec<usize>>,
    by_concept: HashMap<String, Vec<usize>>,
    children: HashMap<String, Vec<usize>>,
    relations: HashMap<String, (usize, usize)>,
    laws: HashMap<String, (usize, usize)>,
    issues: Vec<Issue>,
}

impl CheckedGraph {
    pub fn check(document: GraphDocument, packs: Vec<RelationPack>) -> Result<Self, CheckError> {
        Self::check_internal(document, packs, None)
    }
    pub fn check_controlled(
        document: GraphDocument,
        packs: Vec<RelationPack>,
        control: &crate::WorkControl,
    ) -> Result<Self, CheckError> {
        Self::check_internal(document, packs, Some(control))
    }
    fn check_internal(
        document: GraphDocument,
        packs: Vec<RelationPack>,
        control: Option<&crate::WorkControl>,
    ) -> Result<Self, CheckError> {
        crate::control::poll(control)?;
        metadata_bounds(&document)?;
        let endpoints: usize = document
            .mappings
            .iter()
            .map(|m| m.sources.len().saturating_add(m.targets.len()))
            .sum();
        if document.entities.len() > MAX_ENTITIES
            || document.mappings.len() > MAX_MAPPINGS
            || document.authorities.len() > MAX_AUTHORITIES
            || endpoints > MAX_ENDPOINTS
            || packs.len() > 64
            || packs.iter().map(|p| p.relations.len()).sum::<usize>() > MAX_RELATIONS
            || document.authorities.iter().any(|a| a.facts.len() > 128)
        {
            return Err(CheckError(vec![Issue::error(
                "GRAPH_RESOURCE_LIMIT",
                "Graph exceeds the declared draft profile limits",
                &document.id,
            )]));
        }
        crate::laws::preflight(&packs)?;
        let packs: Vec<RelationPack> = parse(&canonical_bytes(&packs)?)?;
        let mut result = Self {
            document,
            packs,
            digest: String::new(),
            entities: HashMap::new(),
            mappings: HashMap::new(),
            authorities: HashMap::new(),
            incident: HashMap::new(),
            by_relation: HashMap::new(),
            by_concept: HashMap::new(),
            children: HashMap::new(),
            relations: HashMap::new(),
            laws: HashMap::new(),
            issues: Vec::new(),
        };
        let mut issues = Vec::new();
        let doc = &result.document;
        if !identifier(&doc.id) {
            issues.push(Issue::error(
                "INVALID_DOCUMENT_ID",
                "Invalid document identity",
                &doc.id,
            ));
        }
        if !token(&doc.namespace, b"._-") {
            issues.push(Issue::error(
                "INVALID_NAMESPACE",
                "Invalid namespace",
                &doc.id,
            ));
        }
        if doc.label.as_ref().is_some_and(String::is_empty)
            || doc.revision.as_ref().is_some_and(String::is_empty)
        {
            issues.push(Issue::error(
                "INVALID_DOCUMENT",
                "Present label and revision must be nonempty",
                &doc.id,
            ));
        }
        let mut ids = HashSet::new();
        for (index, entity) in doc.entities.iter().enumerate() {
            crate::control::poll(control)?;
            if !identifier(&entity.id) {
                issues.push(Issue::error(
                    "INVALID_ENTITY_ID",
                    "Invalid entity identity",
                    &entity.id,
                ));
            }
            if !ids.insert(&entity.id) {
                issues.push(Issue::error(
                    "DUPLICATE_ID",
                    "Identity is declared more than once",
                    &entity.id,
                ));
            }
            if entity.kind.is_empty() {
                issues.push(Issue::error(
                    "INVALID_ENTITY_KIND",
                    "Open entity kind must be nonempty",
                    &entity.id,
                ));
            }
            if entity.label.as_ref().is_some_and(String::is_empty)
                || entity.schema.as_ref().is_some_and(|s| !identifier(s))
            {
                issues.push(Issue::error(
                    "INVALID_ENTITY",
                    "Invalid label or schema reference",
                    &entity.id,
                ));
            }
            let mut locators = HashSet::new();
            for locator in entity.locators.iter().flatten() {
                if !identifier(&locator.uri) {
                    issues.push(Issue::error(
                        "INVALID_LOCATOR",
                        "Locator requires a scheme and nonempty reference",
                        &entity.id,
                    ));
                }
                if !locators.insert(&locator.uri) {
                    let mut duplicate = Issue::error(
                        "DUPLICATE_LOCATOR",
                        "Entity contains duplicate locators",
                        &entity.id,
                    );
                    duplicate.severity = Severity::Warning;
                    issues.push(duplicate);
                }
                if [&locator.media_type, &locator.revision, &locator.digest]
                    .iter()
                    .any(|v| v.as_ref().is_some_and(String::is_empty))
                {
                    issues.push(Issue::error(
                        "INVALID_LOCATOR",
                        "Present locator fields must be nonempty",
                        &entity.id,
                    ));
                }
            }
            if let Some(p) = &entity.provenance {
                provenance(p, &entity.id, &mut issues);
            }
            result.entities.insert(entity.id.clone(), index);
        }
        let mut pack_ids = HashMap::new();
        for (pi, pack) in result.packs.iter().enumerate() {
            crate::control::poll(control)?;
            if !identifier(&pack.id) || pack.version.is_empty() {
                issues.push(Issue::error(
                    "INVALID_RELATION_PACK",
                    "Invalid pack identity or version",
                    &pack.id,
                ));
            }
            if pack_ids.insert(pack.id.as_str(), pi).is_some() {
                issues.push(Issue::error(
                    "DUPLICATE_RELATION_PACK",
                    "A pack can be supplied only once",
                    &pack.id,
                ));
            }
            for (ri, relation) in pack.relations.iter().enumerate() {
                crate::control::poll(control)?;
                if !relation_id(&relation.id) {
                    issues.push(Issue::error(
                        "INVALID_RELATION_ID",
                        "Invalid relation token",
                        &relation.id,
                    ));
                }
                if result
                    .relations
                    .insert(relation.id.clone(), (pi, ri))
                    .is_some()
                {
                    issues.push(Issue::error(
                        "DUPLICATE_RELATION",
                        "A relation definition can have only one owner pack",
                        &relation.id,
                    ));
                }
                for kinds in [&relation.source_kinds, &relation.target_kinds]
                    .into_iter()
                    .flatten()
                {
                    if kinds.is_empty() || duplicates(kinds) || kinds.iter().any(String::is_empty) {
                        issues.push(Issue::error(
                            "INVALID_RELATION_PACK",
                            "Endpoint kind lists must be nonempty unique kind tokens",
                            &relation.id,
                        ));
                    }
                }
                if relation.cardinalities.as_ref().is_some_and(|v| {
                    v.is_empty() || (0..v.len()).any(|i| v[i + 1..].contains(&v[i]))
                }) {
                    issues.push(Issue::error(
                        "INVALID_RELATION_PACK",
                        "Allowed cardinalities must be nonempty and unique",
                        &relation.id,
                    ));
                }
            }
        }
        let mut refs = HashSet::new();
        for pack_ref in doc.relation_packs.iter().flatten() {
            if !refs.insert(&pack_ref.id) {
                issues.push(Issue::error(
                    "DUPLICATE_RELATION_PACK_REFERENCE",
                    "A graph pack reference can appear only once",
                    &pack_ref.id,
                ));
            }
            if !identifier(&pack_ref.id)
                || pack_ref.version.is_empty()
                || pack_ref.uri.as_ref().is_some_and(|s| !identifier(s))
            {
                issues.push(Issue::error(
                    "INVALID_RELATION_PACK_REFERENCE",
                    "Invalid pack reference",
                    &pack_ref.id,
                ));
            }
            if let Some(index) = pack_ids.get(pack_ref.id.as_str()) {
                let pack = &result.packs[*index];
                if pack_ref.version != pack.version
                    || pack_ref
                        .digest
                        .as_ref()
                        .is_some_and(|d| canonical_digest(pack).map_or(true, |value| value != *d))
                {
                    issues.push(Issue::error(
                        "RELATION_PACK_BINDING_MISMATCH",
                        "Supplied pack differs from its graph binding",
                        &pack_ref.id,
                    ));
                }
            } else {
                issues.push(Issue::error(
                    "UNAVAILABLE_RELATION_PACK",
                    "Referenced pack was not supplied",
                    &pack_ref.id,
                ));
            }
        }
        for (index, mapping) in doc.mappings.iter().enumerate() {
            crate::control::poll(control)?;
            if !identifier(&mapping.id) {
                issues.push(Issue::error(
                    "INVALID_MAPPING_ID",
                    "Invalid mapping identity",
                    &mapping.id,
                ));
            }
            if !ids.insert(&mapping.id) {
                issues.push(Issue::error(
                    "DUPLICATE_ID",
                    "Identity is declared more than once",
                    &mapping.id,
                ));
            }
            if mapping.sources.is_empty() || mapping.targets.is_empty() {
                issues.push(Issue::error(
                    "EMPTY_ARRAY",
                    "Both endpoint groups must be nonempty",
                    &mapping.id,
                ));
            }
            if duplicates(&mapping.sources) || duplicates(&mapping.targets) {
                issues.push(Issue::error(
                    "DUPLICATE_ENDPOINT",
                    "Endpoint groups must contain unique identities",
                    &mapping.id,
                ));
            }
            let cardinality_ok = match mapping.cardinality {
                Cardinality::OneToOne => mapping.sources.len() == 1 && mapping.targets.len() == 1,
                Cardinality::OneToMany => mapping.sources.len() == 1,
                Cardinality::ManyToOne => mapping.targets.len() == 1,
                Cardinality::ManyToMany => true,
            };
            if !cardinality_ok {
                issues.push(Issue::error(
                    "CARDINALITY_MISMATCH",
                    "Endpoint groups violate mapping cardinality",
                    &mapping.id,
                ));
            }
            let relation = result
                .relations
                .get(&mapping.relation)
                .map(|&(pi, ri)| &result.packs[pi].relations[ri]);
            if relation.is_none() {
                issues.push(Issue::error(
                    "UNKNOWN_RELATION",
                    "Relation was not supplied by a pack",
                    &mapping.id,
                ));
            }
            if relation
                .and_then(|r| r.cardinalities.as_ref())
                .is_some_and(|v| !v.contains(&mapping.cardinality))
            {
                issues.push(Issue::error(
                    "UNSUPPORTED_CARDINALITY",
                    "Cardinality is forbidden by the relation pack",
                    &mapping.id,
                ));
            }
            for (endpoints, kinds) in [
                (
                    &mapping.sources,
                    relation.and_then(|r| r.source_kinds.as_ref()),
                ),
                (
                    &mapping.targets,
                    relation.and_then(|r| r.target_kinds.as_ref()),
                ),
            ] {
                for id in endpoints {
                    crate::control::poll(control)?;
                    if !identifier(id) {
                        issues.push(Issue::error(
                            "INVALID_IDENTIFIER",
                            "Invalid endpoint identity",
                            &mapping.id,
                        ));
                    }
                    match result.entities.get(id) {
                        None => issues.push(Issue::error(
                            "UNRESOLVED_ENDPOINT",
                            format!("Missing endpoint {id}"),
                            &mapping.id,
                        )),
                        Some(&ei)
                            if kinds.is_some_and(|ks| !ks.contains(&doc.entities[ei].kind)) =>
                        {
                            issues.push(Issue::error(
                                "INVALID_ENDPOINT_KIND",
                                format!("Endpoint {id} has a disallowed kind"),
                                &mapping.id,
                            ))
                        }
                        _ => {}
                    }
                }
            }
            provenance(&mapping.provenance, &mapping.id, &mut issues);
            if let Some(transform) = &mapping.transform
                && (transform.adapter.is_empty()
                    || transform.version.is_empty()
                    || transform
                        .entrypoint
                        .as_ref()
                        .is_some_and(|s| !identifier(s)))
            {
                issues.push(Issue::error(
                    "INVALID_TRANSFORM",
                    "Invalid transform reference",
                    &mapping.id,
                ));
            }
            if mapping
                .invariants
                .as_ref()
                .is_some_and(|v| duplicates(v) || v.iter().any(String::is_empty))
            {
                issues.push(Issue::error(
                    "INVALID_INVARIANTS",
                    "Invariants must be unique nonempty strings",
                    &mapping.id,
                ));
            }
            for id in mapping
                .sources
                .iter()
                .chain(&mapping.targets)
                .collect::<BTreeSet<_>>()
            {
                result.incident.entry(id.clone()).or_default().push(index);
            }
            result.mappings.insert(mapping.id.clone(), index);
            result
                .by_relation
                .entry(mapping.relation.clone())
                .or_default()
                .push(index);
        }
        for (index, authority) in doc.authorities.iter().enumerate() {
            crate::control::poll(control)?;
            if !ids.insert(&authority.id) {
                issues.push(Issue::error(
                    "DUPLICATE_ID",
                    "Identity is declared more than once",
                    &authority.id,
                ));
            }
            if [&authority.id, &authority.concept, &authority.source]
                .iter()
                .any(|s| !identifier(s))
            {
                issues.push(Issue::error(
                    "INVALID_IDENTIFIER",
                    "Invalid authority identity/reference",
                    &authority.id,
                ));
            }
            if !result.entities.contains_key(&authority.concept) {
                issues.push(Issue::error(
                    "UNRESOLVED_CONCEPT",
                    "Authority concept does not exist",
                    &authority.id,
                ));
            }
            if !result.entities.contains_key(&authority.source) {
                issues.push(Issue::error(
                    "UNRESOLVED_AUTHORITY_SOURCE",
                    "Authority source does not exist",
                    &authority.id,
                ));
            }
            if authority.facts.is_empty() || authority.facts.iter().any(String::is_empty) {
                issues.push(Issue::error(
                    "EMPTY_ARRAY",
                    "Authority facts must be nonempty",
                    &authority.id,
                ));
            }
            if duplicates(&authority.facts) {
                issues.push(Issue::error(
                    "DUPLICATE_FACT",
                    "Authority facts must be unique",
                    &authority.id,
                ));
            }
            if (authority.mode == AuthorityMode::Delegated) != authority.delegated_from.is_some() {
                issues.push(Issue::error(
                    "INVALID_DELEGATION_PARENT",
                    "Only delegated authority must specify a parent",
                    &authority.id,
                ));
            }
            if let Some(parent) = &authority.delegated_from {
                result
                    .children
                    .entry(parent.clone())
                    .or_default()
                    .push(index);
            }
            result
                .by_concept
                .entry(authority.concept.clone())
                .or_default()
                .push(index);
            result.authorities.insert(authority.id.clone(), index);
            provenance(&authority.provenance, &authority.id, &mut issues);
            if authority.mode == AuthorityMode::Candidate {
                let mut issue = Issue::error(
                    "UNRESOLVED_AUTHORITY",
                    "Candidate ownership remains unresolved",
                    &authority.id,
                );
                issue.severity = Severity::Warning;
                issues.push(issue);
            }
        }
        for authority in &doc.authorities {
            crate::control::poll(control)?;
            if let Some(parent_id) = &authority.delegated_from {
                if let Some(&ai) = result.authorities.get(parent_id) {
                    let parent = &doc.authorities[ai];
                    if parent.mode == AuthorityMode::Candidate {
                        issues.push(Issue::error(
                            "INVALID_DELEGATION_PARENT",
                            "Delegation cannot descend from a candidate",
                            &authority.id,
                        ));
                    }
                    if parent.concept != authority.concept {
                        issues.push(Issue::error(
                            "DELEGATION_CONCEPT_MISMATCH",
                            "Delegation changes concept",
                            &authority.id,
                        ));
                    }
                    if !covers(&parent.facts, &authority.facts) {
                        issues.push(Issue::error(
                            "DELEGATION_FACT_WIDENING",
                            "Delegation widens fact scope",
                            &authority.id,
                        ));
                    }
                } else {
                    issues.push(Issue::error(
                        "UNRESOLVED_DELEGATION_PARENT",
                        "Delegation parent does not exist",
                        &authority.id,
                    ));
                }
            }
            let mut current = authority;
            let mut visited = HashSet::new();
            loop {
                if !visited.insert(current.id.as_str()) {
                    issues.push(Issue::error(
                        "DELEGATION_CYCLE",
                        "Cyclic delegation",
                        &authority.id,
                    ));
                    break;
                }
                let Some(parent) = current
                    .delegated_from
                    .as_ref()
                    .and_then(|s| result.authorities.get(s))
                else {
                    break;
                };
                current = &doc.authorities[*parent];
            }
        }
        for group in result.by_concept.values() {
            for (pos, &a) in group.iter().enumerate() {
                for &b in &group[pos + 1..] {
                    crate::control::poll(control)?;
                    let (a, b) = (&doc.authorities[a], &doc.authorities[b]);
                    if !overlap(&a.facts, &b.facts) {
                        continue;
                    }
                    if a.mode == AuthorityMode::Canonical && b.mode == AuthorityMode::Canonical {
                        issues.push(Issue::error(
                            "AUTHORITY_CONFLICT",
                            "Canonical fact scopes overlap",
                            &a.concept,
                        ));
                    }
                    if a.mode == AuthorityMode::Delegated
                        && b.mode == AuthorityMode::Delegated
                        && !result.ancestor(&a.id, b)
                        && !result.ancestor(&b.id, a)
                    {
                        issues.push(Issue::error(
                            "DELEGATION_BRANCH_CONFLICT",
                            "Independent delegation branches overlap",
                            &a.concept,
                        ));
                    }
                }
            }
        }
        // Bipartite entity -> mapping -> entity traversal preserves hyperedges
        // without expanding a many-to-many assertion into a quadratic edge set.
        for (relation, &(pi, ri)) in &result.relations {
            if result.packs[pi].relations[ri].cycle_policy == CyclePolicy::Forbid
                && result.has_cycle(relation, control)?
            {
                issues.push(Issue::error(
                    "FORBIDDEN_RELATION_CYCLE",
                    "Relation pack forbids this cycle",
                    relation,
                ));
            }
        }
        result.laws = crate::laws::validate(&result.packs)?;
        result.issues = finish(issues)?;
        let encoded = canonical_bytes(&result.document)?;
        result.document = parse(&encoded)?;
        result.digest = byte_digest(&encoded);
        Ok(result)
    }

    fn ancestor(&self, id: &str, authority: &Authority) -> bool {
        let mut current = authority;
        let mut visited = HashSet::new();
        while let Some(parent) = &current.delegated_from {
            if parent == id {
                return true;
            }
            if !visited.insert(parent.as_str()) {
                return false;
            }
            let Some(&index) = self.authorities.get(parent) else {
                return false;
            };
            current = &self.document.authorities[index];
        }
        false
    }

    fn has_cycle(
        &self,
        relation: &str,
        control: Option<&crate::WorkControl>,
    ) -> Result<bool, CheckError> {
        let mut adjacency: HashMap<&str, Vec<&str>> = HashMap::new();
        let mut indegree: HashMap<&str, usize> = HashMap::new();
        for &index in self.by_relation.get(relation).into_iter().flatten() {
            crate::control::poll(control)?;
            let m = &self.document.mappings[index];
            // IDs are globally unique, so mapping IDs can serve as factor nodes.
            indegree.entry(&m.id).or_default();
            for s in &m.sources {
                adjacency.entry(s).or_default().push(&m.id);
                *indegree.entry(&m.id).or_default() += 1;
                indegree.entry(s).or_default();
            }
            for t in &m.targets {
                adjacency.entry(&m.id).or_default().push(t);
                *indegree.entry(t).or_default() += 1;
            }
        }
        let mut queue: VecDeque<_> = indegree
            .iter()
            .filter_map(|(&id, &n)| (n == 0).then_some(id))
            .collect();
        let mut count = 0;
        while let Some(id) = queue.pop_front() {
            crate::control::poll(control)?;
            count += 1;
            for target in adjacency.get(id).into_iter().flatten() {
                let Some(n) = indegree.get_mut(target) else {
                    continue;
                };
                *n -= 1;
                if *n == 0 {
                    queue.push_back(target);
                }
            }
        }
        Ok(count != indegree.len())
    }

    pub fn document(&self) -> &GraphDocument {
        &self.document
    }
    pub fn packs(&self) -> &[RelationPack] {
        &self.packs
    }
    pub fn law(&self, id: &str) -> Option<(&RelationPack, &RelationLaw)> {
        self.laws.get(id).map(|&(pi, li)| {
            (
                &self.packs[pi],
                &self.packs[pi]
                    .laws
                    .as_ref()
                    .expect("checked executable pack")[li],
            )
        })
    }
    pub fn digest(&self) -> &str {
        &self.digest
    }
    pub fn issues(&self) -> &[Issue] {
        &self.issues
    }
    pub fn entity(&self, id: &str) -> Option<&Entity> {
        self.entities.get(id).map(|&i| &self.document.entities[i])
    }
    pub fn mapping(&self, id: &str) -> Option<&Mapping> {
        self.mappings.get(id).map(|&i| &self.document.mappings[i])
    }
    pub fn relation(&self, id: &str) -> Option<&Relation> {
        self.relations
            .get(id)
            .map(|&(pi, ri)| &self.packs[pi].relations[ri])
    }
    pub fn incident(&self, id: &str) -> impl Iterator<Item = &Mapping> {
        self.incident
            .get(id)
            .into_iter()
            .flatten()
            .map(|&i| &self.document.mappings[i])
    }
    pub fn known(&self, id: &str) -> bool {
        id == self.document.id
            || self.entities.contains_key(id)
            || self.mappings.contains_key(id)
            || self.authorities.contains_key(id)
    }

    pub fn resolve_authority(&self, concept: &str, fact: &str) -> AuthorityResolution {
        let applicable: Vec<_> = self
            .by_concept
            .get(concept)
            .into_iter()
            .flatten()
            .map(|&i| &self.document.authorities[i])
            .filter(|a| a.facts.iter().any(|f| f == "*" || f == fact))
            .collect();
        let candidates: Vec<_> = applicable
            .iter()
            .filter(|a| a.mode == AuthorityMode::Candidate)
            .map(|a| a.id.clone())
            .collect();
        let canonical: Vec<_> = applicable
            .iter()
            .filter(|a| a.mode == AuthorityMode::Canonical)
            .collect();
        if let [root] = canonical.as_slice() {
            let mut current = **root;
            let mut chain = vec![current.id.clone()];
            loop {
                let children: Vec<_> = self
                    .children
                    .get(&current.id)
                    .into_iter()
                    .flatten()
                    .map(|&i| &self.document.authorities[i])
                    .filter(|a| a.facts.iter().any(|f| f == "*" || f == fact))
                    .collect();
                let Some(child) = children.first() else {
                    break;
                };
                current = child;
                chain.push(current.id.clone());
            }
            AuthorityResolution::Resolved {
                canonical: root.id.clone(),
                effective: current.id.clone(),
                delegation_chain: chain,
                candidates,
            }
        } else if applicable.is_empty() {
            AuthorityResolution::Unresolved { candidates }
        } else {
            AuthorityResolution::Ambiguous {
                candidates: applicable.iter().map(|a| a.id.clone()).collect(),
            }
        }
    }

    pub fn trace(
        &self,
        start: &str,
        direction: Direction,
        max_depth: usize,
        relations: &[String],
    ) -> Result<Vec<TraceVisit>, CheckError> {
        if max_depth > 64 {
            return Err(CheckError(vec![Issue::error(
                "TRACE_DEPTH_LIMIT",
                "Maximum trace depth is 64",
                start,
            )]));
        }
        if self.entity(start).is_none() {
            return Ok(Vec::new());
        }
        let mut visited = HashSet::from([start.to_owned()]);
        let mut expanded = HashSet::new();
        let mut queue = VecDeque::from([(start.to_owned(), 0)]);
        let mut result = vec![TraceVisit {
            entity_id: start.to_owned(),
            depth: 0,
            via_mapping: None,
            predecessor: None,
        }];
        while let Some((id, depth)) = queue.pop_front() {
            if depth == max_depth {
                continue;
            }
            let mut neighbors = BTreeMap::new();
            for m in self
                .incident(&id)
                .filter(|m| relations.is_empty() || relations.contains(&m.relation))
            {
                let symmetric = self
                    .relation(&m.relation)
                    .is_some_and(|r| r.symmetric == Some(true));
                for (from, to, enabled, role) in [
                    (
                        &m.sources,
                        &m.targets,
                        direction != Direction::Incoming || symmetric,
                        false,
                    ),
                    (
                        &m.targets,
                        &m.sources,
                        direction != Direction::Outgoing || symmetric,
                        true,
                    ),
                ] {
                    if enabled && from.contains(&id) && expanded.insert((m.id.as_str(), role)) {
                        for target in to {
                            neighbors.insert((m.id.as_str(), target.as_str()), target);
                        }
                    }
                }
            }
            for ((mapping, _), target) in neighbors {
                if visited.insert(target.clone()) {
                    result.push(TraceVisit {
                        entity_id: target.clone(),
                        depth: depth + 1,
                        via_mapping: Some(mapping.to_owned()),
                        predecessor: Some(id.clone()),
                    });
                    queue.push_back((target.clone(), depth + 1));
                }
            }
        }
        Ok(result)
    }
}

#[derive(Debug, Serialize)]
#[serde(tag = "status", rename_all = "lowercase")]
pub enum AuthorityResolution {
    Resolved {
        canonical: String,
        effective: String,
        #[serde(rename = "delegationChain")]
        delegation_chain: Vec<String>,
        candidates: Vec<String>,
    },
    Ambiguous {
        candidates: Vec<String>,
    },
    Unresolved {
        candidates: Vec<String>,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Direction {
    Incoming,
    Outgoing,
    Both,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TraceVisit {
    pub entity_id: String,
    pub depth: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub via_mapping: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub predecessor: Option<String>,
}

pub fn compose(
    documents: &[GraphDocument],
    id: String,
    namespace: String,
) -> Result<GraphDocument, CheckError> {
    if documents.is_empty() {
        return Err(CheckError(vec![Issue::error(
            "EMPTY_SHARDS",
            "At least one shard is required",
            &id,
        )]));
    }
    let mut entities = BTreeMap::new();
    let mut mappings = BTreeMap::new();
    let mut authorities = BTreeMap::new();
    let mut packs = BTreeMap::new();
    let mut source_ids = BTreeSet::new();
    fn insert<T: Clone + PartialEq>(
        map: &mut BTreeMap<String, T>,
        id: &str,
        value: &T,
    ) -> Result<(), CheckError> {
        if map.get(id).is_some_and(|v| v != value) {
            return Err(CheckError(vec![Issue::error(
                "CONFLICTING_SHARD_DEFINITION",
                "Shards disagree on a stable identity",
                id,
            )]));
        }
        map.entry(id.to_owned()).or_insert_with(|| value.clone());
        Ok(())
    }
    for doc in documents {
        if !source_ids.insert(&doc.id) {
            return Err(CheckError(vec![Issue::error(
                "DUPLICATE_SHARD_ID",
                "Shard identity appears more than once",
                &doc.id,
            )]));
        }
        for v in &doc.entities {
            insert(&mut entities, &v.id, v)?;
        }
        for v in &doc.mappings {
            insert(&mut mappings, &v.id, v)?;
        }
        for v in &doc.authorities {
            insert(&mut authorities, &v.id, v)?;
        }
        for v in doc.relation_packs.iter().flatten() {
            insert(&mut packs, &v.id, v)?;
        }
    }
    Ok(GraphDocument {
        schema: None,
        schema_version: ProtocolVersion::Draft1,
        document_type: GraphType::Graph,
        id,
        namespace,
        label: None,
        revision: None,
        relation_packs: Some(packs.into_values().collect()),
        entities: entities.into_values().collect(),
        mappings: mappings.into_values().collect(),
        authorities: authorities.into_values().collect(),
        metadata: Some(BTreeMap::from([(
            "composedFrom".into(),
            serde_json::json!(documents.iter().map(|d| &d.id).collect::<Vec<_>>()),
        )])),
        extensions: None,
    })
}
