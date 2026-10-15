//! Narrow, checked HTTP bindings. Cargo and HTTP remain independent evidence.
use crate::{CheckedProjection, emit_rust, emit_typescript, js_string, locator, native_target};
use patamaps_contracts::{Entity, canonical_bytes};
use patamaps_core::{CheckError, Issue};
use serde::Deserialize;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

const PROFILE: &str = "patamaps-http-object-strings-1";
const DIALECT: &str = "https://json-schema.org/draft/2020-12/schema";

fn refusal(code: &str, message: &str, subject: &str) -> CheckError {
    CheckError(vec![Issue::error(code, message, subject)])
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Endpoint {
    method: String,
    path: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Backend {
    method: String,
    path: String,
    success_status: u16,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Handler {
    profile: String,
    module_path: String,
    request_type: String,
    response_type: String,
    error_type: String,
    errors: Vec<OperationError>,
    response_schema: Value,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct OperationError {
    variant: String,
    status: u16,
    code: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ObjectSchema {
    #[serde(rename = "$schema")]
    dialect: String,
    #[serde(rename = "type")]
    kind: String,
    #[serde(rename = "additionalProperties")]
    additional_properties: bool,
    required: Vec<String>,
    properties: BTreeMap<String, StringSchema>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct StringSchema {
    #[serde(rename = "type")]
    kind: String,
    min_length: Option<u32>,
    max_length: Option<u32>,
}

fn schema(value: &Value, subject: &str) -> Result<ObjectSchema, CheckError> {
    let parsed: ObjectSchema = serde_json::from_slice(&canonical_bytes(value)?).map_err(|_| {
        refusal(
            "HTTP_SCHEMA_UNSUPPORTED",
            "Expected the declared object/string schema subset; unknown keywords refuse",
            subject,
        )
    })?;
    let required: BTreeSet<_> = parsed.required.iter().collect();
    if parsed.dialect != DIALECT
        || parsed.kind != "object"
        || parsed.additional_properties
        || parsed.properties.is_empty()
        || parsed.properties.len() > 64
        || required.len() != parsed.required.len()
        || required != parsed.properties.keys().collect()
        || parsed.properties.iter().any(|(key, field)| {
            key.is_empty()
                || key.len() > 128
                || field.kind != "string"
                || field.min_length.unwrap_or(0) > field.max_length.unwrap_or(1_000_000)
                || field.max_length.is_some_and(|v| v > 1_000_000)
        })
    {
        return Err(refusal(
            "HTTP_SCHEMA_UNSUPPORTED",
            "Only exact objects with all properties required and bounded string constraints are supported",
            subject,
        ));
    }
    Ok(parsed)
}

fn attribute<T: serde::de::DeserializeOwned>(entity: &Entity, key: &str) -> Result<T, CheckError> {
    let value = entity
        .attributes
        .as_ref()
        .and_then(|a| a.get(key))
        .ok_or_else(|| {
            refusal(
                "HTTP_CONTRACT_MISSING",
                "A required owned HTTP attribute is absent",
                &entity.id,
            )
        })?;
    serde_json::from_slice(&canonical_bytes(value)?).map_err(|_| {
        refusal(
            "HTTP_CONTRACT_UNSUPPORTED",
            "HTTP attributes must use the explicit supported shape",
            &entity.id,
        )
    })
}

fn path(value: &str) -> bool {
    value.starts_with('/')
        && value.len() <= 512
        && !value.contains("//")
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"/_-".contains(&b))
}

fn identifier(value: &str) -> bool {
    crate::language_identifier(value)
        && ![
            "self", "Self", "super", "crate", "type", "mod", "fn", "impl", "pub", "struct", "enum",
            "match", "const", "static", "let", "use", "async", "await", "move", "ref", "mut", "in",
            "where", "return", "break", "loop", "for", "while", "if", "else", "trait", "dyn",
            "unsafe", "extern", "as", "true", "false", "gen", "yield", "try",
        ]
        .contains(&value)
}

struct Binding<'a> {
    id: &'a str,
    frontend: Endpoint,
    backend: Backend,
    handler: Handler,
    module: String,
    symbol: String,
    request: ObjectSchema,
    response: ObjectSchema,
}

fn bindings(projection: &CheckedProjection) -> Result<Vec<Binding<'_>>, CheckError> {
    if projection.record().entries.is_empty() || projection.record().entries.len() > 64 {
        return Err(refusal(
            "HTTP_OPERATION_LIMIT",
            "HTTP generation requires one to 64 checked operations",
            &projection.record().id,
        ));
    }
    let mut result = Vec::new();
    let mut backend_routes = BTreeSet::new();
    let mut frontend_routes = BTreeSet::new();
    let mut modules = BTreeMap::new();
    for entry in &projection.record().entries {
        let frontend: Endpoint = attribute(&entry.subject, "http")?;
        let target = native_target(entry, "handler")?;
        let endpoint = native_target(entry, "endpoint")?;
        let input = native_target(entry, "input")?;
        let backend: Backend = attribute(endpoint, "http")?;
        let handler: Handler = attribute(target, "http")?;
        let source = locator(target, "rust:")?;
        let parts: Vec<_> = source.split("::").collect();
        if parts.len() != 3
            || parts[0] != "crate"
            || !parts[1..].iter().all(|s| identifier(s))
            || !identifier(&handler.request_type)
            || !identifier(&handler.response_type)
            || !identifier(&handler.error_type)
            || handler.profile != PROFILE
            || handler.errors.is_empty()
            || handler.errors.len() > 16
            || handler.module_path.len() > 512
            || !handler.module_path.ends_with(".rs")
            || handler
                .module_path
                .split('/')
                .any(|s| s.is_empty() || s == "." || s == "..")
            || !handler
                .module_path
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"_./-".contains(&b))
            || target.locators.as_ref().is_none_or(|ls| {
                !ls.iter().any(|l| {
                    l.uri == format!("rust:{source}")
                        && l.digest.as_deref().is_some_and(|d| {
                            d.len() == 71
                                && d.starts_with("sha256:")
                                && d[7..]
                                    .bytes()
                                    .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
                        })
                })
            })
        {
            return Err(refusal(
                "HTTP_NATIVE_BINDING_UNSUPPORTED",
                "Expected a byte-bound crate::module::function and explicit contained module map",
                &target.id,
            ));
        }
        if frontend.method != "POST"
            || backend.method != "POST"
            || !path(&frontend.path)
            || !path(&backend.path)
            || !(200..300).contains(&backend.success_status)
            || !frontend_routes.insert((frontend.method.clone(), frontend.path.clone()))
            || !backend_routes.insert((backend.method.clone(), backend.path.clone()))
        {
            return Err(refusal(
                "HTTP_ENDPOINT_CONFLICT",
                "Only unique literal POST endpoints are supported",
                &entry.subject.id,
            ));
        }
        let mut variants = BTreeSet::new();
        let mut codes = BTreeSet::new();
        for error in &handler.errors {
            if !identifier(&error.variant)
                || !(400..600).contains(&error.status)
                || error.code.is_empty()
                || error.code.len() > 128
                || !variants.insert(&error.variant)
                || !codes.insert((error.status, &error.code))
                || !error
                    .code
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b"_-".contains(&b))
            {
                return Err(refusal(
                    "HTTP_ERROR_CONTRACT",
                    "Error variants, statuses and codes must be explicit and unique",
                    &target.id,
                ));
            }
        }
        let module_binding = (
            handler.module_path.clone(),
            target
                .locators
                .as_ref()
                .and_then(|ls| ls.iter().find(|l| l.uri.starts_with("rust:")))
                .and_then(|l| l.digest.clone()),
        );
        if modules
            .insert(parts[1].to_owned(), module_binding.clone())
            .is_some_and(|old| old != module_binding)
        {
            return Err(refusal(
                "HTTP_MODULE_CONFLICT",
                "A module alias cannot select different file bytes",
                &target.id,
            ));
        }
        let request_value: Value = attribute(input, "jsonSchema")?;
        let request = schema(&request_value, &input.id)?;
        let response = schema(&handler.response_schema, &target.id)?;
        result.push(Binding {
            id: &entry.subject.id,
            frontend,
            backend,
            module: parts[1].to_owned(),
            symbol: parts[2].to_owned(),
            request,
            response,
            handler,
        });
    }
    Ok(result)
}

fn rust_validator(schema: &ObjectSchema) -> String {
    let mut check = format!(
        "let Some(object) = value.as_object() else {{ return false; }};\nif object.len() != {} {{ return false; }}\n",
        schema.properties.len()
    );
    for (key, field) in &schema.properties {
        check.push_str(&format!("let Some(text) = object.get({key:?}).and_then(serde_json::Value::as_str) else {{ return false; }};\n"));
        if field.min_length.is_some_and(|n| n > 0) || field.max_length.is_some() {
            check.push_str("let length = text.chars().count();\n");
            if let Some(min) = field.min_length.filter(|n| *n > 0) {
                check.push_str(&format!("if length < {min} {{ return false; }}\n"));
            }
            if let Some(max) = field.max_length {
                check.push_str(&format!("if length > {max} {{ return false; }}\n"));
            }
        } else {
            check.push_str("let _ = text;\n");
        }
    }
    check.push_str("true\n");
    check
}

/// Emits source only. The consumer must bind module paths to captured bytes and run Cargo.
pub fn emit_http_rust(projection: &CheckedProjection) -> Result<String, CheckError> {
    let checked = bindings(projection)?;
    let mut out = emit_rust(projection, None)?;
    out.push_str(&format!(
        "// HTTP profile {PROFILE}; projection {}.\n",
        projection.record().digest
    ));
    let mut modules = BTreeSet::new();
    for binding in &checked {
        if modules.insert(&binding.module) {
            out.push_str(&format!(
                "#[rustfmt::skip]\n#[path = {:?}]\npub mod {};\n",
                binding.handler.module_path, binding.module
            ));
        }
    }
    out.push_str("pub const OPERATIONS: &[(&str, &str, &str)] = &[\n");
    for b in &checked {
        out.push_str(&format!(
            "({:?}, {:?}, {:?}),\n",
            b.id, b.backend.method, b.backend.path
        ));
    }
    out.push_str("];\n");
    for (i, b) in checked.iter().enumerate() {
        out.push_str(&format!("fn request_{i}(value: &serde_json::Value) -> bool {{ {} }}\nfn response_{i}(value: &serde_json::Value) -> bool {{ {} }}\n", rust_validator(&b.request), rust_validator(&b.response)));
    }
    out.push_str("pub fn dispatch(method: &str, path: &str, raw: &[u8]) -> Option<(u16, serde_json::Value)> {\nmatch (method, path) {\n");
    for (i, b) in checked.iter().enumerate() {
        out.push_str(&format!("({:?}, {:?}) => {{\nif raw.len() > 8192 {{ return Some((413, serde_json::json!({{\"error\":\"input-limit\"}}))); }}\nlet parsed: serde_json::Value = match serde_json::from_slice(raw) {{ Ok(v) => v, Err(_) => return Some((400, serde_json::json!({{\"error\":\"invalid-request\"}}))) }};\nif !request_{i}(&parsed) {{ return Some((400, serde_json::json!({{\"error\":\"invalid-request\"}}))); }}\nlet input: {m}::{req} = match serde_json::from_value(parsed) {{ Ok(v) => v, Err(_) => return Some((400, serde_json::json!({{\"error\":\"invalid-request\"}}))) }};\nlet handler: fn({m}::{req}) -> Result<{m}::{res}, {m}::{error}> = {m}::{symbol};\nSome(match handler(input) {{\nOk(value) => match serde_json::to_value(value) {{ Ok(value) if response_{i}(&value) => ({status}, value), _ => (500, serde_json::json!({{\"error\":\"invalid-response\"}})) }},\n", b.backend.method, b.backend.path, m=b.module, req=b.handler.request_type, res=b.handler.response_type, error=b.handler.error_type, symbol=b.symbol, status=b.backend.success_status));
        for error in &b.handler.errors {
            out.push_str(&format!(
                "Err({}::{}::{}) => ({}, serde_json::json!({{\"error\":{:?}}})),\n",
                b.module, b.handler.error_type, error.variant, error.status, error.code
            ));
        }
        out.push_str("})\n},\n");
    }
    out.push_str("_ => None,\n}\n}\n");
    Ok(out)
}

fn ts_type(schema: &ObjectSchema) -> String {
    format!(
        "{{ {} }}",
        schema
            .properties
            .keys()
            .map(|k| format!("{}: string;", js_string(k)))
            .collect::<Vec<_>>()
            .join(" ")
    )
}

fn ts_validator(schema: &ObjectSchema) -> String {
    let mut check = format!(
        "if (typeof value !== 'object' || value === null || Array.isArray(value) || Object.keys(value).length !== {}) return false;\nconst object = value as Record<string, unknown>;\n",
        schema.properties.len()
    );
    for (i, (key, field)) in schema.properties.iter().enumerate() {
        check.push_str(&format!("if (!Object.prototype.hasOwnProperty.call(object, {key})) return false;\nconst text{i} = object[{key}];\nif (typeof text{i} !== 'string' || !unicodeScalars(text{i})) return false;\nconst length{i} = Array.from(text{i}).length;\nif (length{i} < {min} || length{i} > {max}) return false;\n", key=js_string(key), min=field.min_length.unwrap_or(0), max=field.max_length.unwrap_or(u32::MAX)));
    }
    check.push_str("return true;\n");
    check
}

pub fn emit_http_typescript(projection: &CheckedProjection) -> Result<String, CheckError> {
    let checked = bindings(projection)?;
    let mut out = emit_typescript(projection, "BINDINGS", None)?;
    out.push_str(&format!(
        "// HTTP profile {PROFILE}; projection {}.\n",
        projection.record().digest
    ));
    out.push_str("export interface Requests {\n");
    for b in &checked {
        out.push_str(&format!("{}: {};\n", js_string(b.id), ts_type(&b.request)));
    }
    out.push_str("}\nexport interface Responses {\n");
    for b in &checked {
        out.push_str(&format!("{}: {};\n", js_string(b.id), ts_type(&b.response)));
    }
    out.push_str("}\nexport const OPERATIONS = [\n");
    for b in &checked {
        let errors: Vec<_> = b
            .handler
            .errors
            .iter()
            .map(|e| serde_json::json!({"status":e.status,"code":e.code}))
            .chain([
                serde_json::json!({"status":400,"code":"invalid-request"}),
                serde_json::json!({"status":413,"code":"input-limit"}),
                serde_json::json!({"status":500,"code":"invalid-response"}),
            ])
            .collect();
        out.push_str(&format!("{{ id: {}, frontend: {{ method: {}, path: {} }}, backend: {{ method: {}, path: {} }}, successStatus: {}, errors: {} }},\n", js_string(b.id), js_string(&b.frontend.method), js_string(&b.frontend.path), js_string(&b.backend.method), js_string(&b.backend.path), b.backend.success_status, serde_json::to_string(&errors).expect("finite errors")));
    }
    out.push_str("] as const;\nfunction unicodeScalars(value: string): boolean {\nfor (const point of value) { const n = point.codePointAt(0)!; if (n >= 0xd800 && n <= 0xdfff) return false; }\nreturn true;\n}\n");
    for (i, b) in checked.iter().enumerate() {
        out.push_str(&format!("function request_{i}(value: unknown): boolean {{ {} }}\nfunction response_{i}(value: unknown): boolean {{ {} }}\n", ts_validator(&b.request), ts_validator(&b.response)));
    }
    out.push_str(
        "export function validRequest(id: SemanticId, value: unknown): boolean {\nswitch (id) {\n",
    );
    for (i, b) in checked.iter().enumerate() {
        out.push_str(&format!(
            "case {}: return request_{i}(value);\n",
            js_string(b.id)
        ));
    }
    out.push_str("default: return false;\n}\n}\nexport function validResponse(id: SemanticId, value: unknown): boolean {\nswitch (id) {\n");
    for (i, b) in checked.iter().enumerate() {
        out.push_str(&format!(
            "case {}: return response_{i}(value);\n",
            js_string(b.id)
        ));
    }
    out.push_str("default: return false;\n}\n}\n");
    out.push_str("export async function callOperation<I extends SemanticId>(id: I, input: Requests[I], options: {base?: string; endpoint?: 'frontend' | 'backend'; transport?: typeof fetch} = {}): Promise<{status: number; body: Responses[I] | {error: string}}> {\nconst operation = OPERATIONS.find(op => op.id === id);\nif (!operation || !validRequest(id, input)) throw new Error('HTTP_INVALID_REQUEST');\nconst endpoint = operation[options.endpoint ?? 'frontend'];\nconst response = await (options.transport ?? fetch)((options.base ?? '') + endpoint.path, {method:endpoint.method, headers:{'content-type':'application/json'}, body:JSON.stringify(input), cache:'no-store'});\nlet body: unknown;\ntry { body = await response.json(); } catch { throw new Error('HTTP_INVALID_JSON'); }\nif (response.status === operation.successStatus) {\nif (!validResponse(id, body)) throw new Error('HTTP_RESPONSE_CONTRACT');\nreturn {status:response.status, body:body as Responses[I]};\n}\nif (typeof body !== 'object' || body === null || Array.isArray(body) || Object.keys(body).length !== 1 || !('error' in body) || typeof body.error !== 'string' || !operation.errors.some(e => e.status === response.status && e.code === body.error)) throw new Error('HTTP_ERROR_CONTRACT');\nreturn {status:response.status, body:body as {error:string}};\n}\n");
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn schema_refuses_unimplemented_required_semantics() {
        let base = serde_json::json!({"$schema":DIALECT,"type":"object","additionalProperties":false,"required":["name"],"properties":{"name":{"type":"string","minLength":1,"maxLength":80}}});
        assert!(schema(&base, "request").is_ok());
        let mut integral = base.clone();
        integral["properties"]["name"]["maxLength"] = serde_json::json!(80.0);
        assert!(schema(&integral, "request").is_ok());
        let mut fractional = base.clone();
        fractional["properties"]["name"]["maxLength"] = serde_json::json!(80.5);
        assert!(schema(&fractional, "request").is_err());
        for bad in [
            serde_json::json!({"pattern":"^[a-z]+$"}),
            serde_json::json!({"format":"email"}),
            serde_json::json!({"type":"integer"}),
        ] {
            let mut value = base.clone();
            value["properties"]["name"]
                .as_object_mut()
                .unwrap()
                .extend(bad.as_object().unwrap().clone());
            assert!(schema(&value, "request").is_err());
        }
        let mut optional = base.clone();
        optional["required"] = serde_json::json!([]);
        assert!(schema(&optional, "request").is_err());
        let mut duplicate = base.clone();
        duplicate["required"] = serde_json::json!(["name", "name"]);
        assert!(schema(&duplicate, "request").is_err());
        let mut inverted = base;
        inverted["properties"]["name"]["maxLength"] = serde_json::json!(0);
        assert!(schema(&inverted, "request").is_err());
    }
}
