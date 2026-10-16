//! Original v1 projection observations. These records never admit a generation.
use crate::legacy_viability::{
    ObservationIssue, core_registry, items, project, response, s, strings, validate_generation,
};
use crate::legacy_workspace::{error, get, locale, obj, observed, scalar};
use crate::{
    LegacyGraphRegistry, LegacyPortableSchema, LegacyWorkspaceError, validate_legacy_document,
};
use patamaps_contracts::{LegacyOrderedJson as J, LegacyReadOnlyJson as Data, byte_digest};
use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

fn limit() -> LegacyWorkspaceError {
    let mut e = error(
        "Error",
        "Original v1 projection exceeds native compatibility resource bounds",
    );
    e.code = "LEGACY_PROJECTION_RESOURCE_LIMIT".into();
    e
}
#[derive(Default)]
struct Budget {
    bytes: usize,
    values: usize,
    steps: usize,
}
impl Budget {
    fn charge(&mut self, bytes: usize, values: usize) -> Result<(), LegacyWorkspaceError> {
        self.bytes = self.bytes.checked_add(bytes).ok_or_else(limit)?;
        self.values = self.values.checked_add(values).ok_or_else(limit)?;
        if self.bytes > patamaps_contracts::COMPATIBILITY_JSON_LIMITS.max_bytes
            || self.values > patamaps_contracts::COMPATIBILITY_JSON_LIMITS.max_values
        {
            return Err(limit());
        }
        Ok(())
    }
    fn step(&mut self, n: usize) -> Result<(), LegacyWorkspaceError> {
        self.steps = self.steps.checked_add(n).ok_or_else(limit)?;
        if self.steps > patamaps_contracts::COMPATIBILITY_JSON_LIMITS.max_values {
            return Err(limit());
        }
        Ok(())
    }
    fn value(&mut self, v: &J) -> Result<(), LegacyWorkspaceError> {
        let mut values = 0;
        let mut stack = vec![(v, 1usize)];
        while let Some((v, depth)) = stack.pop() {
            if depth > patamaps_contracts::COMPATIBILITY_JSON_LIMITS.max_depth {
                return Err(limit());
            }
            values += 1;
            match v {
                J::Object(p) => {
                    values += p.len();
                    stack.extend(p.iter().map(|(_, v)| (v, depth + 1)));
                }
                J::Array(a) => stack.extend(a.iter().map(|v| (v, depth + 1))),
                _ => {}
            }
        }
        let bytes = Data::json_raw(v)
            .map_err(|e| error("Error", &e.to_string()))?
            .get()
            .len();
        self.charge(bytes, values)
    }
}
fn bounded_facts(
    value: &mut J,
    path: &mut Vec<String>,
    facts: &mut Vec<J>,
    budget: &mut Budget,
) -> Result<(), LegacyWorkspaceError> {
    match value {
        J::Number(n) if !n.is_finite() || (*n == 0.0 && n.is_sign_negative()) => {
            crate::legacy_viability::numeric_facts(value, path, facts);
            budget.value(facts.last().expect("numeric fact"))?;
        }
        J::Object(pairs) => {
            for (key, v) in pairs {
                path.push(key.clone());
                bounded_facts(v, path, facts, budget)?;
                path.pop();
            }
        }
        J::Array(values) => {
            for (i, v) in values.iter_mut().enumerate() {
                path.push(i.to_string());
                bounded_facts(v, path, facts, budget)?;
                path.pop();
            }
        }
        _ => {}
    }
    Ok(())
}

fn issue(code: &str, message: String, options: Vec<(&str, J)>) -> ObservationIssue {
    let mut keys = vec!["severity".into(), "code".into(), "message".into()];
    let mut fields = vec![
        ("severity", scalar("error")),
        ("code", scalar(code)),
        ("message", J::String(message)),
    ];
    for (key, value) in options {
        keys.push(key.into());
        fields.push((key, value));
    }
    ObservationIssue {
        value: obj(fields),
        keys,
    }
}
fn digest(v: &J, name: &str) -> Result<String, LegacyWorkspaceError> {
    Data::stable_bytes(v, &locale(name)?)
        .map(|b| byte_digest(&b))
        .map_err(|e| error("Error", &e.to_string()))
}
fn schema(record: bool) -> &'static LegacyPortableSchema {
    static SPEC: OnceLock<LegacyPortableSchema> = OnceLock::new();
    static RECORD: OnceLock<LegacyPortableSchema> = OnceLock::new();
    if record {
        RECORD.get_or_init(|| {
            LegacyPortableSchema::new(include_str!(
                "../../../fixtures/reference/schemas/metamap-projection.schema.json"
            ))
        })
    } else {
        SPEC.get_or_init(|| {
            LegacyPortableSchema::new(include_str!(
                "../../../fixtures/reference/schemas/metamap-projection-spec.schema.json"
            ))
        })
    }
}
fn validate(
    v: &J,
    record: bool,
    name: &str,
    holes: &HashSet<usize>,
) -> Result<Vec<ObservationIssue>, LegacyWorkspaceError> {
    let mut issues = schema(record)
        .legacy_issues(v, holes)
        .into_iter()
        .map(|e| {
            issue(
                if record {
                    "INVALID_PROJECTION"
                } else {
                    "INVALID_PROJECTION_SPEC"
                },
                e.message,
                vec![(
                    "path",
                    scalar(if e.path.is_empty() { "$" } else { &e.path }),
                )],
            )
        })
        .collect::<Vec<_>>();
    if !issues.is_empty() {
        return Ok(issues);
    }
    if record {
        let J::Object(pairs) = v else { unreachable!() };
        let content = J::Object(
            pairs
                .iter()
                .filter(|(k, _)| !["$schema", "id", "digest"].contains(&k.as_str()))
                .cloned()
                .collect(),
        );
        let expected = digest(&content, name)?;
        let id = format!(
            "urn:metamap:projection:{}",
            expected.trim_start_matches("sha256:")
        );
        if s(v, "digest") != expected {
            issues.push(issue(
                "PROJECTION_DIGEST_MISMATCH",
                format!(
                    "Projection digest {} does not match {expected}",
                    s(v, "digest")
                ),
                vec![("subjectId", get(v, "id")?.clone())],
            ));
        }
        if s(v, "id") != id {
            issues.push(issue(
                "PROJECTION_ID_MISMATCH",
                format!(
                    "Projection id {} does not match its content address",
                    s(v, "id")
                ),
                vec![("subjectId", get(v, "id")?.clone())],
            ));
        }
    } else {
        if !crate::legacy_references::reference(&Data::string_units(s(v, "id"))) {
            issues.push(issue(
                "INVALID_PROJECTION_SPEC_ID",
                format!("{} is not URI-like", s(v, "id")),
                vec![("path", scalar("$.id"))],
            ));
        }
        let mut names = HashSet::new();
        for (i, slot) in items(v, "slots").iter().enumerate() {
            let slot_name = s(slot, "name");
            if !names.insert(slot_name) {
                issues.push(issue(
                    "DUPLICATE_PROJECTION_SLOT",
                    format!("Projection slot {slot_name} is declared more than once"),
                    vec![
                        ("slot", get(slot, "name")?.clone()),
                        ("path", scalar(&format!("$.slots[{i}].name"))),
                    ],
                ));
            }
            if !crate::legacy_references::relation(&Data::string_units(s(slot, "relation"))) {
                issues.push(issue(
                    "INVALID_PROJECTION_RELATION",
                    format!("{} is not a relation identifier", s(slot, "relation")),
                    vec![
                        ("slot", get(slot, "name")?.clone()),
                        ("path", scalar(&format!("$.slots[{i}].relation"))),
                    ],
                ));
            }
        }
    }
    Ok(issues)
}
fn entity(v: &J) -> J {
    let J::Object(pairs) = v else { unreachable!() };
    J::Object(
        ["id", "kind", "label", "schema", "locators", "attributes"]
            .into_iter()
            .filter_map(|key| pairs.iter().find(|(k, _)| k == key).cloned())
            .collect(),
    )
}
fn result(issues: Vec<ObservationIssue>, projection: Option<J>) -> Result<J, LegacyWorkspaceError> {
    let mut fields = vec![
        (
            "status",
            scalar(if projection.is_some() {
                "projected"
            } else {
                "rejected"
            }),
        ),
        (
            "issues",
            J::Array(issues.iter().map(|v| v.value.clone()).collect()),
        ),
    ];
    if let Some(p) = projection {
        fields.push(("projection", p));
    }
    let mut value = obj(fields);
    let mut facts = vec![];
    let mut budget = Budget::default();
    budget.value(&value)?;
    bounded_facts(&mut value, &mut vec![], &mut facts, &mut budget)?;
    let J::Object(mut envelope) = response(value, issues) else {
        unreachable!()
    };
    envelope.push(("numbers".into(), J::Array(facts)));
    Ok(J::Object(envelope))
}
fn mapped_issue(v: J) -> ObservationIssue {
    let mut fields = vec![];
    for key in ["severity", "code", "message", "subjectId", "path"] {
        if let Some(value) = v.get(key) {
            fields.push((key, value.clone()));
        }
    }
    ObservationIssue {
        value: obj(fields),
        keys: ["severity", "code", "message", "subjectId", "path"]
            .map(str::to_owned)
            .to_vec(),
    }
}
fn compile(input: &J, name: &str, holes: &HashSet<usize>) -> Result<J, LegacyWorkspaceError> {
    let document = get(input, "document")?;
    let generation = get(input, "generation")?;
    let spec = get(input, "spec")?;
    if s(generation, "schemaVersion") != "1.0.0" || s(spec, "schemaVersion") != "1.0.0" {
        return result(
            vec![issue(
                "PROJECTION_VERSION_MISMATCH",
                "Generation and projection specification must use the same supported profile"
                    .into(),
                vec![],
            )],
            None,
        );
    }
    if matches!(input.get("semanticPolicyPresent"), Some(J::Bool(true)))
        || input
            .get("executablePackCount")
            .is_some_and(|v| matches!(v,J::Number(n) if *n>0.0))
        || items(document, "mappings").iter().any(|m| {
            m.get("attributes")
                .and_then(|a| a.get("metamap:derivation"))
                .is_some()
        })
    {
        return result(vec![issue("EXECUTABLE_PROJECTION_REQUIRED","Typed policy inputs, executable packs and proof claims require the version 2 projection profile".into(),vec![])],None);
    }
    let registry = input
        .get("registry")
        .map(project)
        .transpose()?
        .unwrap_or_else(core_registry);
    let graph_registry: LegacyGraphRegistry =
        serde_json::from_value(registry.clone()).map_err(|e| error("TypeError", &e.to_string()))?;
    let graph_validation = validate_legacy_document(&project(document)?, &graph_registry);
    let mut issues = validate(spec, false, name, holes)?;
    issues.extend(
        validate_generation(generation, name, holes)?
            .into_iter()
            .map(|v| mapped_issue(v.value)),
    );
    issues.extend(
        graph_validation
            .issues
            .into_iter()
            .filter(|v| v.severity == crate::Severity::Error)
            .map(|v| mapped_issue(observed(v))),
    );
    if !issues.is_empty() {
        return result(issues, None);
    }
    let graph_digest = digest(document, name)?;
    let binding = get(generation, "graph")?;
    if s(binding, "id") != s(document, "id") {
        issues.push(issue(
            "PROJECTION_GRAPH_ID_MISMATCH",
            format!(
                "Generation is bound to {}, not {}",
                s(binding, "id"),
                s(document, "id")
            ),
            vec![("subjectId", get(generation, "id")?.clone())],
        ));
    }
    if s(binding, "digest") != graph_digest {
        issues.push(issue(
            "STALE_PROJECTION_GENERATION",
            format!(
                "Generation graph digest does not match {}",
                s(document, "id")
            ),
            vec![("subjectId", get(generation, "id")?.clone())],
        ));
    }
    for slot in items(spec, "slots") {
        if !registry["definitions"].as_array().is_some_and(|defs| {
            defs.iter()
                .any(|d| d["key"].as_str() == Some(s(slot, "relation")))
        }) {
            issues.push(issue(
                "UNKNOWN_PROJECTION_RELATION",
                format!(
                    "Projection slot {} uses unregistered relation {}",
                    s(slot, "name"),
                    s(slot, "relation")
                ),
                vec![("slot", get(slot, "name")?.clone())],
            ));
        }
    }
    let entities = items(document, "entities")
        .iter()
        .map(|v| (s(v, "id"), v))
        .collect::<HashMap<_, _>>();
    let active = strings(generation, "activeMappings")
        .into_iter()
        .collect::<HashSet<_>>();
    let mapping_ids = items(document, "mappings")
        .iter()
        .map(|m| s(m, "id"))
        .collect::<HashSet<_>>();
    for id in strings(generation, "activeMappings") {
        if !mapping_ids.contains(id.as_str()) {
            issues.push(issue(
                "UNKNOWN_ACTIVE_MAPPING",
                format!("Generation activates mapping {id}, which is absent from the graph"),
                vec![("subjectId", J::String(id))],
            ));
        }
    }
    let collator = locale(name)?;
    let cmp = |a: &str, b: &str| {
        collator.compare_legacy_utf16(&Data::string_units(a), &Data::string_units(b))
    };
    let mut mappings = items(document, "mappings")
        .iter()
        .filter(|m| active.contains(s(m, "id")))
        .collect::<Vec<_>>();
    mappings.sort_by(|a, b| cmp(s(a, "id"), s(b, "id")));
    // Index only active mappings once; duplicate endpoints preserve original incidence.
    let mut outgoing: HashMap<(&str, &str), Vec<&J>> = HashMap::new();
    let mut incoming: HashMap<(&str, &str), Vec<&J>> = HashMap::new();
    for mapping in mappings {
        for id in items(mapping, "sources").iter().filter_map(J::string) {
            outgoing
                .entry((id, s(mapping, "relation")))
                .or_default()
                .push(mapping);
        }
        for id in items(mapping, "targets").iter().filter_map(J::string) {
            incoming
                .entry((id, s(mapping, "relation")))
                .or_default()
                .push(mapping);
        }
    }
    let select = get(spec, "select")?;
    let ids = select
        .get("ids")
        .map(|_| strings(select, "ids").into_iter().collect::<HashSet<_>>());
    let kinds = select
        .get("kinds")
        .map(|_| strings(select, "kinds").into_iter().collect::<HashSet<_>>());
    for id in strings(select, "ids") {
        if !entities.contains_key(id.as_str()) {
            issues.push(issue(
                "UNKNOWN_PROJECTION_SUBJECT",
                format!("Projection selects missing entity {id}"),
                vec![("subjectId", J::String(id))],
            ));
        }
    }
    let mut subjects = items(document, "entities")
        .iter()
        .filter(|e| {
            ids.as_ref().is_none_or(|ids| ids.contains(s(e, "id")))
                && kinds
                    .as_ref()
                    .is_none_or(|kinds| kinds.contains(s(e, "kind")))
        })
        .collect::<Vec<_>>();
    subjects.sort_by(|a, b| cmp(s(a, "id"), s(b, "id")));
    if subjects.is_empty() {
        issues.push(issue(
            "EMPTY_PROJECTION",
            format!("Projection {} selected no graph entities", s(spec, "id")),
            vec![("subjectId", get(spec, "id")?.clone())],
        ));
    }
    let mut budget = Budget::default();
    budget.charge(1024, 64)?;
    for id in [
        get(document, "id")?,
        get(generation, "id")?,
        get(spec, "id")?,
    ] {
        budget.value(id)?;
    }
    budget.step(
        subjects
            .len()
            .checked_mul(items(spec, "slots").len())
            .ok_or_else(limit)?,
    )?;
    let mut entity_costs = HashMap::new();
    for v in entities.values() {
        let mut cost = Budget::default();
        cost.value(&entity(v))?;
        entity_costs.insert(s(v, "id"), (cost.bytes, cost.values));
    }
    let mut entries = vec![];
    for subject in subjects {
        budget.charge(64, 8)?;
        let cost = entity_costs[s(subject, "id")];
        budget.charge(cost.0, cost.1)?;
        let mut slots = vec![];
        for slot in items(spec, "slots") {
            budget.charge(128, 32)?;
            for field in ["name", "relation", "direction", "cardinality"] {
                budget.value(get(slot, field)?)?;
            }
            let index = if s(slot, "direction") == "outgoing" {
                &outgoing
            } else {
                &incoming
            };
            let matching = index
                .get(&(s(subject, "id"), s(slot, "relation")))
                .map(Vec::as_slice)
                .unwrap_or(&[]);
            let mut targets = HashSet::new();
            let options = || {
                vec![
                    (
                        "subjectId",
                        get(subject, "id").expect("validated subject").clone(),
                    ),
                    ("slot", get(slot, "name").expect("validated slot").clone()),
                ]
            };
            for mapping in matching {
                budget.step(1)?;
                budget.value(get(mapping, "id")?)?;
                if s(mapping, "lossiness") == "lossy"
                    && !matches!(slot.get("allowLossy"), Some(J::Bool(true)))
                {
                    issues.push(issue(
                        "LOSSY_PROJECTION_LINK",
                        format!(
                            "{} is lossy but slot {} does not allow lossy linkage",
                            s(mapping, "id"),
                            s(slot, "name")
                        ),
                        options(),
                    ));
                }
                for id in items(
                    mapping,
                    if s(slot, "direction") == "outgoing" {
                        "targets"
                    } else {
                        "sources"
                    },
                )
                .iter()
                .filter_map(J::string)
                {
                    budget.step(1)?;
                    targets.insert(id);
                }
            }
            let allowed = slot.get("targetKinds").map(|_| {
                strings(slot, "targetKinds")
                    .into_iter()
                    .collect::<HashSet<_>>()
            });
            let unfiltered = targets
                .into_iter()
                .filter_map(|id| entities.get(id).copied())
                .collect::<Vec<_>>();
            let mut selected = unfiltered
                .iter()
                .copied()
                .filter(|v| allowed.as_ref().is_none_or(|a| a.contains(s(v, "kind"))))
                .collect::<Vec<_>>();
            selected.sort_by(|a, b| cmp(s(a, "id"), s(b, "id")));
            for v in &selected {
                let cost = entity_costs[s(v, "id")];
                budget.charge(cost.0, cost.1)?;
            }
            if selected.len() != unfiltered.len() {
                let mut rejected = unfiltered
                    .iter()
                    .filter(|v| {
                        !allowed
                            .as_ref()
                            .expect("kind filter")
                            .contains(s(v, "kind"))
                    })
                    .map(|v| s(v, "kind"))
                    .collect::<Vec<_>>();
                rejected.sort_by_key(|v| Data::string_units(v));
                rejected.dedup();
                issues.push(issue(
                    "PROJECTION_TARGET_KIND_MISMATCH",
                    format!(
                        "{} slot {} resolved disallowed target kind(s): {}",
                        s(subject, "id"),
                        s(slot, "name"),
                        rejected.join(", ")
                    ),
                    options(),
                ));
            }
            let count = selected.len();
            let cardinality = s(slot, "cardinality");
            let missing = count == 0 && ["exactly-one", "one-or-more"].contains(&cardinality);
            let ambiguous = count > 1 && ["exactly-one", "zero-or-one"].contains(&cardinality);
            if missing {
                issues.push(issue(
                    "REQUIRED_PROJECTION_TARGET_MISSING",
                    format!(
                        "{} slot {} requires {cardinality}, resolved {count}",
                        s(subject, "id"),
                        s(slot, "name")
                    ),
                    options(),
                ));
            }
            if ambiguous {
                issues.push(issue(
                    "AMBIGUOUS_PROJECTION_TARGET",
                    format!(
                        "{} slot {} requires {cardinality}, resolved {count}: {}",
                        s(subject, "id"),
                        s(slot, "name"),
                        selected
                            .iter()
                            .map(|v| s(v, "id"))
                            .collect::<Vec<_>>()
                            .join(", ")
                    ),
                    options(),
                ));
            }
            slots.push(obj(vec![
                ("name", get(slot, "name")?.clone()),
                ("relation", get(slot, "relation")?.clone()),
                ("direction", get(slot, "direction")?.clone()),
                ("cardinality", get(slot, "cardinality")?.clone()),
                (
                    "mappings",
                    J::Array(
                        matching
                            .iter()
                            .map(|m| get(m, "id").expect("validated mapping").clone())
                            .collect(),
                    ),
                ),
                (
                    "targets",
                    J::Array(selected.into_iter().map(entity).collect()),
                ),
            ]));
        }
        slots.sort_by(|a, b| cmp(s(a, "name"), s(b, "name")));
        entries.push(obj(vec![
            ("subject", entity(subject)),
            ("slots", J::Array(slots)),
        ]));
    }
    if !issues.is_empty() {
        return result(issues, None);
    }
    let binding = |v: &J| -> Result<J, LegacyWorkspaceError> {
        Ok(obj(vec![
            ("id", get(v, "id")?.clone()),
            ("digest", get(v, "digest")?.clone()),
        ]))
    };
    let content = obj(vec![
        ("schemaVersion", scalar("1.0.0")),
        ("generation", binding(generation)?),
        (
            "graph",
            obj(vec![
                ("id", get(document, "id")?.clone()),
                ("digest", scalar(&graph_digest)),
            ]),
        ),
        (
            "spec",
            obj(vec![
                ("id", get(spec, "id")?.clone()),
                ("digest", scalar(&digest(spec, name)?)),
            ]),
        ),
        ("entries", J::Array(entries)),
    ]);
    let address = digest(&content, name)?;
    let J::Object(mut fields) = content else {
        unreachable!()
    };
    fields.insert(0,("$schema".into(),scalar("https://raw.githubusercontent.com/roryscot/metamap/v0.4.0/schemas/metamap-projection.schema.json")));
    fields.push((
        "id".into(),
        scalar(&format!(
            "urn:metamap:projection:{}",
            address.trim_start_matches("sha256:")
        )),
    ));
    fields.push(("digest".into(), scalar(&address)));
    result(vec![], Some(J::Object(fields)))
}
pub(crate) fn request(
    operation: &str,
    input: &J,
    name: &str,
    holes: &HashSet<usize>,
) -> Result<J, LegacyWorkspaceError> {
    if operation == "projection-compile" {
        return compile(input, name, holes);
    }
    let value = get(input, "value")?;
    let record = matches!(operation, "projection-validate" | "projection-parse");
    if ![
        "projection-spec-validate",
        "projection-spec-parse",
        "projection-validate",
        "projection-parse",
    ]
    .contains(&operation)
    {
        return Err(error("TypeError", "Unknown legacy projection operation"));
    }
    let issues = validate(value, record, name, holes)?;
    if operation.ends_with("-parse") {
        if !issues.is_empty() {
            let message = issues
                .iter()
                .map(|i| {
                    format!(
                        "{} {}",
                        i.value.get("path").and_then(J::string).unwrap_or("$"),
                        s(&i.value, "message")
                    )
                })
                .collect::<Vec<_>>()
                .join("; ");
            return Err(error(
                "Error",
                &format!(
                    "Invalid Metamap {}: {message}",
                    if record {
                        "projection"
                    } else {
                        "projection specification"
                    }
                ),
            ));
        }
        return Ok(response(value.clone(), vec![]));
    }
    let result = obj(vec![
        ("valid", J::Bool(issues.is_empty())),
        (
            "issues",
            J::Array(issues.iter().map(|i| i.value.clone()).collect()),
        ),
    ]);
    Ok(response(result, issues))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn projected_output_depth_is_bounded_before_serialization() {
        let mut value = J::Null;
        for _ in 0..patamaps_contracts::COMPATIBILITY_JSON_LIMITS.max_depth {
            value = J::Array(vec![value]);
        }
        let error = Budget::default().value(&value).unwrap_err();
        assert_eq!(error.code.as_ref(), "LEGACY_PROJECTION_RESOURCE_LIMIT");
    }
}
