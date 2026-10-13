//! Legacy declarations and drift observations over a read-only snapshot. A
//! canonical declaration here is data, not checked authority or admission.
use crate::legacy_references::urn;
use crate::legacy_reporting::{LegacyReportText as Text, js_text};
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyReadOnlyJson as Data,
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json, value::RawValue};
use std::collections::{HashMap, HashSet};
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LegacyCorrespondenceRequest {
    pub input: String,
}
#[derive(Debug, thiserror::Error, Serialize)]
#[error("{message}")]
pub struct LegacyCorrespondenceError {
    pub code: String,
    pub name: String,
    pub message: String,
}
fn failure(message: impl Into<String>) -> LegacyCorrespondenceError {
    LegacyCorrespondenceError {
        code: "LEGACY_CORRESPONDENCE_INPUT".into(),
        name: "Error".into(),
        message: message.into(),
    }
}
fn string<'a>(v: &'a J, key: &str) -> Result<&'a str, LegacyCorrespondenceError> {
    v.get(key)
        .and_then(J::string)
        .ok_or_else(|| failure(format!("Read-only legacy {key} requires a string")))
}
fn array<'a>(v: &'a J, key: &str) -> Result<&'a [J], LegacyCorrespondenceError> {
    v.get(key)
        .and_then(J::array)
        .ok_or_else(|| failure(format!("Read-only legacy {key} requires an array")))
}
fn nonnull(v: Option<&J>) -> Option<&J> {
    v.filter(|v| !matches!(v, J::Null))
}
fn optional_array<'a>(v: Option<&'a J>, label: &str) -> Result<&'a [J], LegacyCorrespondenceError> {
    match nonnull(v) {
        None => Ok(&[]),
        Some(J::Array(items)) => Ok(items),
        _ => Err(failure(format!(
            "Read-only legacy {label} requires an array"
        ))),
    }
}
fn attr<'a>(v: &'a J, key: &str) -> Option<&'a J> {
    v.get("attributes").and_then(|a| a.get(key))
}
fn string_attr<'a>(v: &'a J, key: &str) -> Option<&'a str> {
    attr(v, key).and_then(J::string)
}
fn bool_attr(v: &J, key: &str) -> Option<bool> {
    if let Some(J::Bool(b)) = attr(v, key) {
        Some(*b)
    } else {
        None
    }
}
fn truthy(v: Option<&J>) -> bool {
    match v {
        None | Some(J::Null) | Some(J::Bool(false)) => false,
        Some(J::String(s)) => !s.is_empty(),
        Some(J::Number(n)) => *n != 0.0,
        _ => true,
    }
}
fn object(fields: Vec<(&str, J)>) -> J {
    J::Object(fields.into_iter().map(|(k, v)| (k.to_owned(), v)).collect())
}
fn literal(s: &str) -> J {
    Data::string_value(&s.encode_utf16().collect::<Vec<_>>())
}
fn text(s: &Text) -> J {
    Data::string_value(&s.0)
}
fn source(s: &str) -> J {
    J::String(s.to_owned())
}
fn fields(v: Option<&J>, fallback: &str) -> J {
    nonnull(v).cloned().unwrap_or_else(|| literal(fallback))
}
macro_rules! line {($($part:expr),*$(,)?)=>{Text::join(&[$(Text::from($part)),*],"")};}
fn make_id(namespace: &Text, kind: &str, value: &Text) -> Result<J, LegacyCorrespondenceError> {
    urn(namespace, &kind.into(), value)
        .map(|v| text(&v))
        .map_err(|e| LegacyCorrespondenceError {
            code: "LEGACY_CORRESPONDENCE_INPUT".into(),
            name: e.name,
            message: e.message,
        })
}
fn string_names(values: &[J]) -> Result<Vec<&str>, LegacyCorrespondenceError> {
    values
        .iter()
        .map(|v| {
            v.string()
                .ok_or_else(|| failure("Read-only legacy name/fact set requires strings"))
        })
        .collect()
}
fn by_name<'a>(entities: &[&'a J]) -> Vec<(&'a str, &'a J)> {
    let mut slots = HashMap::new();
    let mut result = Vec::new();
    for &entity in entities {
        if let Some(name) = string_attr(entity, "name").filter(|s| !s.is_empty()) {
            if let Some(&slot) = slots.get(name) {
                result[slot] = (name, entity)
            } else {
                slots.insert(name, result.len());
                result.push((name, entity));
            }
        }
    }
    result
}
fn symbolic_type(value: &str) -> String {
    let value = value
        .strip_prefix("reference:")
        .or_else(|| value.strip_prefix("enum:"))
        .unwrap_or(value);
    let value = if value.len() >= 6
        && value
            .get(value.len() - 6..)
            .is_some_and(|s| s.eq_ignore_ascii_case("schema"))
    {
        &value[..value.len() - 6]
    } else {
        value
    };
    value
        .chars()
        .filter(char::is_ascii_alphanumeric)
        .map(|c| c.to_ascii_lowercase())
        .collect()
}
fn types_compatible(a: Option<&str>, b: Option<&str>) -> bool {
    if a.is_none_or(str::is_empty) || b.is_none_or(str::is_empty) {
        return a == b;
    }
    if a == b {
        return true;
    }
    let a = a.expect("nonempty type");
    let b = b.expect("nonempty type");
    (a.starts_with("reference:") || a.starts_with("enum:"))
        && (b.starts_with("reference:") || b.starts_with("enum:"))
        && symbolic_type(a) == symbolic_type(b)
}
fn fact_matches(fact: &str, a: &J, b: &J) -> bool {
    match fact {
        "type" => types_compatible(string_attr(a, "dataType"), string_attr(b, "dataType")),
        "cardinality" => string_attr(a, "cardinality") == string_attr(b, "cardinality"),
        "presence" => bool_attr(a, "presenceRequired") == bool_attr(b, "presenceRequired"),
        _ => bool_attr(a, "nullable") == bool_attr(b, "nullable"),
    }
}
fn fact_description(fact: &str, v: &J) -> Text {
    match fact {
        "type" => string_attr(v, "dataType")
            .map(Text::source)
            .unwrap_or_else(|| "unknown".into()),
        "cardinality" => string_attr(v, "cardinality")
            .map(Text::source)
            .unwrap_or_else(|| "unknown".into()),
        _ => {
            let key = if fact == "presence" {
                "presenceRequired"
            } else {
                "nullable"
            };
            line!(
                key,
                "=",
                bool_attr(v, key)
                    .map(|b| b.to_string())
                    .unwrap_or_else(|| "undefined".into())
            )
        }
    }
}
struct Output {
    entities: Vec<J>,
    mappings: Vec<J>,
    authorities: Vec<J>,
    issues: Vec<J>,
    configured: Vec<J>,
    configured_seen: HashSet<String>,
    bindings: Vec<Value>,
    undefined: Vec<Value>,
    provenance: J,
}
impl Output {
    fn issue(
        &mut self,
        severity: &str,
        code: &str,
        message: Text,
        config: &J,
        subject: (Option<&str>, Option<&str>, Option<&str>, bool),
    ) {
        let (source_id, target_id, fact, missing_ids) = subject;
        let mut fields = vec![
            ("severity".to_owned(), literal(severity)),
            ("code".to_owned(), literal(code)),
            ("message".to_owned(), text(&message)),
            (
                "correspondenceId".to_owned(),
                config.get("id").expect("checked configuration id").clone(),
            ),
        ];
        let index = self.issues.len();
        for (offset, (key, id)) in [("sourceId", source_id), ("targetId", target_id)]
            .into_iter()
            .enumerate()
        {
            if let Some(id) = id {
                fields.push((key.to_owned(), source(id)));
            } else if missing_ids {
                self.undefined
                    .push(json!({"path":["issues",index,key],"position":4+offset}));
            }
        }
        if let Some(fact) = fact {
            fields.push(("fact".to_owned(), source(fact)));
        }
        self.issues.push(J::Object(fields));
    }
    fn configured(&mut self, id: &str) {
        if self.configured_seen.insert(id.to_owned()) {
            self.configured.push(source(id));
        }
    }
    fn binding(&mut self, target: Value, source: Value) {
        self.bindings.push(json!({"target":target,"source":source}));
    }
    fn mapping(
        &mut self,
        id: J,
        relation: J,
        a: &str,
        b: &str,
        attributes: J,
        transform: Option<&J>,
    ) {
        let index = self.mappings.len();
        let mut result = vec![
            ("id".to_owned(), id),
            ("relation".to_owned(), relation),
            ("sources".to_owned(), J::Array(vec![source(a)])),
            ("targets".to_owned(), J::Array(vec![source(b)])),
            ("cardinality".to_owned(), literal("one-to-one")),
            ("lossiness".to_owned(), literal("unknown")),
            ("attributes".to_owned(), attributes),
        ];
        if truthy(transform) {
            result.push((
                "transform".to_owned(),
                object(vec![
                    ("adapter", literal("declaration")),
                    ("version", literal("1.0.0")),
                    ("entrypoint", transform.expect("truthy transform").clone()),
                    ("deterministic", J::Bool(true)),
                ]),
            ));
        } else {
            self.undefined
                .push(json!({"path":["document","mappings",index,"transform"],"position":7}));
        }
        result.push(("provenance".to_owned(), self.provenance.clone()));
        self.mappings.push(J::Object(result));
    }
}
struct Discovery<'a> {
    structures: HashMap<(String, String, String), Vec<&'a J>>,
    children: HashMap<&'a str, Vec<&'a J>>,
}
impl<'a> Discovery<'a> {
    fn new(entities: &'a [J]) -> Self {
        let mut result = Self {
            structures: HashMap::new(),
            children: HashMap::new(),
        };
        for v in entities {
            if let (Some(a), Some(b), Some(c)) = (
                string_attr(v, "sourceId"),
                string_attr(v, "name"),
                string_attr(v, "structureKind"),
            ) {
                result
                    .structures
                    .entry((a.to_owned(), b.to_owned(), c.to_owned()))
                    .or_default()
                    .push(v);
            }
            if let Some(parent) = string_attr(v, "structureId") {
                result.children.entry(parent).or_default().push(v);
            }
        }
        result
    }
    fn resolve(&self, reference: &J) -> Result<&[&'a J], LegacyCorrespondenceError> {
        let key = (
            string(reference, "sourceId")?.to_owned(),
            string(reference, "name")?.to_owned(),
            string(reference, "kind")?.to_owned(),
        );
        Ok(self.structures.get(&key).map(Vec::as_slice).unwrap_or(&[]))
    }
    fn children(&self, id: &str) -> &[&'a J] {
        self.children.get(id).map(Vec::as_slice).unwrap_or(&[])
    }
}
fn coverage(
    output: &mut Output,
    side: &str,
    children: &[&J],
    mapped: &HashSet<&str>,
    ignored: &[J],
    required: bool,
    config: &J,
) -> Result<(), LegacyCorrespondenceError> {
    let mut names = Vec::new();
    let mut seen = HashSet::new();
    for &v in children {
        if bool_attr(v, "relation") != Some(true)
            && let Some(name) = string_attr(v, "name")
            && seen.insert(name)
        {
            names.push(name);
        }
    }
    let ignored = string_names(ignored)?;
    let mut ignored_set = HashSet::new();
    for name in ignored {
        if ignored_set.insert(name) && !seen.contains(name) {
            output.issue(
                "warning",
                "STALE_COVERAGE_IGNORE",
                line!(side, " ignore ", Text::source(name), " no longer resolves"),
                config,
                (None, None, Some("coverage"), false),
            );
        }
    }
    if required {
        for name in names {
            if !mapped.contains(name) && !ignored_set.contains(name) {
                output.issue(
                    "error",
                    "UNMAPPED_FIELD",
                    line!(
                        side,
                        " field ",
                        Text::source(name),
                        " is neither mapped nor explicitly ignored"
                    ),
                    config,
                    (None, None, Some("coverage"), false),
                );
            }
        }
    }
    Ok(())
}
fn process_enum(
    output: &mut Output,
    discovery: &Discovery<'_>,
    namespace: &Text,
    config: &J,
    a: &J,
    b: &J,
) -> Result<(), LegacyCorrespondenceError> {
    let a_values = by_name(discovery.children(string(a, "id")?));
    let b_values = by_name(discovery.children(string(b, "id")?));
    let a_by_name: HashMap<_, _> = a_values.iter().copied().collect();
    let b_by_name: HashMap<_, _> = b_values.iter().copied().collect();
    let enum_values = config.get("enumValues");
    let a_allowed = string_names(optional_array(
        enum_values.and_then(|v| v.get("allowSourceOnly")),
        "allowSourceOnly",
    )?)?
    .into_iter()
    .collect::<HashSet<_>>();
    let b_allowed = string_names(optional_array(
        enum_values.and_then(|v| v.get("allowTargetOnly")),
        "allowTargetOnly",
    )?)?
    .into_iter()
    .collect::<HashSet<_>>();
    let config_id = Text::source(string(config, "id")?);
    for (name, a_value) in a_values {
        if let Some(b_value) = b_by_name.get(name) {
            let id = make_id(
                namespace,
                "mapping",
                &line!(&config_id, ":enum-value:", Text::source(name)),
            )?;
            output.mapping(
                id,
                fields(config.get("relation"), "core:derives_from"),
                string(a_value, "id")?,
                string(b_value, "id")?,
                object(vec![
                    ("correspondenceId", config.get("id").expect("id").clone()),
                    ("value", source(name)),
                ]),
                None,
            );
        } else {
            let allowed = a_allowed.contains(name);
            output.issue(
                if allowed { "info" } else { "error" },
                if allowed {
                    "WAIVED_ENUM_DIFFERENCE"
                } else {
                    "ENUM_VALUE_DRIFT"
                },
                line!(
                    Text::source(name),
                    " exists only in source enum ",
                    js_text(config.get("source").and_then(|v| v.get("name")))
                ),
                config,
                (
                    Some(string(a_value, "id")?),
                    None,
                    Some("enum-values"),
                    false,
                ),
            );
        }
    }
    for (name, b_value) in b_values {
        if a_by_name.contains_key(name) {
            continue;
        }
        let allowed = b_allowed.contains(name);
        output.issue(
            if allowed { "info" } else { "error" },
            if allowed {
                "WAIVED_ENUM_DIFFERENCE"
            } else {
                "ENUM_VALUE_DRIFT"
            },
            line!(
                Text::source(name),
                " exists only in target enum ",
                js_text(config.get("target").and_then(|v| v.get("name")))
            ),
            config,
            (
                None,
                Some(string(b_value, "id")?),
                Some("enum-values"),
                false,
            ),
        );
    }
    Ok(())
}
pub fn legacy_correspondence_request(
    request: LegacyCorrespondenceRequest,
) -> Result<Box<RawValue>, LegacyCorrespondenceError> {
    let data = Data::parse(&request.input, COMPATIBILITY_JSON_LIMITS)
        .map_err(|e| failure(e.to_string()))?;
    let input = data.value();
    let namespace = Text::source(string(input, "namespace")?);
    let document_id = Text::source(string(input, "documentId")?);
    let config_revision = input
        .get("configRevision")
        .ok_or_else(|| failure("Missing configRevision"))?;
    let discovered = input
        .get("discovered")
        .ok_or_else(|| failure("Missing discovered graph"))?;
    let configurations = array(input, "configurations")?;
    let discovery = Discovery::new(array(discovered, "entities")?);
    let provenance = object(vec![
        ("status", literal("declared")),
        ("assertedBy", literal("metamap-config")),
        ("sourceRevision", config_revision.clone()),
    ]);
    let mut output = Output {
        entities: Vec::new(),
        mappings: Vec::new(),
        authorities: Vec::new(),
        issues: Vec::new(),
        configured: Vec::new(),
        configured_seen: HashSet::new(),
        bindings: Vec::new(),
        undefined: Vec::new(),
        provenance,
    };
    for (ci, config) in configurations.iter().enumerate() {
        let config_id = Text::source(string(config, "id")?);
        let a_ref = config
            .get("source")
            .ok_or_else(|| failure("Missing source reference"))?;
        let b_ref = config
            .get("target")
            .ok_or_else(|| failure("Missing target reference"))?;
        let a_matches = discovery.resolve(a_ref)?;
        let b_matches = discovery.resolve(b_ref)?;
        if a_matches.len() != 1 || b_matches.len() != 1 {
            for (side, reference, matches) in
                [("SOURCE", a_ref, a_matches), ("TARGET", b_ref, b_matches)]
            {
                if matches.len() != 1 {
                    let code = format!(
                        "{}_CORRESPONDENCE_{side}",
                        if matches.is_empty() {
                            "MISSING"
                        } else {
                            "AMBIGUOUS"
                        }
                    );
                    output.issue(
                        "error",
                        &code,
                        line!(
                            js_text(reference.get("sourceId")),
                            ":",
                            js_text(reference.get("name")),
                            " resolved ",
                            matches.len(),
                            " times"
                        ),
                        config,
                        (None, None, None, false),
                    );
                }
            }
            continue;
        }
        let a = a_matches[0];
        let b = b_matches[0];
        let a_id = string(a, "id")?;
        let b_id = string(b, "id")?;
        output.configured(a_id);
        output.configured(b_id);
        let concept_id = make_id(&namespace, "concept", &config_id)?;
        output.entities.push(object(vec![
            ("id", concept_id.clone()),
            ("kind", literal("concept")),
            ("label", config.get("id").expect("id").clone()),
            (
                "attributes",
                object(vec![
                    ("correspondenceId", config.get("id").expect("id").clone()),
                    ("sourceStructure", source(a_id)),
                    ("targetStructure", source(b_id)),
                ]),
            ),
            ("provenance", output.provenance.clone()),
        ]));
        output.mappings.push(object(vec![
            (
                "id",
                make_id(
                    &namespace,
                    "mapping",
                    &line!(&config_id, ":implementations"),
                )?,
            ),
            ("relation", literal("core:implements")),
            ("sources", J::Array(vec![concept_id.clone()])),
            ("targets", J::Array(vec![source(a_id), source(b_id)])),
            ("cardinality", literal("one-to-many")),
            ("lossiness", literal("unknown")),
            ("provenance", output.provenance.clone()),
        ]));
        output.mapping(
            make_id(&namespace, "mapping", &line!(&config_id, ":structure"))?,
            fields(config.get("relation"), "core:derives_from"),
            a_id,
            b_id,
            object(vec![(
                "correspondenceId",
                config.get("id").expect("id").clone(),
            )]),
            None,
        );
        if truthy(config.get("authority")) {
            let authority = config.get("authority").expect("truthy");
            let index = output.authorities.len();
            let mut fields = vec![
                (
                    "id".to_owned(),
                    make_id(&namespace, "authority", &config_id)?,
                ),
                ("concept".to_owned(), concept_id),
                (
                    "source".to_owned(),
                    source(
                        if authority.get("side").and_then(J::string) == Some("source") {
                            a_id
                        } else {
                            b_id
                        },
                    ),
                ),
            ];
            if let Some(facts) = authority.get("facts") {
                fields.push(("facts".to_owned(), facts.clone()));
                output.binding(
                    json!(["document", "authorities", index, "facts"]),
                    json!(["configurations", ci, "authority", "facts"]),
                );
            } else {
                output
                    .undefined
                    .push(json!({"path":["document","authorities",index,"facts"],"position":3}));
            }
            fields.push(("mode".to_owned(), literal("canonical")));
            fields.push(("provenance".to_owned(), output.provenance.clone()));
            output.authorities.push(J::Object(fields));
        }
        if a_ref.get("kind").and_then(J::string) == Some("enum")
            && b_ref.get("kind").and_then(J::string) == Some("enum")
        {
            process_enum(&mut output, &discovery, &namespace, config, a, b)?;
        }
        if !truthy(config.get("fields")) {
            continue;
        }
        let field_config = config.get("fields").expect("truthy");
        let a_fields = discovery.children(a_id);
        let b_fields = discovery.children(b_id);
        let a_names = by_name(a_fields).into_iter().collect::<HashMap<_, _>>();
        let b_names = by_name(b_fields).into_iter().collect::<HashMap<_, _>>();
        let mut mapped_a = HashSet::new();
        let mut mapped_b = HashSet::new();
        for (pi, pair) in array(field_config, "pairs")?.iter().enumerate() {
            let a_name = string(pair, "source")?;
            let b_name = string(pair, "target")?;
            let a_field = a_names.get(a_name).copied();
            let b_field = b_names.get(b_name).copied();
            let (Some(a_field), Some(b_field)) = (a_field, b_field) else {
                output.issue(
                    "error",
                    "MISSING_MAPPED_FIELD",
                    line!(
                        Text::source(a_name),
                        " -> ",
                        Text::source(b_name),
                        " resolves as ",
                        if a_field.is_some() {
                            "source"
                        } else {
                            "missing source"
                        },
                        " / ",
                        if b_field.is_some() {
                            "target"
                        } else {
                            "missing target"
                        }
                    ),
                    config,
                    (
                        a_field.map(|v| string(v, "id")).transpose()?,
                        b_field.map(|v| string(v, "id")).transpose()?,
                        None,
                        true,
                    ),
                );
                continue;
            };
            mapped_a.insert(a_name);
            mapped_b.insert(b_name);
            let a_field_id = string(a_field, "id")?;
            let b_field_id = string(b_field, "id")?;
            let default = J::Array(
                ["type", "presence", "nullability", "cardinality"]
                    .map(literal)
                    .to_vec(),
            );
            let compared = nonnull(pair.get("compare")).unwrap_or(&default);
            let compared_names = string_names(
                compared
                    .array()
                    .ok_or_else(|| failure("Read-only legacy compare requires an array"))?,
            )?;
            let allowed_value = nonnull(pair.get("allowDifferences"))
                .cloned()
                .unwrap_or_else(|| J::Array(vec![]));
            let allowed =
                string_names(allowed_value.array().ok_or_else(|| {
                    failure("Read-only legacy allowDifferences requires an array")
                })?)?
                .into_iter()
                .collect::<HashSet<_>>();
            for fact in compared_names {
                if fact_matches(fact, a_field, b_field) {
                    continue;
                }
                let waived = allowed.contains(fact);
                let mut message = line!(
                    Text::source(a_name),
                    " -> ",
                    Text::source(b_name),
                    " differs for ",
                    Text::source(fact),
                    ": ",
                    fact_description(fact, a_field),
                    " vs ",
                    fact_description(fact, b_field)
                );
                if truthy(pair.get("note")) {
                    message = Text::join(
                        &[message, " (".into(), js_text(pair.get("note")), ")".into()],
                        "",
                    );
                }
                output.issue(
                    if waived { "info" } else { "error" },
                    if waived {
                        "WAIVED_FIELD_DIFFERENCE"
                    } else {
                        "FIELD_DRIFT"
                    },
                    message,
                    config,
                    (Some(a_field_id), Some(b_field_id), Some(fact), false),
                );
            }
            let mapping_index = output.mappings.len();
            let id = make_id(
                &namespace,
                "mapping",
                &line!(
                    &config_id,
                    ":field:",
                    Text::source(a_name),
                    ":",
                    Text::source(b_name)
                ),
            )?;
            let attributes = object(vec![
                ("correspondenceId", config.get("id").expect("id").clone()),
                ("comparedFacts", compared.clone()),
                ("allowedDifferences", allowed_value),
                ("note", fields(pair.get("note"), "")),
            ]);
            output.mapping(
                id,
                fields(config.get("relation"), "core:derives_from"),
                a_field_id,
                b_field_id,
                attributes,
                pair.get("transform"),
            );
            for (field, key) in [
                ("comparedFacts", "compare"),
                ("allowedDifferences", "allowDifferences"),
            ] {
                if nonnull(pair.get(key)).is_some() {
                    output.binding(
                        json!(["document", "mappings", mapping_index, "attributes", field]),
                        json!(["configurations", ci, "fields", "pairs", pi, key]),
                    );
                }
            }
        }
        coverage(
            &mut output,
            "source",
            a_fields,
            &mapped_a,
            optional_array(field_config.get("ignoreSource"), "ignoreSource")?,
            truthy(field_config.get("requireSourceCoverage")),
            config,
        )?;
        coverage(
            &mut output,
            "target",
            b_fields,
            &mapped_b,
            optional_array(field_config.get("ignoreTarget"), "ignoreTarget")?,
            truthy(field_config.get("requireTargetCoverage")),
            config,
        )?;
    }
    let document = object(vec![
        ("schemaVersion", literal("2.0.0")),
        ("id", make_id(&namespace, "metamap-shard", &document_id)?),
        ("namespace", text(&namespace)),
        ("label", literal("Declared structural correspondences")),
        ("revision", config_revision.clone()),
        (
            "relationPacks",
            J::Array(vec![object(vec![
                ("id", literal("urn:metamap:relation-pack:core")),
                ("version", literal("1.0.0")),
            ])]),
        ),
        ("entities", J::Array(output.entities)),
        ("mappings", J::Array(output.mappings)),
        ("authorities", J::Array(output.authorities)),
        (
            "metadata",
            object(vec![
                ("source", literal("metamap-config")),
                (
                    "correspondenceCount",
                    J::Number(configurations.len() as f64),
                ),
            ]),
        ),
    ]);
    #[derive(Serialize)]
    #[serde(rename_all = "camelCase")]
    struct Response {
        document: Box<RawValue>,
        issues: Box<RawValue>,
        configured_structure_ids: Box<RawValue>,
        provenance: Box<RawValue>,
        bindings: Vec<Value>,
        undefined_properties: Vec<Value>,
    }
    let raw = |v: &J| Data::json_raw(v).map_err(|e| failure(e.to_string()));
    let response = Response {
        document: raw(&document)?,
        issues: raw(&J::Array(output.issues))?,
        configured_structure_ids: raw(&J::Array(output.configured))?,
        provenance: raw(&output.provenance)?,
        bindings: output.bindings,
        undefined_properties: output.undefined,
    };
    RawValue::from_string(serde_json::to_string(&response).map_err(|e| failure(e.to_string()))?)
        .map_err(|e| failure(e.to_string()))
}
