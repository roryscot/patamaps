//! Original v1 compilation observations. These portable records are not native
//! admitted generations and cannot authorize protected activation.
use crate::legacy_evaluation::{impact, selector};
use crate::legacy_workspace::{
    error, get, locale, native, obj, observed, parse, raw, scalar, text,
};
use crate::{
    LegacyGraphRegistry, LegacyPortableSchema, LegacyWorkspaceError, LegacyWorkspaceRequest,
    validate_legacy_document,
};
use patamaps_contracts::{LegacyOrderedJson as J, LegacyReadOnlyJson as Data, byte_digest};
use serde_json::{Value, json, value::RawValue};
use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

pub(crate) struct ObservationIssue {
    pub value: J,
    pub keys: Vec<String>,
}
impl ObservationIssue {
    pub fn new(code: &str, message: &str, subject: Option<&str>, path: Option<&str>) -> Self {
        let mut pairs = vec![
            ("severity", scalar("error")),
            ("code", scalar(code)),
            ("message", scalar(message)),
        ];
        if let Some(id) = subject {
            pairs.push(("subjectId", J::String(id.into())));
        }
        if let Some(path) = path {
            pairs.push(("path", scalar(path)));
        }
        Self {
            value: obj(pairs),
            keys: ["severity", "code", "message", "subjectId", "path"]
                .map(str::to_owned)
                .to_vec(),
        }
    }
    pub fn constraint(code: &str, message: &str, subject: &str) -> Self {
        let mut v = Self::new(code, message, Some(subject), None);
        v.keys.pop();
        v
    }
    fn set(&mut self, key: &'static str, value: J) {
        let J::Object(pairs) = &mut self.value else {
            unreachable!()
        };
        if let Some((_, slot)) = pairs.iter_mut().find(|(k, _)| k == key) {
            *slot = value;
        } else {
            pairs.push((key.into(), value));
        }
        if !self.keys.iter().any(|name| name == key) {
            self.keys.push(key.to_owned());
        }
    }
}
pub(crate) fn items<'a>(v: &'a J, key: &str) -> &'a [J] {
    v.get(key).and_then(J::array).unwrap_or(&[])
}
pub(crate) fn s<'a>(v: &'a J, key: &str) -> &'a str {
    v.get(key).and_then(J::string).unwrap_or("")
}
pub(crate) fn strings(v: &J, key: &str) -> Vec<String> {
    items(v, key)
        .iter()
        .filter_map(J::string)
        .map(str::to_owned)
        .collect()
}
pub(crate) fn project(v: &J) -> Result<Value, LegacyWorkspaceError> {
    Data::projected_value(v).map_err(|e| error("Error", &e.to_string()))
}
fn digest(v: &J, locale_name: &str) -> Result<String, LegacyWorkspaceError> {
    Data::stable_bytes(v, &locale(locale_name)?)
        .map(|b| byte_digest(&b))
        .map_err(|e| error("Error", &e.to_string()))
}
fn schema(generation: bool) -> &'static LegacyPortableSchema {
    static POLICY: OnceLock<LegacyPortableSchema> = OnceLock::new();
    static GENERATION: OnceLock<LegacyPortableSchema> = OnceLock::new();
    if generation {
        GENERATION.get_or_init(|| {
            LegacyPortableSchema::new(include_str!(
                "../../../fixtures/reference/schemas/metamap-generation.schema.json"
            ))
        })
    } else {
        POLICY.get_or_init(|| {
            LegacyPortableSchema::new(include_str!(
                "../../../fixtures/reference/schemas/metamap-viability.schema.json"
            ))
        })
    }
}
fn shape(
    v: &J,
    generation: bool,
    holes: &HashSet<usize>,
) -> Result<Vec<ObservationIssue>, LegacyWorkspaceError> {
    Ok(schema(generation)
        .legacy_issues(v, holes)
        .into_iter()
        .map(|e| ObservationIssue {
            value: obj(vec![
                ("severity", scalar("error")),
                (
                    "code",
                    scalar(if generation {
                        "INVALID_VIABLE_GENERATION"
                    } else {
                        "INVALID_VIABILITY_POLICY"
                    }),
                ),
                ("message", scalar(&e.message)),
                (
                    "path",
                    scalar(if e.path.is_empty() { "$" } else { &e.path }),
                ),
            ]),
            keys: ["severity", "code", "message", "path"]
                .map(str::to_owned)
                .to_vec(),
        })
        .collect())
}
fn validate_policy(
    v: &J,
    holes: &HashSet<usize>,
) -> Result<Vec<ObservationIssue>, LegacyWorkspaceError> {
    let mut issues = shape(v, false, holes)?;
    if !issues.is_empty() {
        return Ok(issues);
    }
    let mut ids = HashMap::new();
    let mut register = |id: &str, path: String| {
        if let Some(previous) = ids.get(id) {
            issues.push(ObservationIssue::new(
                "DUPLICATE_POLICY_ID",
                &format!("{id} is already declared at {previous}"),
                Some(id),
                Some(&path),
            ));
        } else {
            ids.insert(id.to_owned(), path);
        }
    };
    register(s(v, "id"), "$.id".into());
    for field in ["constraints", "evidence", "waivers"] {
        for (index, entry) in items(v, field).iter().enumerate() {
            register(s(entry, "id"), format!("$.{field}[{index}].id"));
        }
    }
    Ok(issues)
}
pub(crate) fn validate_generation(
    v: &J,
    locale_name: &str,
    holes: &HashSet<usize>,
) -> Result<Vec<ObservationIssue>, LegacyWorkspaceError> {
    let mut issues = shape(v, true, holes)?;
    if !issues.is_empty() {
        return Ok(issues);
    }
    let J::Object(pairs) = v else { unreachable!() };
    let content = J::Object(
        pairs
            .iter()
            .filter(|(k, _)| !["$schema", "id", "digest"].contains(&k.as_str()))
            .cloned()
            .collect(),
    );
    let expected = digest(&content, locale_name)?;
    let expected_id = format!(
        "urn:metamap:generation:{}",
        expected.trim_start_matches("sha256:")
    );
    if s(v, "digest") != expected {
        issues.push(ObservationIssue::new(
            "GENERATION_DIGEST_MISMATCH",
            &format!(
                "Generation digest {} does not match {expected}",
                s(v, "digest")
            ),
            Some(s(v, "id")),
            None,
        ));
    }
    if s(v, "id") != expected_id {
        issues.push(ObservationIssue::new(
            "GENERATION_ID_MISMATCH",
            &format!(
                "Generation id {} does not match its content address",
                s(v, "id")
            ),
            Some(s(v, "id")),
            None,
        ));
    }
    Ok(issues)
}
pub(crate) fn response(value: J, issues: Vec<ObservationIssue>) -> J {
    let path_indexes = issues
        .iter()
        .map(|issue| {
            let subject = s(&issue.value, "subjectId");
            issue.value.get("causalPath")?;
            value.get("impact").and_then(|impact| {
                items(impact, "paths")
                    .iter()
                    .position(|path| s(path, "subjectId") == subject)
            })
        })
        .collect::<Vec<_>>();
    obj(vec![
        ("value", value),
        (
            "issueKeys",
            native(issues.iter().map(|i| &i.keys).collect::<Vec<_>>()),
        ),
        ("issuePathIndexes", native(path_indexes)),
    ])
}
fn validation_response(issues: Vec<ObservationIssue>) -> J {
    let value = obj(vec![
        ("valid", J::Bool(issues.is_empty())),
        (
            "issues",
            J::Array(issues.iter().map(|i| i.value.clone()).collect()),
        ),
    ]);
    response(value, issues)
}

/// ECMAScript's ISO Date.parse domain normalizes day 29..31 beyond a month's
/// end and truncates submillisecond digits. The original timestamp gate adds
/// its own full-date-time syntax before checking this finite result.
pub(crate) fn timestamp(value: &str) -> Option<i128> {
    let b = value.as_bytes();
    if b.len() < 20
        || b.get(4) != Some(&b'-')
        || b.get(7) != Some(&b'-')
        || b.get(10) != Some(&b'T')
        || b.get(13) != Some(&b':')
        || b.get(16) != Some(&b':')
    {
        return None;
    }
    let number = |a: usize, z: usize| -> Option<u32> {
        let part = b.get(a..z)?;
        if !part.iter().all(u8::is_ascii_digit) {
            return None;
        }
        value.get(a..z)?.parse().ok()
    };
    let year = number(0, 4)?;
    let month = number(5, 7)?;
    let day = number(8, 10)?;
    let hour = number(11, 13)?;
    let minute = number(14, 16)?;
    let second = number(17, 19)?;
    if !(1..=12).contains(&month)
        || !(1..=31).contains(&day)
        || hour > 24
        || minute > 59
        || second > 59
    {
        return None;
    }
    let mut at = 19;
    let mut ms = 0;
    let mut fraction_nonzero = false;
    if b.get(at) == Some(&b'.') {
        at += 1;
        let start = at;
        while b.get(at).is_some_and(u8::is_ascii_digit) {
            at += 1;
        }
        if at == start {
            return None;
        }
        fraction_nonzero = b[start..at].iter().any(|&b| b != b'0');
        for i in 0..3 {
            ms *= 10;
            if start + i < at {
                ms += u32::from(b[start + i] - b'0');
            }
        }
    }
    if hour == 24 && (minute != 0 || second != 0 || fraction_nonzero) {
        return None;
    }
    let offset = if b.get(at) == Some(&b'Z') && at + 1 == b.len() {
        0
    } else {
        let sign = match b.get(at) {
            Some(b'+') => 1,
            Some(b'-') => -1,
            _ => return None,
        };
        if at + 6 != b.len() || b.get(at + 3) != Some(&b':') {
            return None;
        }
        let h = number(at + 1, at + 3)?;
        let m = number(at + 4, at + 6)?;
        if h > 23 || m > 59 {
            return None;
        }
        sign * i128::from(h * 60 + m) * 60_000
    };
    let first =
        time::Date::from_calendar_date(year as i32, time::Month::try_from(month as u8).ok()?, 1)
            .ok()?
            .midnight()
            .assume_utc();
    Some(
        first.unix_timestamp_nanos() / 1_000_000
            + i128::from(day - 1) * 86_400_000
            + i128::from(hour * 3600 + minute * 60 + second) * 1000
            + i128::from(ms)
            - offset,
    )
}

struct NumericInput {
    value: J,
    holes: HashSet<usize>,
    hole_paths: Vec<Vec<String>>,
}
fn numeric_input(input: J) -> Result<NumericInput, LegacyWorkspaceError> {
    if input.get("numbers").is_none() {
        return Ok(NumericInput {
            value: input,
            holes: HashSet::new(),
            hole_paths: Vec::new(),
        });
    }
    let facts = crate::legacy_evaluation::number_facts(&input)?;
    let mut value = get(&input, "value")?.clone();
    let mut holes = HashSet::new();
    let mut hole_paths = Vec::new();
    let mut slots = HashSet::new();
    for fact in facts {
        let mut slot = &mut value;
        for (index, key) in fact.path.iter().enumerate() {
            if fact.kind == "hole" && index + 1 == fact.path.len() && !matches!(slot, J::Array(_)) {
                return Err(error("TypeError", "Array hole facts require an array slot"));
            }
            slot = match slot {
                J::Object(pairs) => pairs
                    .iter_mut()
                    .find(|(name, _)| name == key)
                    .map(|(_, value)| value),
                J::Array(values) => key
                    .parse::<usize>()
                    .ok()
                    .and_then(|index| values.get_mut(index)),
                _ => None,
            }
            .ok_or_else(|| error("TypeError", "Numeric observation path does not exist"))?;
        }
        let address = std::ptr::from_ref(&*slot) as usize;
        if !slots.insert(address) {
            return Err(error(
                "TypeError",
                "Numeric fact path must be unique and nonempty",
            ));
        }
        *slot = match fact.kind.as_str() {
            "nan" => J::Number(f64::NAN),
            "negative-zero" => J::Number(-0.0),
            "positive-infinity" => J::Number(f64::INFINITY),
            "negative-infinity" => J::Number(f64::NEG_INFINITY),
            "hole" => {
                holes.insert(address);
                hole_paths.push(fact.path);
                J::Null
            }
            _ => unreachable!("numeric fact kind was checked"),
        };
    }
    Ok(NumericInput {
        value,
        holes,
        hole_paths,
    })
}

pub(crate) fn numeric_facts(value: &mut J, path: &mut Vec<String>, facts: &mut Vec<J>) {
    match value {
        J::Number(number)
            if !number.is_finite() || (*number == 0.0 && number.is_sign_negative()) =>
        {
            let kind = if number.is_nan() {
                "nan"
            } else if *number == 0.0 {
                "negative-zero"
            } else if number.is_sign_positive() {
                "positive-infinity"
            } else {
                "negative-infinity"
            };
            facts.push(obj(vec![
                ("path", native(path.clone())),
                ("kind", scalar(kind)),
            ]));
            *number = 0.0;
        }
        J::Object(pairs) => {
            for (key, value) in pairs {
                path.push(key.clone());
                numeric_facts(value, path, facts);
                path.pop();
            }
        }
        J::Array(values) => {
            for (index, value) in values.iter_mut().enumerate() {
                path.push(index.to_string());
                numeric_facts(value, path, facts);
                path.pop();
            }
        }
        _ => {}
    }
}

fn evaluation(
    operation: &str,
    mut input: J,
    locale_name: &str,
    holes: &[Vec<String>],
) -> Result<J, LegacyWorkspaceError> {
    let mut numbers = Vec::new();
    numeric_facts(&mut input, &mut Vec::new(), &mut numbers);
    for path in holes {
        let mut slot = &mut input;
        for key in path {
            slot = match slot {
                J::Object(pairs) => pairs
                    .iter_mut()
                    .find(|(name, _)| name == key)
                    .map(|(_, value)| value),
                J::Array(values) => key
                    .parse::<usize>()
                    .ok()
                    .and_then(|index| values.get_mut(index)),
                _ => None,
            }
            .expect("compiled context hole path was checked");
        }
        *slot = J::Number(0.0);
        numbers.push(obj(vec![
            ("path", native(path.clone())),
            ("kind", scalar("hole")),
        ]));
    }
    let result = crate::legacy_evaluation_request(LegacyWorkspaceRequest {
        operation: operation.into(),
        input: raw(&obj(vec![("value", input), ("numbers", J::Array(numbers))]))?,
        locale: locale_name.into(),
    })?;
    parse(result.get())
}
pub(crate) fn core_registry() -> Value {
    let pack: Value =
        serde_json::from_str(include_str!("legacy_core.json")).expect("pinned core pack");
    json!({"packs":[{"key":pack["id"],"version":pack["version"]}],"definitions":pack["relations"].as_array().expect("core relations").iter().map(|r|json!({"key":r["id"],"value":r})).collect::<Vec<_>>()})
}
fn rejected(issues: Vec<ObservationIssue>, impact: J) -> J {
    let value = obj(vec![
        ("status", scalar("rejected")),
        (
            "issues",
            J::Array(issues.iter().map(|i| i.value.clone()).collect()),
        ),
        ("impact", impact.clone()),
        (
            "quarantinedSubjects",
            impact
                .get("affectedSubjects")
                .expect("impact subjects")
                .clone(),
        ),
    ]);
    response(value, issues)
}

fn compile(
    input: &J,
    locale_name: &str,
    holes: &HashSet<usize>,
    context_holes: &[Vec<String>],
) -> Result<J, LegacyWorkspaceError> {
    let document = get(input, "document")?;
    let policy = get(input, "policy")?;
    if s(policy, "schemaVersion") == "2.0.0" {
        return Err(error(
            "Error",
            "Original version 2 semantic compilation is not implemented",
        ));
    }
    let empty = obj(vec![]);
    let options = input.get("options").unwrap_or(&empty);
    let context = options
        .get("context")
        .filter(|v| !matches!(v, J::Null))
        .unwrap_or(&empty);
    let evaluated_at = text(options, "evaluatedAt")?;
    let doc = project(document)?;
    let pol = project(policy)?;
    let registry = input
        .get("registry")
        .map(project)
        .transpose()?
        .unwrap_or_else(core_registry);
    let changed = strings(options, "changedSubjects");
    let run_impact = |changed: Vec<String>,
                      active: Option<&HashSet<String>>|
     -> Result<J, LegacyWorkspaceError> {
        let mut options = json!({"changedSubjects":changed,"policy":pol});
        if let Some(active) = active {
            options["activeMappings"] = json!(active);
        }
        impact(
            &json!({"document":doc,"options":options,"registry":registry}),
            locale_name,
        )
    };
    if input
        .get("executablePackCount")
        .is_some_and(|v| matches!(v,J::Number(n) if *n>0.0))
        || items(document, "mappings").iter().any(|m| {
            m.get("attributes")
                .and_then(|a| a.get("metamap:derivation"))
                .is_some()
        })
    {
        return Ok(rejected(
            vec![ObservationIssue::new(
                "EXECUTABLE_POLICY_REQUIRED",
                "Executable packs and proof claims require the version 2 policy profile",
                Some(s(policy, "id")),
                None,
            )],
            run_impact(changed, None)?,
        ));
    }
    let graph_registry: LegacyGraphRegistry =
        serde_json::from_value(registry.clone()).map_err(|e| error("TypeError", &e.to_string()))?;
    let graph_validation = validate_legacy_document(&doc, &graph_registry);
    let mut issues = graph_validation
        .issues
        .into_iter()
        .map(|i| {
            let value = observed(i);
            let mut pairs = vec![];
            for k in ["severity", "code", "message", "path", "subjectId"] {
                if let Some(v) = value.get(k) {
                    pairs.push((k, v.clone()));
                }
            }
            ObservationIssue {
                value: obj(pairs),
                keys: ["severity", "code", "message", "path", "subjectId"]
                    .map(str::to_owned)
                    .to_vec(),
            }
        })
        .collect::<Vec<_>>();
    let policy_issues = validate_policy(policy, holes)?;
    let policy_valid = policy_issues.is_empty();
    issues.extend(policy_issues);
    if timestamp(evaluated_at).is_none() {
        issues.push(ObservationIssue::new(
            "INVALID_EVALUATION_TIME",
            &format!("{evaluated_at} is not a valid timestamp"),
            Some(s(policy, "id")),
            None,
        ));
    }
    if !graph_validation.valid || !policy_valid {
        let impact = run_impact(changed, None)?;
        attach_paths(&mut issues, &impact);
        return Ok(rejected(issues, impact));
    }
    let mappings = items(document, "mappings");
    let declarations = items(policy, "mappings");
    let kinds = json!(
        items(document, "entities")
            .iter()
            .map(|e| vec![s(e, "id"), s(e, "kind")])
            .collect::<Vec<_>>()
    );
    let mut resolved: HashMap<&str, Vec<&J>> = HashMap::new();
    let mut mapping_order = Vec::new();
    let mut counts = vec![0; declarations.len()];
    for mapping in mappings {
        let id = s(mapping, "id");
        let mut ds = declarations
            .iter()
            .filter(|d| d.get("mapping").is_some_and(|v| v.string() == Some(id)))
            .collect::<Vec<_>>();
        for (i, d) in declarations.iter().enumerate() {
            if d.get("mapping").is_none()
                && selector(
                    &json!({"mapping":project(mapping)?,"selector":project(get(d,"select")?)?,"entityKinds":kinds}),
                )?
            {
                ds.push(d);
                counts[i] += 1;
            }
        }
        if !resolved.contains_key(id) {
            mapping_order.push(id);
        }
        resolved.insert(id, ds);
    }
    let pid = s(policy, "id");
    let graph = get(policy, "graph")?;
    let graph_digest = digest(document, locale_name)?;
    if s(graph, "id") != s(document, "id") {
        issues.push(ObservationIssue::new(
            "GRAPH_BINDING_MISMATCH",
            &format!(
                "Policy expects {}, received {}",
                s(graph, "id"),
                s(document, "id")
            ),
            Some(pid),
            None,
        ));
    }
    if let Some(revision) = graph.get("revision")
        && revision.string() != document.get("revision").and_then(J::string)
    {
        issues.push(ObservationIssue::new(
            "GRAPH_REVISION_MISMATCH",
            &format!(
                "Policy expects graph revision {}, received {}",
                revision.js_text(),
                document
                    .get("revision")
                    .map(J::js_text)
                    .unwrap_or_else(|| "unversioned".into())
            ),
            Some(pid),
            None,
        ));
    }
    if graph
        .get("digest")
        .is_some_and(|d| d.string() != Some(&graph_digest))
    {
        issues.push(ObservationIssue::new(
            "GRAPH_DIGEST_MISMATCH",
            &format!("Policy graph digest does not match {}", s(document, "id")),
            Some(pid),
            None,
        ));
    }
    let mapping_ids = mappings.iter().map(|m| s(m, "id")).collect::<HashSet<_>>();
    for (index, d) in declarations.iter().enumerate() {
        if let Some(id) = d.get("mapping").and_then(J::string)
            && !mapping_ids.contains(id)
        {
            issues.push(ObservationIssue::new(
                "UNKNOWN_MAPPING_DECLARATION",
                &format!("Policy declares missing mapping {id}"),
                Some(id),
                None,
            ));
        }
        if let Some(select) = d.get("select") {
            if counts[index] == 0 {
                issues.push(ObservationIssue::new(
                    "EMPTY_MAPPING_SELECTOR",
                    &format!("Mapping selector at policy index {index} matches no graph mappings"),
                    Some(pid),
                    None,
                ));
            }
            for id in strings(select, "ids") {
                if !mapping_ids.contains(id.as_str()) {
                    issues.push(ObservationIssue::new(
                        "UNKNOWN_MAPPING_SELECTOR_ID",
                        &format!("Mapping selector references missing mapping {id}"),
                        Some(&id),
                        None,
                    ));
                }
            }
        }
    }
    for mapping in mappings {
        let id = s(mapping, "id");
        let count = resolved[id].len();
        if count == 0 {
            issues.push(ObservationIssue::new(
                "MAPPING_POLICY_MISSING",
                &format!("{id} has no viability declaration"),
                Some(id),
                None,
            ));
        } else if count > 1 {
            issues.push(ObservationIssue::new(
                "DUPLICATE_MAPPING_POLICY",
                &format!("{id} has {count} viability declarations"),
                Some(id),
                None,
            ));
        }
    }
    let mut known = HashSet::from([s(document, "id").to_owned()]);
    for field in ["entities", "mappings", "authorities"] {
        known.extend(items(document, field).iter().map(|e| s(e, "id").to_owned()));
    }
    for entry in items(policy, "constraints")
        .iter()
        .chain(items(policy, "evidence"))
    {
        for subject in strings(entry, "subjects") {
            if !known.contains(&subject) {
                issues.push(ObservationIssue::new(
                    "UNKNOWN_POLICY_SUBJECT",
                    &format!(
                        "{} references unknown graph subject {subject}",
                        s(entry, "id")
                    ),
                    Some(s(entry, "id")),
                    None,
                ));
            }
        }
    }
    for field in ["constraints", "evidence"] {
        known.extend(items(policy, field).iter().map(|e| s(e, "id").to_owned()));
    }
    for waiver in items(policy, "waivers") {
        for subject in strings(waiver, "subjects") {
            if !known.contains(&subject) {
                issues.push(ObservationIssue::new(
                    "UNKNOWN_WAIVER_SUBJECT",
                    &format!("{} references unknown subject {subject}", s(waiver, "id")),
                    Some(s(waiver, "id")),
                    None,
                ));
            }
        }
    }
    for mapping in mappings {
        let id = s(mapping, "id");
        if resolved[id].len() != 1 {
            continue;
        }
        let d = resolved[id][0];
        let relation = s(mapping, "relation");
        let direction = registry["definitions"]
            .as_array()
            .and_then(|ds| ds.iter().find(|d| d["key"].as_str() == Some(relation)))
            .and_then(|d| d["value"].get("impactDirection"))
            .and_then(Value::as_str);
        if direction.is_none_or(str::is_empty) {
            issues.push(ObservationIssue::new(
                "UNDECLARED_IMPACT_DIRECTION",
                &format!("{relation} must declare impactDirection before {id} can activate"),
                Some(id),
                None,
            ));
        }
        let lossiness = s(mapping, "lossiness");
        if lossiness == "unknown" {
            issues.push(ObservationIssue::new(
                "UNDECLARED_LOSSINESS",
                &format!("{id} must declare lossless or lossy before activation"),
                Some(id),
                None,
            ));
        }
        let transform = mapping.get("transform");
        if s(d, "determinism") == "deterministic"
            && transform.is_some_and(|t| !matches!(t.get("deterministic"), Some(J::Bool(true))))
        {
            issues.push(ObservationIssue::new(
                "UNVERIFIED_DETERMINISM",
                &format!("{id} claims deterministic execution but its transform does not"),
                Some(id),
                None,
            ));
        }
        if s(d, "reversibility") == "reversible" {
            if lossiness != "lossless" {
                issues.push(ObservationIssue::new(
                    "REVERSIBLE_MAPPING_IS_LOSSY",
                    &format!("{id} cannot be reversible with {lossiness} lossiness"),
                    Some(id),
                    None,
                ));
            }
            if transform.is_some_and(|t| !matches!(t.get("reversible"), Some(J::Bool(true)))) {
                issues.push(ObservationIssue::new(
                    "UNVERIFIED_REVERSIBILITY",
                    &format!("{id} claims reversibility but its transform does not"),
                    Some(id),
                    None,
                ));
            }
        }
    }
    for id in &mapping_order {
        for declaration in &resolved[id] {
            let mut required = Vec::new();
            let mut seen = HashSet::new();
            if let Some(a) = declaration.get("applicability") {
                for k in ["when", "unless"] {
                    if let Some(expr) = a.get(k) {
                        let keys = evaluation(
                            "required",
                            obj(vec![("expression", expr.clone())]),
                            locale_name,
                            &[],
                        )?;
                        for key in keys.array().expect("required keys") {
                            let key = key.string().expect("context key");
                            if seen.insert(key.to_owned()) {
                                required.push(key.to_owned());
                            }
                        }
                    }
                }
            }
            for key in required {
                if context.get(&key).is_none() {
                    issues.push(ObservationIssue::new(
                        "CONTEXT_KEY_MISSING",
                        &format!("{id} requires context key {key}"),
                        Some(id),
                        None,
                    ));
                }
            }
        }
    }
    let mut active = HashSet::new();
    let mut inactive = Vec::new();
    for mapping in mappings {
        let id = s(mapping, "id");
        if resolved[id].len() != 1 {
            continue;
        }
        let d = resolved[id][0];
        let reason = evaluation(
            "inactive",
            obj(vec![
                (
                    "applicability",
                    d.get("applicability").cloned().unwrap_or(J::Null),
                ),
                ("context", context.clone()),
            ]),
            locale_name,
            context_holes,
        )?;
        if let Some(reason) = reason.string() {
            inactive.push(obj(vec![
                ("id", J::String(id.into())),
                ("reason", J::String(reason.into())),
            ]));
        } else {
            active.insert(id.to_owned());
        }
    }
    let collator = locale(locale_name)?;
    inactive.sort_by(|a, b| {
        collator.compare_legacy_utf16(
            &Data::string_units(s(a, "id")),
            &Data::string_units(s(b, "id")),
        )
    });
    for evidence in items(policy, "evidence") {
        if s(evidence, "result") == "contradicts" {
            for subject in strings(evidence, "subjects") {
                if !mapping_ids.contains(subject.as_str()) || active.contains(&subject) {
                    issues.push(ObservationIssue::new(
                        "CONTRADICTING_EVIDENCE",
                        &format!("{} contradicts active subject {subject}", s(evidence, "id")),
                        Some(&subject),
                        None,
                    ));
                }
            }
        }
    }
    if input
        .get("callbackPhase")
        .is_some_and(|v| matches!(v, J::Bool(true)))
    {
        let active_order = mappings
            .iter()
            .filter(|mapping| active.contains(s(mapping, "id")))
            .map(|mapping| s(mapping, "id").to_owned())
            .collect::<Vec<_>>();
        let frame = obj(vec![
            (
                "issues",
                J::Array(issues.iter().map(|issue| issue.value.clone()).collect()),
            ),
            (
                "issueKeys",
                native(issues.iter().map(|issue| &issue.keys).collect::<Vec<_>>()),
            ),
            ("activeMappings", native(active_order)),
            ("inactiveMappings", J::Array(inactive)),
            ("graphDigest", scalar(&graph_digest)),
            ("evaluatedAt", scalar(evaluated_at)),
        ]);
        return Ok(obj(vec![(
            "value",
            obj(vec![("status", scalar("constraints")), ("frame", frame)]),
        )]));
    }
    for constraint in items(policy, "constraints") {
        let kind = s(constraint, "kind");
        if !crate::legacy_references::relation(&Data::string_units(kind)) {
            issues.push(ObservationIssue::new(
                "INVALID_CONSTRAINT_KIND",
                &format!("{kind} must use namespace:name form"),
                Some(s(constraint, "id")),
                None,
            ));
        } else if !crate::legacy_constraints::KINDS.contains(&kind) {
            issues.push(ObservationIssue::new(
                "UNKNOWN_CONSTRAINT_KIND",
                &format!("No evaluator is registered for {kind}"),
                Some(s(constraint, "id")),
                None,
            ));
        } else {
            issues.extend(crate::legacy_constraints::evaluate(
                constraint,
                document,
                &active,
                items(policy, "evidence"),
                &registry,
            )?);
        }
    }
    let handles = vec![None; issues.len()];
    complete_compilation(
        input,
        locale_name,
        CompilationState {
            issues,
            active,
            inactive,
            evaluated_at: evaluated_at.to_owned(),
            handles,
        },
    )
}

struct CompilationState {
    issues: Vec<ObservationIssue>,
    active: HashSet<String>,
    inactive: Vec<J>,
    evaluated_at: String,
    handles: Vec<Option<usize>>,
}
fn complete_compilation(
    input: &J,
    locale_name: &str,
    state: CompilationState,
) -> Result<J, LegacyWorkspaceError> {
    let CompilationState {
        mut issues,
        active,
        inactive,
        evaluated_at,
        handles,
    } = state;
    let mut issue_writes = Vec::new();
    let evaluated_at = evaluated_at.as_str();
    let document = get(input, "document")?;
    let policy = get(input, "policy")?;
    let empty = obj(vec![]);
    let options = input.get("options").unwrap_or(&empty);
    let context = options
        .get("context")
        .filter(|v| !matches!(v, J::Null))
        .unwrap_or(&empty);
    let changed = strings(options, "changedSubjects");
    let doc = project(document)?;
    let pol = project(policy)?;
    let registry = input
        .get("registry")
        .map(project)
        .transpose()?
        .unwrap_or_else(core_registry);
    let mapping_ids = items(document, "mappings")
        .iter()
        .map(|m| s(m, "id"))
        .collect::<HashSet<_>>();
    let run_impact = |changed: Vec<String>,
                      active: Option<&HashSet<String>>|
     -> Result<J, LegacyWorkspaceError> {
        let mut options = json!({"changedSubjects":changed,"policy":pol});
        if let Some(active) = active {
            options["activeMappings"] = json!(active);
        }
        impact(
            &json!({"document":doc,"options":options,"registry":registry}),
            locale_name,
        )
    };
    let mut applied = HashSet::new();
    const WAIVABLE: [&str; 10] = [
        "CONTRADICTING_EVIDENCE",
        "FORBIDDEN_MAPPING_ACTIVE",
        "NON_UNIQUE_MAPPING_TARGET",
        "REQUIRED_AUTHORITY_UNRESOLVED",
        "REQUIRED_EVIDENCE_MISSING",
        "REQUIRED_MAPPING_MISSING",
        "UNDECLARED_LOSSINESS",
        "UNDECLARED_IMPACT_DIRECTION",
        "UNVERIFIED_DETERMINISM",
        "UNVERIFIED_REVERSIBILITY",
    ];
    for waiver in items(policy, "waivers") {
        let id = s(waiver, "id");
        let expires = s(waiver, "expiresAt");
        let Some(expiry) = timestamp(expires) else {
            issues.push(ObservationIssue::new(
                "INVALID_WAIVER_EXPIRY",
                &format!("{id} has invalid expiry {expires}"),
                Some(id),
                None,
            ));
            continue;
        };
        if timestamp(evaluated_at).is_some_and(|now| expiry <= now) {
            issues.push(ObservationIssue::new(
                "EXPIRED_WAIVER",
                &format!("{id} expired at {expires}"),
                Some(id),
                None,
            ));
            continue;
        }
        let mut matched = false;
        for index in 0..issues.len() {
            let issue = &mut issues[index];
            let code = s(&issue.value, "code");
            let subject = s(&issue.value, "subjectId");
            if s(&issue.value, "severity") == "error"
                && WAIVABLE.contains(&code)
                && items(waiver, "codes")
                    .iter()
                    .any(|v| v.string() == Some(code))
                && issue.value.get("subjectId").is_some()
                && items(waiver, "subjects")
                    .iter()
                    .any(|v| v.string() == Some(subject))
            {
                issue.set("severity", scalar("warning"));
                issue.set("waivedBy", J::String(id.into()));
                applied.insert(id.to_owned());
                matched = true;
                if let Some(handle) = handles.get(index).copied().flatten() {
                    issue_writes.push(native(
                        json!({"handle":handle,"key":"severity","value":"warning"}),
                    ));
                    issue_writes.push(native(json!({"handle":handle,"key":"waivedBy","value":id})));
                    let value = issues[index].value.clone();
                    let keys = issues[index].keys.clone();
                    for (other, other_handle) in handles.iter().enumerate() {
                        if *other_handle == Some(handle) {
                            issues[other].value = value.clone();
                            issues[other].keys = keys.clone();
                        }
                    }
                }
            }
        }
        if !matched {
            let mut issue = ObservationIssue::constraint(
                "STALE_WAIVER",
                &format!("{id} does not match an active, waivable issue"),
                id,
            );
            issue.set("severity", scalar("warning"));
            issues.push(issue);
        }
    }
    let failure_seeds = issues
        .iter()
        .filter(|i| s(&i.value, "severity") == "error")
        .filter_map(|i| {
            i.value
                .get("subjectId")
                .and_then(J::string)
                .map(str::to_owned)
        })
        .collect();
    let impact = run_impact(
        if changed.is_empty() {
            failure_seeds
        } else {
            changed
        },
        Some(&active),
    )?;
    attach_paths(&mut issues, &impact);
    for (index, issue) in issues.iter().enumerate() {
        if let Some(handle) = handles.get(index).copied().flatten() {
            let subject = s(&issue.value, "subjectId");
            if !subject.is_empty() {
                let mut write = json!({"handle":handle,"key":"causalPath"});
                if let Some(path_index) = items(&impact, "paths")
                    .iter()
                    .position(|path| s(path, "subjectId") == subject)
                {
                    write["pathIndex"] = json!(path_index);
                }
                issue_writes.push(native(write));
            }
        }
    }
    if issues.iter().any(|i| s(&i.value, "severity") == "error") {
        let mut result = rejected(issues, impact);
        let J::Object(pairs) = &mut result else {
            unreachable!()
        };
        pairs.push(("issueHandles".into(), native(handles)));
        pairs.push(("issueWrites".into(), J::Array(issue_writes)));
        return Ok(result);
    }
    let sorted = |values: HashSet<String>| {
        let mut values = values.into_iter().collect::<Vec<_>>();
        values.sort_by_key(|s| Data::string_units(s));
        J::Array(values.into_iter().map(J::String).collect())
    };
    let graph_digest = digest(document, locale_name)?;
    let mut graph_pairs = vec![("id", get(document, "id")?.clone())];
    if let Some(revision) = document.get("revision") {
        graph_pairs.push(("revision", revision.clone()));
    }
    graph_pairs.push(("digest", scalar(&graph_digest)));
    let mut evidence = items(policy, "evidence")
        .iter()
        .filter(|e| {
            s(e, "result") == "supports"
                && strings(e, "subjects")
                    .iter()
                    .any(|s| !mapping_ids.contains(s.as_str()) || active.contains(s))
        })
        .map(|e| s(e, "id").to_owned())
        .collect::<Vec<_>>();
    evidence.sort_by_key(|s| Data::string_units(s));
    let content = obj(vec![
        ("schemaVersion", scalar("1.0.0")),
        ("evaluatedAt", scalar(evaluated_at)),
        ("graph", obj(graph_pairs)),
        (
            "policy",
            obj(vec![
                ("id", get(policy, "id")?.clone()),
                ("digest", scalar(&digest(policy, locale_name)?)),
            ]),
        ),
        ("context", context.clone()),
        ("activeMappings", sorted(active)),
        ("inactiveMappings", J::Array(inactive)),
        (
            "evidence",
            J::Array(evidence.into_iter().map(J::String).collect()),
        ),
        ("waiversApplied", sorted(applied)),
    ]);
    let digest = digest(&content, locale_name)?;
    let J::Object(content) = content else {
        unreachable!()
    };
    let mut generation = vec![(
        "$schema".into(),
        scalar(
            "https://raw.githubusercontent.com/roryscot/metamap/v0.3.0/schemas/metamap-generation.schema.json",
        ),
    )];
    generation.extend(content);
    generation.push((
        "id".into(),
        scalar(&format!(
            "urn:metamap:generation:{}",
            digest.trim_start_matches("sha256:")
        )),
    ));
    generation.push(("digest".into(), scalar(&digest)));
    let value = obj(vec![
        ("status", scalar("viable")),
        ("generation", J::Object(generation)),
        (
            "issues",
            J::Array(issues.iter().map(|i| i.value.clone()).collect()),
        ),
        ("impact", impact),
    ]);
    let issue_handles = native(handles);
    let mut result = response(value, issues);
    let J::Object(pairs) = &mut result else {
        unreachable!()
    };
    pairs.push(("graphKeys".into(), native(vec!["id", "revision", "digest"])));
    pairs.push(("issueHandles".into(), issue_handles));
    pairs.push(("issueWrites".into(), J::Array(issue_writes)));
    Ok(result)
}
fn attach_paths(issues: &mut [ObservationIssue], impact: &J) {
    for issue in issues {
        let id = s(&issue.value, "subjectId");
        if !id.is_empty() {
            let path = items(impact, "paths")
                .iter()
                .find(|p| s(p, "subjectId") == id)
                .and_then(|p| p.get("path"))
                .cloned();
            if let Some(path) = path {
                issue.set("causalPath", path);
            } else if !issue.keys.iter().any(|key| key == "causalPath") {
                issue.keys.push("causalPath".to_owned());
            }
        }
    }
}

fn continuation(
    input: &J,
    locale_name: &str,
    holes: &HashSet<usize>,
) -> Result<J, LegacyWorkspaceError> {
    for (owner, field) in [
        (get(input, "document")?, "mappings"),
        (get(input, "document")?, "authorities"),
        (get(input, "policy")?, "constraints"),
        (get(input, "policy")?, "evidence"),
    ] {
        if items(owner, field)
            .iter()
            .any(|value| holes.contains(&(std::ptr::from_ref(value) as usize)))
        {
            return Err(error(
                "TypeError",
                "Iterator value undefined is not an entry object",
            ));
        }
    }
    let frame = get(input, "frame")?;
    let values = items(frame, "issues");
    let keys = items(frame, "issueKeys");
    if values.len() != keys.len() {
        return Err(error("TypeError", "Invalid compilation issue frame"));
    }
    let mut issues = values
        .iter()
        .zip(keys)
        .map(|(value, keys)| ObservationIssue {
            value: value.clone(),
            keys: keys
                .array()
                .unwrap_or(&[])
                .iter()
                .filter_map(J::string)
                .map(str::to_owned)
                .collect(),
        })
        .collect::<Vec<_>>();
    let mut handles = vec![None; issues.len()];
    for issue in items(input, "callbackIssues") {
        issues.push(ObservationIssue {
            value: get(issue, "value")?.clone(),
            keys: strings(issue, "keys"),
        });
        handles.push(match issue.get("handle") {
            Some(J::Number(value))
                if value.is_finite() && *value >= 0.0 && value.fract() == 0.0 =>
            {
                Some(*value as usize)
            }
            _ => None,
        });
    }
    let active = strings(input, "activeMappings").into_iter().collect();
    complete_compilation(
        input,
        locale_name,
        CompilationState {
            issues,
            active,
            inactive: items(frame, "inactiveMappings").to_vec(),
            evaluated_at: text(frame, "evaluatedAt")?.to_owned(),
            handles,
        },
    )
}

fn constraint_operation(operation: &str, input: &J) -> Result<J, LegacyWorkspaceError> {
    match operation {
        "constraint-kinds" => {
            let names = [
                "requiresEvidence",
                "requiresMapping",
                "forbidsMapping",
                "uniqueTarget",
                "requiresAuthority",
                "topologyRelationTotality",
                "topologyReachable",
                "topologyContextSatisfied",
            ];
            Ok(obj(vec![(
                "value",
                native(
                    crate::legacy_constraints::KINDS
                        .iter()
                        .zip(names)
                        .map(|(kind, name)| json!({"kind":kind,"name":name}))
                        .collect::<Vec<_>>(),
                ),
            )]))
        }
        "constraint-register" | "constraint-get" => {
            let keys = items(input, "keys");
            let key = get(input, "key")?;
            let ordinal = keys.iter().position(
                |value| matches!((value,key),(J::Number(left),J::Number(right)) if left == right),
            );
            Ok(obj(vec![(
                "value",
                if operation == "constraint-register" {
                    native(ordinal.is_some())
                } else {
                    ordinal.map_or(J::Null, native)
                },
            )]))
        }
        "constraint-select" => {
            let c = get(input, "constraint")?;
            if !crate::legacy_references::relation(&Data::string_units(s(c, "kind"))) {
                let issue = ObservationIssue::new(
                    "INVALID_CONSTRAINT_KIND",
                    &format!("{} must use namespace:name form", get(c, "kind")?.js_text()),
                    Some(s(c, "id")),
                    None,
                );
                Ok(response(
                    obj(vec![
                        ("status", scalar("missing")),
                        ("issues", J::Array(vec![issue.value.clone()])),
                    ]),
                    vec![issue],
                ))
            } else {
                Ok(obj(vec![(
                    "value",
                    obj(vec![
                        ("status", scalar("lookup")),
                        ("kind", get(c, "kind")?.clone()),
                    ]),
                )]))
            }
        }
        "constraint-missing" => {
            let c = get(input, "constraint")?;
            let issue = ObservationIssue::new(
                "UNKNOWN_CONSTRAINT_KIND",
                &format!("No evaluator is registered for {}", s(c, "kind")),
                Some(s(c, "id")),
                None,
            );
            Ok(response(
                obj(vec![("issues", J::Array(vec![issue.value.clone()]))]),
                vec![issue],
            ))
        }
        "constraint-evaluate" => {
            let context = get(input, "context")?;
            let registry = context
                .get("registry")
                .map(project)
                .transpose()?
                .unwrap_or_else(core_registry);
            let graph = context.get("graph").map(project).transpose()?;
            let active = strings(context, "activeMappings").into_iter().collect();
            let issues = crate::legacy_constraints::evaluate_as(
                text(input, "kind")?,
                get(input, "constraint")?,
                get(context, "document")?,
                &active,
                items(context, "evidence"),
                &registry,
                graph.as_ref(),
            )?;
            Ok(response(
                J::Array(issues.iter().map(|issue| issue.value.clone()).collect()),
                issues,
            ))
        }
        _ => Err(error("TypeError", "Unknown constraint registry operation")),
    }
}

fn activation_operation(
    operation: &str,
    input: &J,
    locale_name: &str,
) -> Result<J, LegacyWorkspaceError> {
    match operation {
        "activation-receiver" => {
            let member = text(input, "member")?;
            if !["governedHost", "governedState"].contains(&member) {
                return Err(error("TypeError", "Unknown activator private member"));
            }
            let message = if matches!(input.get("nullReceiver"), Some(J::Bool(true))) {
                format!("Cannot read properties of null (reading '#{member}')")
            } else if matches!(input.get("undefinedReceiver"), Some(J::Bool(true))) {
                format!("Cannot read properties of undefined (reading '#{member}')")
            } else {
                format!(
                    "Cannot read private member #{member} from an object whose class did not declare it"
                )
            };
            Err(error("TypeError", &message))
        }
        "activation-select" => {
            let has_policy = matches!(input.get("hasPolicy"), Some(J::Bool(true)));
            let host = matches!(input.get("hostPresent"), Some(J::Bool(true)));
            let action = if !has_policy {
                if host && s(input, "hostMode") == "governed" {
                    "governed"
                } else {
                    "host-required"
                }
            } else if host || s(input, "policyVersion") != "1.0.0" {
                "protected"
            } else {
                "compile"
            };
            let mut value = vec![("action", scalar(action))];
            if action == "host-required" {
                value.push(("result",obj(vec![("status",scalar("rejected")),("activated",J::Bool(false)),("issues",native(json!([{"code":"GOVERNANCE_HOST_REQUIRED","message":"The consumer must select governed mode outside the request"}])))])));
            }
            Ok(obj(vec![("value", obj(value))]))
        }
        "activation-protected" => {
            let options = json!({"changedSubjects":strings(input,"changedSubjects")});
            let registry = input
                .get("registry")
                .map(project)
                .transpose()?
                .unwrap_or_else(core_registry);
            let impact = impact(
                &json!({"document":project(get(input,"document")?)?,"options":options,"registry":registry}),
                locale_name,
            )?;
            let mut issue = ObservationIssue::new(
                "PROTECTED_ACTIVATION_REQUIRED",
                "Governed consumers and version 2 candidates require exact protected approval",
                None,
                None,
            );
            if let Some(subject) = input.get("subjectId") {
                issue.set("subjectId", subject.clone());
            }
            Ok(rejected(vec![issue], impact))
        }
        "activation-complete" => {
            let activated = match s(input, "compilationStatus") {
                "viable" => true,
                "rejected" => false,
                _ => return Err(error("TypeError", "Invalid memory compilation status")),
            };
            Ok(obj(vec![(
                "value",
                native(json!({"activated":activated,"publishGeneration":activated})),
            )]))
        }
        "activation-governed" => Err(error(
            "Error",
            "Legacy signed governed activation transport is not implemented",
        )),
        _ => Err(error("TypeError", "Unknown memory activation operation")),
    }
}

pub fn legacy_viability_request(
    request: LegacyWorkspaceRequest,
) -> Result<Box<RawValue>, LegacyWorkspaceError> {
    let observation = numeric_input(parse(&request.input)?)?;
    let input = &observation.value;
    let context_holes = observation
        .hole_paths
        .iter()
        .filter(|path| path.len() > 2 && path[0] == "options" && path[1] == "context")
        .map(|path| {
            std::iter::once("context".to_owned())
                .chain(path[2..].iter().cloned())
                .collect::<Vec<_>>()
        })
        .collect::<Vec<_>>();
    let result = match request.operation.as_str() {
        operation if operation.starts_with("uncertainty-") || operation.starts_with("risk-") => {
            crate::legacy_uncertainty_risk::request(operation, input)?
        }
        operation if operation.starts_with("projection-") => crate::legacy_projection::request(
            operation,
            input,
            &request.locale,
            &observation.holes,
        )?,
        operation if operation.starts_with("semantic-") => {
            crate::legacy_semantic::request(operation, input)?
        }
        "validate-policy" => {
            validation_response(validate_policy(get(input, "value")?, &observation.holes)?)
        }
        "validate-generation" => validation_response(validate_generation(
            get(input, "value")?,
            &request.locale,
            &observation.holes,
        )?),
        "parse-policy" | "parse-generation" => {
            let v = get(input, "value")?;
            let generation = request.operation == "parse-generation";
            let issues = if generation {
                validate_generation(v, &request.locale, &observation.holes)?
            } else {
                validate_policy(v, &observation.holes)?
            };
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
                        if generation {
                            "generation"
                        } else {
                            "viability policy"
                        }
                    ),
                ));
            }
            if !generation
                && (s(v, "schemaVersion") != "1.0.0"
                    || !crate::legacy_references::reference(&Data::string_units(s(v, "id"))))
            {
                return Err(error("Error", "Invalid Metamap viability policy identity"));
            }
            response(v.clone(), issues)
        }
        "compile" | "compile-start" => {
            compile(input, &request.locale, &observation.holes, &context_holes)?
        }
        "compile-finish" => continuation(input, &request.locale, &observation.holes)?,
        "activation-receiver"
        | "activation-select"
        | "activation-protected"
        | "activation-complete"
        | "activation-governed" => {
            activation_operation(&request.operation, input, &request.locale)?
        }
        "constraint-kinds"
        | "constraint-register"
        | "constraint-get"
        | "constraint-select"
        | "constraint-missing"
        | "constraint-evaluate" => constraint_operation(&request.operation, input)?,
        _ => return Err(error("TypeError", "Unknown legacy viability operation")),
    };
    RawValue::from_string(raw(&result)?).map_err(|e| error("Error", &e.to_string()))
}
