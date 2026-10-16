//! Finite, acyclic JSON Schema DTO subset, compiled to source expressions.
use crate::js_string;
use patamaps_core::{CheckError, Issue};
use serde_json::{Map, Value};
use std::collections::{BTreeMap, BTreeSet};

const DIALECT: &str = "https://json-schema.org/draft/2020-12/schema";
const SAFE: f64 = 9_007_199_254_740_991.0;

#[derive(Debug)]
pub(super) enum Schema {
    Any,
    Never,
    Null,
    Boolean,
    String {
        min: u64,
        max: Option<u64>,
        values: Option<Vec<String>>,
        uuid: bool,
        unsigned_decimal: bool,
    },
    Number {
        integer: bool,
        min: Option<f64>,
        max: Option<f64>,
    },
    Array {
        item: Box<Schema>,
        min: u64,
        max: Option<u64>,
    },
    Object {
        fields: BTreeMap<String, Schema>,
        required: BTreeSet<String>,
        extra: Box<Schema>,
    },
    Union {
        variants: Vec<Schema>,
        exactly_one: bool,
    },
}

struct Parser<'a> {
    root: &'a Value,
    subject: &'a str,
    nodes: usize,
    active: BTreeSet<String>,
    validated_definitions: BTreeSet<String>,
    transport: bool,
}

impl Parser<'_> {
    fn error(&self) -> CheckError {
        CheckError(vec![Issue::error(
            "HTTP_JSON_SCHEMA_UNSUPPORTED",
            "Expected the finite JSON DTO schema profile; unknown keywords, remote/recursive references and unsupported formats refuse",
            self.subject,
        )])
    }

    fn allowed(
        &self,
        map: &Map<String, Value>,
        keys: &[&str],
        top: bool,
    ) -> Result<(), CheckError> {
        if map.keys().any(|key| {
            !keys.contains(&key.as_str())
                && !["title", "description", "default", "examples"].contains(&key.as_str())
                && !(top && ["$schema", "$defs"].contains(&key.as_str()))
        }) {
            return Err(self.error());
        }
        if map.get("title").is_some_and(|v| !v.is_string())
            || map.get("description").is_some_and(|v| !v.is_string())
            || map.get("examples").is_some_and(|v| !v.is_array())
        {
            return Err(self.error());
        }
        Ok(())
    }

    fn count(
        &self,
        map: &Map<String, Value>,
        key: &str,
        default: Option<u64>,
    ) -> Result<Option<u64>, CheckError> {
        match map.get(key) {
            None => Ok(default),
            Some(value) => value
                .as_f64()
                .filter(|v| v.is_finite() && *v >= 0.0 && *v <= 1_000_000.0 && v.fract() == 0.0)
                .map(|v| Some(v as u64))
                .ok_or_else(|| self.error()),
        }
    }

    fn bound(&self, map: &Map<String, Value>, key: &str) -> Result<Option<f64>, CheckError> {
        match map.get(key) {
            None => Ok(None),
            Some(value) => value
                .as_f64()
                .filter(|v| v.is_finite())
                .map(Some)
                .ok_or_else(|| self.error()),
        }
    }

    fn node(&mut self, value: &Value, top: bool, depth: usize) -> Result<Schema, CheckError> {
        self.nodes += 1;
        if self.nodes > 2048 || depth > 32 {
            return Err(self.error());
        }
        if let Some(b) = value.as_bool() {
            return Ok(if b { Schema::Any } else { Schema::Never });
        }
        let map = value.as_object().ok_or_else(|| self.error())?;
        if let Some(reference) = map.get("$ref") {
            self.allowed(map, &["$ref"], top)?;
            let reference = reference.as_str().ok_or_else(|| self.error())?;
            let name = reference
                .strip_prefix("#/$defs/")
                .ok_or_else(|| self.error())?;
            if name.is_empty()
                || name.len() > 128
                || !name
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b"_-".contains(&b))
                || !self.active.insert(name.into())
            {
                return Err(self.error());
            }
            let target = self
                .root
                .get("$defs")
                .and_then(|d| d.get(name))
                .ok_or_else(|| self.error())?;
            let result = self.node(target, false, depth + 1);
            self.active.remove(name);
            if result.is_ok() {
                self.validated_definitions.insert(name.into());
            }
            return result;
        }
        for key in ["oneOf", "anyOf"] {
            if let Some(value) = map.get(key) {
                self.allowed(map, &[key], top)?;
                let variants = value
                    .as_array()
                    .filter(|a| !a.is_empty() && a.len() <= 64)
                    .ok_or_else(|| self.error())?;
                let variants = variants
                    .iter()
                    .map(|v| self.node(v, false, depth + 1))
                    .collect::<Result<Vec<_>, _>>()?;
                return Ok(Schema::Union {
                    variants,
                    exactly_one: key == "oneOf",
                });
            }
        }
        if let Some(kinds) = map.get("type").and_then(Value::as_array) {
            if kinds.len() != 2 || kinds.iter().filter(|v| v.as_str() == Some("null")).count() != 1
            {
                return Err(self.error());
            }
            let kind = kinds
                .iter()
                .find(|v| v.as_str() != Some("null"))
                .ok_or_else(|| self.error())?;
            if !kind.is_string() {
                return Err(self.error());
            }
            let mut branch = value.clone();
            branch["type"] = kind.clone();
            return Ok(Schema::Union {
                variants: vec![Schema::Null, self.node(&branch, top, depth + 1)?],
                exactly_one: false,
            });
        }
        let kind = map.get("type").and_then(Value::as_str);
        match kind {
            Some("object") => {
                self.allowed(
                    map,
                    &["type", "properties", "required", "additionalProperties"],
                    top,
                )?;
                let empty = Map::new();
                let properties = match map.get("properties") {
                    None => &empty,
                    Some(v) => v.as_object().ok_or_else(|| self.error())?,
                };
                if properties.len() > 128
                    || properties.keys().any(|k| k.is_empty() || k.len() > 128)
                {
                    return Err(self.error());
                }
                let required: Vec<String> = match map.get("required") {
                    None => Vec::new(),
                    Some(v) => v
                        .as_array()
                        .ok_or_else(|| self.error())?
                        .iter()
                        .map(|v| v.as_str().map(str::to_owned).ok_or_else(|| self.error()))
                        .collect::<Result<_, _>>()?,
                };
                let set: BTreeSet<_> = required.iter().cloned().collect();
                if set.len() != required.len() || set.iter().any(|k| !properties.contains_key(k)) {
                    return Err(self.error());
                }
                let fields = properties
                    .iter()
                    .map(|(k, v)| Ok((k.clone(), self.node(v, false, depth + 1)?)))
                    .collect::<Result<_, CheckError>>()?;
                let extra = match map.get("additionalProperties") {
                    None => Schema::Any,
                    Some(v) => self.node(v, false, depth + 1)?,
                };
                Ok(Schema::Object {
                    fields,
                    required: set,
                    extra: Box::new(extra),
                })
            }
            Some("array") => {
                self.allowed(map, &["type", "items", "minItems", "maxItems"], top)?;
                let min = self.count(map, "minItems", Some(0))?.expect("default");
                let max = self.count(map, "maxItems", None)?;
                if max.is_some_and(|v| v < min) {
                    return Err(self.error());
                }
                let item = match map.get("items") {
                    None => Schema::Any,
                    Some(v) => self.node(v, false, depth + 1)?,
                };
                Ok(Schema::Array {
                    item: Box::new(item),
                    min,
                    max,
                })
            }
            Some("string") => {
                self.allowed(
                    map,
                    &[
                        "type",
                        "minLength",
                        "maxLength",
                        "enum",
                        "const",
                        "format",
                        "pattern",
                    ],
                    top,
                )?;
                let min = self.count(map, "minLength", Some(0))?.expect("default");
                let max = self.count(map, "maxLength", None)?;
                if max.is_some_and(|v| v < min)
                    || (map.contains_key("enum") && map.contains_key("const"))
                {
                    return Err(self.error());
                }
                let values = if let Some(value) = map.get("const") {
                    Some(vec![value.as_str().ok_or_else(|| self.error())?.into()])
                } else if let Some(value) = map.get("enum") {
                    let values = value
                        .as_array()
                        .filter(|v| !v.is_empty() && v.len() <= 128)
                        .ok_or_else(|| self.error())?
                        .iter()
                        .map(|v| v.as_str().map(str::to_owned).ok_or_else(|| self.error()))
                        .collect::<Result<Vec<_>, _>>()?;
                    if values.iter().collect::<BTreeSet<_>>().len() != values.len() {
                        return Err(self.error());
                    }
                    Some(values)
                } else {
                    None
                };
                let uuid = match map.get("format") {
                    None => false,
                    Some(v) if self.transport && v.as_str() == Some("uuid") => true,
                    _ => return Err(self.error()),
                };
                let unsigned_decimal = match map.get("pattern") {
                    None => false,
                    Some(v) if self.transport && v.as_str() == Some("^(0|[1-9][0-9]*)$") => true,
                    _ => return Err(self.error()),
                };
                Ok(Schema::String {
                    min,
                    max,
                    values,
                    uuid,
                    unsigned_decimal,
                })
            }
            Some("number" | "integer") => {
                self.allowed(map, &["type", "minimum", "maximum", "format"], top)?;
                let integer = kind == Some("integer");
                let mut min = self.bound(map, "minimum")?;
                let mut max = self.bound(map, "maximum")?;
                if integer {
                    min = Some(min.unwrap_or(-SAFE).max(-SAFE));
                    max = Some(max.unwrap_or(SAFE).min(SAFE));
                }
                if let Some(format) = map.get("format") {
                    if !integer {
                        return Err(self.error());
                    }
                    let (lo, hi) = match format.as_str() {
                        Some("uint8") => (0.0, 255.0),
                        Some("uint16") => (0.0, 65535.0),
                        Some("uint32") => (0.0, 4294967295.0),
                        Some("int8") => (-128.0, 127.0),
                        Some("int16") => (-32768.0, 32767.0),
                        Some("int32") => (-2147483648.0, 2147483647.0),
                        // Explicit transport interoperability subset, never a claim of full u64/i64.
                        Some("uint64") if self.transport => (0.0, SAFE),
                        Some("int64") if self.transport => (-SAFE, SAFE),
                        _ => return Err(self.error()),
                    };
                    min = Some(min.unwrap_or(lo).max(lo));
                    max = Some(max.unwrap_or(hi).min(hi));
                }
                if min.zip(max).is_some_and(|(lo, hi)| lo > hi) {
                    return Err(self.error());
                }
                Ok(Schema::Number { integer, min, max })
            }
            Some("boolean") => {
                self.allowed(map, &["type"], top)?;
                Ok(Schema::Boolean)
            }
            Some("null") => {
                self.allowed(map, &["type"], top)?;
                Ok(Schema::Null)
            }
            None => {
                self.allowed(map, &[], top)?;
                Ok(Schema::Any)
            }
            _ => Err(self.error()),
        }
    }
}

pub(super) fn parse(value: &Value, subject: &str) -> Result<Schema, CheckError> {
    parse_profile(value, subject, false)
}

pub(super) fn parse_transport(value: &Value, subject: &str) -> Result<Schema, CheckError> {
    parse_profile(value, subject, true)
}

fn parse_profile(value: &Value, subject: &str, transport: bool) -> Result<Schema, CheckError> {
    let mut parser = Parser {
        root: value,
        subject,
        nodes: 0,
        active: BTreeSet::new(),
        validated_definitions: BTreeSet::new(),
        transport,
    };
    if value.get("$schema").and_then(Value::as_str) != Some(DIALECT)
        || patamaps_contracts::canonical_bytes(value)?.len() > 262144
    {
        return Err(parser.error());
    }
    let result = parser.node(value, true, 0)?;
    if let Some(defs) = value.get("$defs") {
        let defs = defs
            .as_object()
            .filter(|v| v.len() <= 128)
            .ok_or_else(|| parser.error())?;
        for (name, definition) in defs {
            // Root expansion already checked every assertion in referenced defs.
            // Do not charge the same independent validation a second time. Root
            // references still expand normally and retain the2048 visitor bound.
            if !parser.validated_definitions.contains(name) {
                parser.node(definition, false, 0)?;
                parser.validated_definitions.insert(name.clone());
            }
        }
    }
    Ok(result)
}

impl Schema {
    pub(super) fn rust(&self) -> String {
        match self {
            Self::Any => "true".into(),
            Self::Never => "false".into(),
            Self::Null => "value.is_null()".into(),
            Self::Boolean => "value.is_boolean()".into(),
            Self::String {
                min,
                max,
                values,
                uuid,
                unsigned_decimal,
            } => {
                let mut terms = Vec::new();
                if *min > 0 {
                    terms.push(format!("text.chars().count() >= {min}"));
                }
                if let Some(max) = max {
                    terms.push(format!("text.chars().count() <= {max}"));
                }
                if let Some(values) = values {
                    terms.push(format!(
                        "[{}].contains(&text)",
                        values
                            .iter()
                            .map(|s| format!("{s:?}"))
                            .collect::<Vec<_>>()
                            .join(",")
                    ));
                }
                if *uuid {
                    terms.push("text.len() == 36 && text.bytes().enumerate().all(|(i,b)| if [8,13,18,23].contains(&i) { b == b'-' } else { b.is_ascii_hexdigit() })".into());
                }
                if *unsigned_decimal {
                    terms.push("(text == \"0\" || (!text.is_empty() && matches!(text.as_bytes()[0], b'1'..=b'9') && text.bytes().all(|b| b.is_ascii_digit())))".into());
                }
                format!(
                    "value.as_str().is_some_and(|text| {{ let _ = text; {} }})",
                    if terms.is_empty() {
                        "true".into()
                    } else {
                        terms.join(" && ")
                    }
                )
            }
            Self::Number { integer, min, max } => {
                let mut terms = vec!["number.is_finite()".to_owned()];
                if *integer {
                    terms.push("number.fract() == 0.0".into());
                }
                if let Some(min) = min {
                    terms.push(format!("number >= {min:?}"));
                }
                if let Some(max) = max {
                    terms.push(format!("number <= {max:?}"));
                }
                format!(
                    "value.as_f64().is_some_and(|number| {})",
                    terms.join(" && ")
                )
            }
            Self::Array { item, min, max } => {
                let mut terms = Vec::new();
                if *min > 0 {
                    terms.push(format!("array.len() >= {min}"));
                }
                if let Some(max) = max {
                    terms.push(format!("array.len() <= {max}"));
                }
                terms.push(format!(
                    "array.iter().all(|value| {{ let _ = value; {} }})",
                    item.rust()
                ));
                format!(
                    "value.as_array().is_some_and(|array| {})",
                    terms.join(" && ")
                )
            }
            Self::Object {
                fields,
                required,
                extra,
            } => {
                let mut terms = required
                    .iter()
                    .map(|k| format!("object.contains_key({k:?})"))
                    .collect::<Vec<_>>();
                for (k, schema) in fields {
                    terms.push(format!(
                        "object.get({k:?}).is_none_or(|value| {})",
                        schema.rust()
                    ));
                }
                let known = fields
                    .keys()
                    .map(|k| format!("{k:?}"))
                    .collect::<Vec<_>>()
                    .join(",");
                terms.push(format!("object.iter().all(|(key,value)| {{ let _ = value; let known: &[&str] = &[{known}]; known.contains(&key.as_str()) || ({}) }})",extra.rust()));
                format!(
                    "value.as_object().is_some_and(|object| {})",
                    terms.join(" && ")
                )
            }
            Self::Union {
                variants,
                exactly_one,
            } => {
                let terms = variants
                    .iter()
                    .map(|v| format!("({})", v.rust()))
                    .collect::<Vec<_>>();
                if *exactly_one {
                    format!(
                        "[{}].into_iter().filter(|matched| *matched).count() == 1",
                        terms.join(",")
                    )
                } else {
                    format!("({})", terms.join(" || "))
                }
            }
        }
    }

    pub(super) fn normalize_rust(&self) -> String {
        match self {
            Self::Number { integer: true, .. } => {
                "if let Some(n) = value.as_f64() { *value = serde_json::Value::from(n as i64); }\n"
                    .into()
            }
            Self::Array { item, .. } => {
                let code = item.normalize_rust();
                if code.is_empty() {
                    String::new()
                } else {
                    format!(
                        "if let Some(values) = value.as_array_mut() {{ for value in values {{ {code} }} }}\n"
                    )
                }
            }
            Self::Object { fields, extra, .. } => {
                let mut code = String::new();
                for (key, schema) in fields {
                    let inner = schema.normalize_rust();
                    if !inner.is_empty() {
                        code.push_str(&format!(
                            "if let Some(value) = object.get_mut({key:?}) {{ {inner} }}\n"
                        ));
                    }
                }
                let inner = extra.normalize_rust();
                if !inner.is_empty() {
                    let names = fields
                        .keys()
                        .map(|k| format!("{k:?}"))
                        .collect::<Vec<_>>()
                        .join(",");
                    code.push_str(&format!("for (key,value) in object.iter_mut() {{ let known: &[&str] = &[{names}]; if !known.contains(&key.as_str()) {{ {inner} }} }}\n"));
                }
                if code.is_empty() {
                    code
                } else {
                    format!("if let Some(object) = value.as_object_mut() {{ {code} }}\n")
                }
            }
            Self::Union { variants, .. } => {
                if variants.iter().all(|v| v.normalize_rust().is_empty()) {
                    return String::new();
                }
                variants
                    .iter()
                    .map(|v| format!("if {} {{ {} }}", v.rust(), v.normalize_rust()))
                    .collect::<Vec<_>>()
                    .join(" else ")
            }
            _ => String::new(),
        }
    }

    pub(super) fn ts(&self) -> String {
        match self {
            Self::Any => "unknown".into(),
            Self::Never => "never".into(),
            Self::Null => "null".into(),
            Self::Boolean => "boolean".into(),
            Self::String { values, .. } => values
                .as_ref()
                .map(|v| {
                    v.iter()
                        .map(|s| js_string(s))
                        .collect::<Vec<_>>()
                        .join(" | ")
                })
                .unwrap_or_else(|| "string".into()),
            Self::Number { .. } => "number".into(),
            Self::Array { item, .. } => format!("Array<{}>", item.ts()),
            Self::Object {
                fields,
                required,
                extra,
            } => {
                // Extra-property types must also admit declared fields for a sound index signature.
                // Keep intersections with Record for open maps, with the full checked validator authoritative.
                let fields = fields
                    .iter()
                    .map(|(k, v)| {
                        format!(
                            "{}{}: {};",
                            js_string(k),
                            if required.contains(k) { "" } else { "?" },
                            v.ts()
                        )
                    })
                    .collect::<Vec<_>>()
                    .join(" ");
                let base = format!("{{ {fields} }}");
                if matches!(extra.as_ref(), Self::Never) {
                    base
                } else if matches!(extra.as_ref(), Self::Any) {
                    format!("{base} & Record<string, unknown>")
                } else {
                    let mut types = vec![extra.ts()];
                    if let Self::Object { fields, .. } = self {
                        types.extend(fields.values().map(Self::ts));
                    }
                    types.push("undefined".into());
                    format!("{base} & Record<string, {}>", types.join(" | "))
                }
            }
            Self::Union { variants, .. } => format!(
                "({})",
                variants
                    .iter()
                    .map(Self::ts)
                    .collect::<Vec<_>>()
                    .join(" | ")
            ),
        }
    }

    pub(super) fn typescript(&self) -> String {
        match self {
            Self::Any => "true".into(),
            Self::Never => "false".into(),
            Self::Null => "value === null".into(),
            Self::Boolean => "typeof value === 'boolean'".into(),
            Self::String {
                min,
                max,
                values,
                uuid,
                unsigned_decimal,
            } => {
                let mut terms = vec![
                    "typeof value === 'string'".into(),
                    "unicodeScalars(value)".into(),
                    format!("Array.from(value).length >= {min}"),
                ];
                if let Some(max) = max {
                    terms.push(format!("Array.from(value).length <= {max}"));
                }
                if let Some(values) = values {
                    terms.push(format!(
                        "([{}] as string[]).includes(value)",
                        values
                            .iter()
                            .map(|v| js_string(v))
                            .collect::<Vec<_>>()
                            .join(",")
                    ));
                }
                if *uuid {
                    terms.push("value.length === 36 && Array.from(value).every((c,i) => [8,13,18,23].includes(i) ? c === '-' : /^[0-9a-fA-F]$/.test(c))".into());
                }
                if *unsigned_decimal {
                    terms.push("(value === '0' || (value.length > 0 && /^[1-9]$/.test(value[0]) && Array.from(value).every(c => /^[0-9]$/.test(c))))".into());
                }
                terms.join(" && ")
            }
            Self::Number { integer, min, max } => {
                let mut terms = vec![
                    "typeof value === 'number'".into(),
                    "Number.isFinite(value)".into(),
                ];
                if *integer {
                    terms.push("Number.isSafeInteger(value)".into());
                }
                if let Some(min) = min {
                    terms.push(format!("value >= {min:?}"));
                }
                if let Some(max) = max {
                    terms.push(format!("value <= {max:?}"));
                }
                terms.join(" && ")
            }
            Self::Array { item, min, max } => {
                let mut terms = vec![
                    "Array.isArray(value)".into(),
                    format!("value.length >= {min}"),
                ];
                if let Some(max) = max {
                    terms.push(format!("value.length <= {max}"));
                }
                terms.push(format!(
                    "Array.from(value).every((value: unknown) => {})",
                    item.typescript()
                ));
                terms.join(" && ")
            }
            Self::Object {
                fields,
                required,
                extra,
            } => {
                let mut terms = required
                    .iter()
                    .map(|k| {
                        format!(
                            "Object.prototype.hasOwnProperty.call(object,{})",
                            js_string(k)
                        )
                    })
                    .collect::<Vec<_>>();
                for (k, schema) in fields {
                    let key = js_string(k);
                    terms.push(format!("(!Object.prototype.hasOwnProperty.call(object,{key}) || ((value: unknown) => {}) (object[{key}]))",schema.typescript()));
                }
                let known = fields
                    .keys()
                    .map(|k| js_string(k))
                    .collect::<Vec<_>>()
                    .join(",");
                terms.push(format!("Object.keys(object).every(key => ([{known}] as string[]).includes(key) || ((value: unknown) => {})(object[key]))",extra.typescript()));
                format!(
                    "typeof value === 'object' && value !== null && !Array.isArray(value) && ((object: Record<string,unknown>) => {}) (value as Record<string,unknown>)",
                    terms.join(" && ")
                )
            }
            Self::Union {
                variants,
                exactly_one,
            } => {
                let terms = variants
                    .iter()
                    .map(|v| format!("({})", v.typescript()))
                    .collect::<Vec<_>>();
                if *exactly_one {
                    format!("[{}].filter(Boolean).length === 1", terms.join(","))
                } else {
                    format!("({})", terms.join(" || "))
                }
            }
        }
    }
}

pub(super) const RUST_RUNTIME: &str = r#"
fn http_json_boundary(value: &serde_json::Value) -> bool {
    fn visit(value: &serde_json::Value, depth: usize, work: &mut usize) -> bool {
        *work += 1;
        if depth > 64 || *work > 16384 { return false; }
        match value {
            serde_json::Value::Array(values) => values.iter().all(|v| visit(v, depth + 1, work)),
            serde_json::Value::Object(values) => values.values().all(|v| visit(v, depth + 1, work)),
            serde_json::Value::Number(n) => n.as_f64().is_some_and(|n| n.is_finite() && (n.fract() != 0.0 || n.abs() <= 9007199254740991.0)),
            _ => true,
        }
    }
    visit(value, 0, &mut 0)
}

"#;

pub(super) const TYPESCRIPT_RUNTIME: &str = r#"
function httpJsonBoundary(value: unknown, maximumDepth = 64, maximumValues = 16384): boolean {
 let work = 0;
 function visit(value: unknown, depth: number): boolean {
  if (++work > maximumValues || depth > maximumDepth) return false;
  if (value === null || typeof value === 'boolean') return true;
  if (typeof value === 'number') return Number.isFinite(value) && (!Number.isInteger(value) || Number.isSafeInteger(value));
  if (typeof value === 'string') return unicodeScalars(value);
  if (typeof value !== 'object') return false;
  if (Array.isArray(value)) return Array.from(value).every(v => visit(v, depth + 1));
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) return false;
  return Object.keys(value).every(key => unicodeScalars(key) && visit((value as Record<string,unknown>)[key], depth + 1));
 }
 return visit(value, 0);
}
"#;

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    #[test]
    fn finite_dtos_and_local_refs_are_supported() {
        let schema = json!({"$schema":DIALECT,"$defs":{"Count":{"type":"integer","format":"uint32","minimum":0}},
            "type":"object","additionalProperties":false,"properties":{"counts":{"type":"array","items":{"$ref":"#/$defs/Count"}},"note":{"type":["string","null"]}},"required":["counts"]});
        let result = parse(&schema, "dto").unwrap();
        assert!(result.ts().contains("\"note\"?:"));
        assert!(result.rust().contains("4294967295.0"));
        assert!(result.typescript().contains("Number.isSafeInteger"));
    }
    #[test]
    fn unsupported_assertions_formats_cycles_and_remote_refs_refuse() {
        for schema in [
            json!({"type":"string","pattern":"x"}),
            json!({"type":"string","format":"uuid"}),
            json!({"type":"integer","format":"uint64"}),
            json!({"$ref":"https://example.invalid/schema"}),
            json!({"$defs":{"Cycle":{"$ref":"#/$defs/Cycle"}},"$ref":"#/$defs/Cycle"}),
            json!({"type":"array","uniqueItems":true}),
            json!({"type":"string","minLength":2,"maxLength":1}),
            json!({"type":"object","required":["missing"]}),
            json!({"type":"object","properties":{"x":{"type":"string"}},"required":["x","x"]}),
        ] {
            let mut schema = schema;
            schema["$schema"] = json!(DIALECT);
            assert!(parse(&schema, "unsupported").is_err(), "{schema}");
        }
    }
    #[test]
    fn transport_scalar_formats_are_explicit_and_bounded() {
        for format in ["uint64", "int64"] {
            let schema = json!({"$schema":DIALECT,"type":"integer","format":format});
            assert!(parse(&schema, "legacy").is_err());
            let Schema::Number { integer, min, max } =
                parse_transport(&schema, "transport").unwrap()
            else {
                panic!("number expected")
            };
            assert!(integer);
            assert_eq!(max, Some(SAFE));
            assert_eq!(min, Some(if format == "uint64" { 0.0 } else { -SAFE }));
        }
        for schema in [
            json!({"$schema":DIALECT,"type":"string","format":"uuid"}),
            json!({"$schema":DIALECT,"type":"string","pattern":"^(0|[1-9][0-9]*)$"}),
        ] {
            assert!(parse(&schema, "legacy").is_err());
            let node = parse_transport(&schema, "transport").unwrap();
            assert_eq!(node.ts(), "string");
            assert!(node.rust().contains("text.bytes()"));
            assert!(node.typescript().contains("Array.from(value)"));
        }
        for schema in [
            json!({"type":"string","pattern":"[0-9]+"}),
            json!({"type":"string","format":"email"}),
            json!({"type":"number","format":"uint64"}),
            json!({"type":"integer","format":"uint128"}),
            json!({"type":"integer","format":"uint64","minimum":9007199254740992_u64}),
        ] {
            let mut schema = schema;
            schema["$schema"] = json!(DIALECT);
            assert!(parse_transport(&schema, "unsupported").is_err(), "{schema}");
        }
    }
    #[test]
    fn repeated_definitions_do_not_pay_for_redundant_post_validation() {
        let shared = (0..90)
            .map(|i| (format!("field{i}"), json!({"type":"string"})))
            .collect::<Map<_, _>>();
        let schema = |count| {
            json!({"$schema":DIALECT,"$defs":{"Shared":{"type":"object","properties":shared,"additionalProperties":false}},
            "type":"object","additionalProperties":false,"properties":(0..count).map(|i|(format!("item{i}"),json!({"$ref":"#/$defs/Shared"}))).collect::<Map<_,_>>()})
        };
        // Root1+extra1+22*(ref1+object1+90fields+extra1)=2048.
        // The previous redundant Shared validation pushed this valid root over budget.
        assert!(parse(&schema(22), "at-bound").is_ok());
        assert!(parse_transport(&schema(22), "at-bound").is_ok());
        assert!(parse(&schema(23), "over-bound").is_err());
        assert!(parse_transport(&schema(23), "over-bound").is_err());
    }
    #[test]
    fn unreachable_definitions_still_validate_and_cycles_still_refuse() {
        for definitions in [
            json!({"Unused":{"type":"string","pattern":"unsupported"}}),
            json!({"UnusedA":{"$ref":"#/$defs/UnusedB"},"UnusedB":{"$ref":"#/$defs/UnusedA"}}),
            json!({"Referenced":{"type":"string"},"Unused":{"type":"integer","format":"uint128"}}),
        ] {
            let schema = json!({"$schema":DIALECT,"type":"string","$defs":definitions});
            assert!(parse(&schema, "unused").is_err());
            assert!(parse_transport(&schema, "unused").is_err());
        }
    }
    #[test]
    fn annotations_are_not_validation_and_one_of_is_exclusive() {
        let schema = json!({"$schema":DIALECT,"oneOf":[{"type":"string"},{"type":"string"}],"title":"ambiguous"});
        let parsed = parse(&schema, "ambiguous").unwrap();
        assert!(parsed.rust().contains("count() == 1"));
        assert!(parsed.typescript().contains("length === 1"));
    }
}
