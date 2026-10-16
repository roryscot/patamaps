//! Explicit HTTP transport contracts and module-local Axum signature witnesses.
//! Existing application routers remain authoritative; no macro inference occurs.
use crate::http::{attribute, identifier, refusal};
use crate::{CheckedProjection, http_schema::Schema, js_string, locator, native_target};
use patamaps_core::CheckError;
use serde::Deserialize;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

const PROFILE: &str = "patamaps-http-transport-1";

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Endpoint {
    method: String,
    path: String,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Backend {
    method: String,
    path: String,
    success_status: u16,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Limits {
    request_bytes: u32,
    response_bytes: u32,
    depth: u32,
    values: u32,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct ErrorBody {
    status: u16,
    schema: Value,
}
#[derive(Deserialize)]
#[serde(tag = "extractor", rename_all = "kebab-case", deny_unknown_fields)]
enum Argument {
    State { r#type: String },
    Json { r#type: String },
    JsonResult { r#type: String },
    Path { r#type: String },
    Query { r#type: String },
    Headers,
}
#[derive(Deserialize)]
#[serde(rename_all = "kebab-case")]
enum OutputMode {
    ResultJson,
    Json,
    Response,
    Native,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Output {
    mode: OutputMode,
    #[serde(default)]
    success_type: Option<String>,
    #[serde(default)]
    error_type: Option<String>,
}
#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Handler {
    profile: String,
    module_path: String,
    arguments: Vec<Argument>,
    output: Output,
    response_schema: Value,
    errors: Vec<ErrorBody>,
    limits: Limits,
    #[serde(default)]
    frontend_group: Option<String>,
    #[serde(default)]
    path_parameters: Option<Value>,
    #[serde(default)]
    query_parameters: Option<Value>,
    #[serde(default)]
    header_parameters: Option<Value>,
}
struct Binding<'a> {
    id: &'a str,
    frontend: Endpoint,
    backend: Backend,
    handler: Handler,
    source: String,
    symbol: String,
    module: String,
    digest: String,
    body: Schema,
    response: Schema,
    errors: Vec<Schema>,
    path: Schema,
    query: Schema,
    headers: Schema,
}
fn rust_type(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 256
        && value
            .split("::")
            .enumerate()
            .all(|(i, s)| identifier(s) || (i == 0 && ["crate", "self", "super"].contains(&s)))
}
fn source_path(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 512
        && value
            .split('/')
            .all(|v| !v.is_empty() && v != "." && v != "..")
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"_./-".contains(&b))
}
fn template(path: &str) -> Option<BTreeSet<String>> {
    if !path.starts_with('/') || path.len() > 1024 || (path.len() > 1 && path.ends_with('/')) {
        return None;
    }
    if path == "/" {
        return Some(BTreeSet::new());
    }
    let mut names = BTreeSet::new();
    for segment in path[1..].split('/') {
        if segment.starts_with(':') || (segment.starts_with('{') && segment.ends_with('}')) {
            let name = if let Some(name) = segment.strip_prefix(':') {
                name
            } else {
                &segment[1..segment.len() - 1]
            };
            if !identifier(name) || !names.insert(name.into()) {
                return None;
            }
        } else if segment.is_empty()
            || [".", ".."].contains(&segment)
            || !segment
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"_-~.".contains(&b))
        {
            return None;
        }
    }
    Some(names)
}
fn parameters(value: Option<&Value>, subject: &str) -> Result<Schema, CheckError> {
    let empty = serde_json::json!({"$schema":"https://json-schema.org/draft/2020-12/schema",
        "type":"object","additionalProperties":false,"properties":{}});
    let node = crate::http_schema::parse_transport(value.unwrap_or(&empty), subject)?;
    if let Schema::Object { fields, extra, .. } = &node
        && matches!(extra.as_ref(), Schema::Never)
        && fields.values().all(|v| {
            matches!(
                v,
                Schema::String { .. } | Schema::Number { .. } | Schema::Boolean
            )
        })
    {
        return Ok(node);
    }
    Err(refusal(
        "HTTP_PARAMETER_SCHEMA",
        "Parameters require exact flat objects of JSON scalar fields",
        subject,
    ))
}
fn bindings(projection: &CheckedProjection) -> Result<Vec<Binding<'_>>, CheckError> {
    let entries = &projection.record().entries;
    if entries.is_empty() || entries.len() > 64 {
        return Err(refusal(
            "HTTP_OPERATION_LIMIT",
            "Select one to64 transport operations",
            &projection.record().id,
        ));
    }
    let mut frontend_groups = BTreeMap::new();
    let mut backends = BTreeSet::new();
    let mut result = Vec::new();
    for entry in entries {
        let id = entry.subject.id.as_str();
        let frontend: Endpoint = attribute(&entry.subject, "http")?;
        let target = native_target(entry, "handler")?;
        let endpoint = native_target(entry, "endpoint")?;
        let input = native_target(entry, "input")?;
        let backend: Backend = attribute(endpoint, "http")?;
        let handler: Handler = attribute(target, "http")?;
        let source = locator(target, "rust:")?.to_owned();
        let parts: Vec<_> = source.split("::").collect();
        let bad = |code, msg| refusal(code, msg, id);
        if handler.profile != PROFILE
            || parts.len() < 3
            || parts.len() > 10
            || parts[0] != "crate"
            || !parts[1..].iter().all(|s| identifier(s))
            || !source_path(&handler.module_path)
            || !handler.module_path.ends_with(".rs")
        {
            return Err(bad(
                "HTTP_TRANSPORT_BINDING",
                "Expected an explicit byte-bound Rust module/function transport declaration",
            ));
        }
        let digest = target
            .locators
            .as_ref()
            .and_then(|v| v.iter().find(|l| l.uri == format!("rust:{source}")))
            .and_then(|v| v.digest.clone())
            .filter(|s| {
                s.len() == 71
                    && s.starts_with("sha256:")
                    && s[7..]
                        .bytes()
                        .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
            })
            .ok_or_else(|| {
                bad(
                    "HTTP_TRANSPORT_BINDING",
                    "A captured source digest is required",
                )
            })?;
        let front_names = template(&frontend.path).ok_or_else(|| {
            bad(
                "HTTP_ENDPOINT_CONFLICT",
                "Unsupported frontend URI template",
            )
        })?;
        let back_names = template(&backend.path)
            .ok_or_else(|| bad("HTTP_ENDPOINT_CONFLICT", "Unsupported backend URI template"))?;
        let methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"];
        if !methods.contains(&frontend.method.as_str())
            || !methods.contains(&backend.method.as_str())
            || frontend.method != backend.method
            || backend.path.split('/').any(|s| s.starts_with(':'))
            || !(200..300).contains(&backend.success_status)
            || !backends.insert((backend.method.clone(), backend.path.clone()))
            || front_names != back_names
        {
            return Err(bad(
                "HTTP_ENDPOINT_CONFLICT",
                "Methods, unique backend routes and shared path parameter names must be explicit",
            ));
        }
        if handler
            .frontend_group
            .as_ref()
            .is_some_and(|v| v.is_empty() || v.len() > 256 || v.chars().any(char::is_control))
        {
            return Err(bad("HTTP_PROXY_GROUP", "Invalid explicit frontend group"));
        }
        if let Some(old) = frontend_groups.insert(
            (frontend.method.clone(), frontend.path.clone()),
            handler.frontend_group.clone(),
        ) && (old.is_none() || old != handler.frontend_group)
        {
            return Err(bad(
                "HTTP_PROXY_GROUP",
                "Shared frontend routes require the same explicit nonempty group",
            ));
        }
        let limits = &handler.limits;
        if !(1..=16777216).contains(&limits.request_bytes)
            || !(1..=67108864).contains(&limits.response_bytes)
            || !(1..=128).contains(&limits.depth)
            || !(1..=1000000).contains(&limits.values)
        {
            return Err(bad(
                "HTTP_TRANSPORT_LIMIT",
                "Transport limits exceed the bounded profile",
            ));
        }
        if handler.arguments.len() > 8 {
            return Err(bad("HTTP_AXUM_SIGNATURE", "Too many extractors"));
        }
        let mut extractors = BTreeSet::new();
        let mut has_body = false;
        for (index, arg) in handler.arguments.iter().enumerate() {
            let (name, ty) = match arg {
                Argument::State { r#type } => ("state", Some(r#type)),
                Argument::Json { r#type } => ("body", Some(r#type)),
                Argument::JsonResult { r#type } => ("body", Some(r#type)),
                Argument::Path { r#type } => ("path", Some(r#type)),
                Argument::Query { r#type } => ("query", Some(r#type)),
                Argument::Headers => ("headers", None),
            };
            if !extractors.insert(name)
                || ty.is_some_and(|v| !rust_type(v))
                || (name == "body"
                    && (index + 1 != handler.arguments.len()
                        || ["GET", "HEAD"].contains(&backend.method.as_str())))
            {
                return Err(bad(
                    "HTTP_AXUM_SIGNATURE",
                    "Extractor types/order are invalid; body extraction must be last",
                ));
            }
            has_body |= name == "body";
        }
        match handler.output.mode {
            OutputMode::ResultJson
                if handler
                    .output
                    .success_type
                    .as_ref()
                    .is_some_and(|v| rust_type(v))
                    && handler
                        .output
                        .error_type
                        .as_ref()
                        .is_some_and(|v| rust_type(v)) => {}
            OutputMode::Json
                if handler
                    .output
                    .success_type
                    .as_ref()
                    .is_some_and(|v| rust_type(v))
                    && handler.output.error_type.is_none() => {}
            OutputMode::Native
                if handler
                    .output
                    .success_type
                    .as_ref()
                    .is_some_and(|v| rust_type(v))
                    && handler.output.error_type.is_none() => {}
            OutputMode::Response
                if handler.output.success_type.is_none() && handler.output.error_type.is_none() => {
            }
            _ => {
                return Err(bad(
                    "HTTP_AXUM_SIGNATURE",
                    "Output shape must explicitly match the actual function return type",
                ));
            }
        }
        let request_value: Value = attribute(input, "jsonSchema")?;
        let body = crate::http_schema::parse_transport(&request_value, &input.id)?;
        if !has_body && !matches!(body, Schema::Null) {
            return Err(bad(
                "HTTP_TRANSPORT_BODY",
                "Bodyless operations must declare null input",
            ));
        }
        let response = crate::http_schema::parse_transport(&handler.response_schema, id)?;
        if (backend.method == "HEAD" || [204, 205].contains(&backend.success_status))
            && !matches!(response, Schema::Null)
        {
            return Err(bad(
                "HTTP_TRANSPORT_BODY",
                "HEAD and no-content response contracts must be null",
            ));
        }
        let path = parameters(handler.path_parameters.as_ref(), id)?;
        let query = parameters(handler.query_parameters.as_ref(), id)?;
        let headers = parameters(handler.header_parameters.as_ref(), id)?;
        if let Schema::Object {
            fields, required, ..
        } = &path
            && (fields.keys().cloned().collect::<BTreeSet<_>>() != front_names
                || *required != front_names)
        {
            return Err(bad(
                "HTTP_PARAMETER_SCHEMA",
                "Path fields must exactly match both templates and all be required",
            ));
        }
        if !front_names.is_empty() && !extractors.contains("path") {
            return Err(bad(
                "HTTP_AXUM_SIGNATURE",
                "Dynamic backend routes require an explicit Path extractor witness",
            ));
        }
        for (node, extractor) in [(&query, "query"), (&headers, "headers")] {
            if let Schema::Object { fields, .. } = node
                && !fields.is_empty()
                && !extractors.contains(extractor)
            {
                return Err(bad(
                    "HTTP_AXUM_SIGNATURE",
                    "Parameter contracts require the matching explicit extractor",
                ));
            }
        }
        if let Schema::Object { fields, .. } = &headers {
            for name in fields.keys() {
                if name.is_empty()
                    || !name
                        .bytes()
                        .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b"-_".contains(&b))
                    || [
                        "host",
                        "content-length",
                        "content-type",
                        "connection",
                        "cookie",
                        "set-cookie",
                    ]
                    .contains(&name.as_str())
                {
                    return Err(bad(
                        "HTTP_HEADER_CONTRACT",
                        "Use explicit lowercase, non-reserved header names",
                    ));
                }
            }
        }
        let mut statuses = BTreeSet::new();
        if handler.errors.len() > 32 {
            return Err(bad("HTTP_ERROR_CONTRACT", "Too many declared errors"));
        }
        let errors = handler
            .errors
            .iter()
            .map(|error| {
                if !(400..600).contains(&error.status) || !statuses.insert(error.status) {
                    return Err(bad(
                        "HTTP_ERROR_CONTRACT",
                        "Error statuses must be unique client/server failures",
                    ));
                }
                let node = crate::http_schema::parse_transport(&error.schema, id)?;
                if backend.method == "HEAD" && !matches!(node, Schema::Null) {
                    return Err(bad("HTTP_ERROR_CONTRACT", "HEAD errors have null bodies"));
                }
                Ok(node)
            })
            .collect::<Result<Vec<_>, _>>()?;
        result.push(Binding {
            id,
            symbol: parts.last().expect("validated").to_string(),
            module: parts[1..parts.len() - 1].join("::"),
            frontend,
            backend,
            handler,
            source,
            digest,
            body,
            response,
            errors,
            path,
            query,
            headers,
        });
    }
    Ok(result)
}

fn argument(arg: &Argument) -> String {
    match arg {
        Argument::State { r#type: ty } => format!("axum::extract::State<{ty}>"),
        Argument::Json { r#type: ty } => format!("axum::Json<{ty}>"),
        Argument::JsonResult { r#type: ty } => {
            format!(
                "::std::result::Result<axum::Json<{ty}>, axum::extract::rejection::JsonRejection>"
            )
        }
        Argument::Path { r#type: ty } => format!("axum::extract::Path<{ty}>"),
        Argument::Query { r#type: ty } => format!("axum::extract::Query<{ty}>"),
        Argument::Headers => "axum::http::HeaderMap".into(),
    }
}

/// Include inside the declared existing Rust module. It registers no routes and runs no code.
pub fn emit_axum_witness(projection: &CheckedProjection) -> Result<String, CheckError> {
    let entries = bindings(projection)?;
    let module = &entries[0].module;
    let path = &entries[0].handler.module_path;
    if entries.iter().any(|b| {
        &b.module != module || &b.handler.module_path != path || b.digest != entries[0].digest
    }) {
        return Err(refusal(
            "HTTP_AXUM_WITNESS_SCOPE",
            "A module-local witness must select exactly one captured Rust module",
            &projection.record().id,
        ));
    }
    let suffix = &projection.record().digest[7..23];
    let mut out = format!(
        "// Module-local Axum witness; projection {}, module {}, source {}.\n",
        projection.record().digest,
        module,
        entries[0].digest
    );
    out.push_str(&format!(
        "#[allow(dead_code)]\nfn __patamaps_witness_{suffix}() {{\n"
    ));
    for (index, b) in entries.iter().enumerate() {
        let args = b
            .handler
            .arguments
            .iter()
            .map(argument)
            .collect::<Vec<_>>()
            .join(",");
        let success = b.handler.output.success_type.as_deref().unwrap_or("()");
        let result = match b.handler.output.mode {
            OutputMode::ResultJson => format!(
                "::std::result::Result<axum::Json<{success}>,(axum::http::StatusCode,axum::Json<{}>)>",
                b.handler.output.error_type.as_ref().expect("validated")
            ),
            OutputMode::Json => format!("axum::Json<{success}>"),
            OutputMode::Response => "axum::response::Response".into(),
            OutputMode::Native => success.into(),
        };
        let state = b
            .handler
            .arguments
            .iter()
            .find_map(|v| match v {
                Argument::State { r#type } => Some(r#type.as_str()),
                _ => None,
            })
            .unwrap_or("()");
        out.push_str(&format!("fn signature_{index}<__PatamapsHandler{suffix},__PatamapsFuture{suffix}>(handler:__PatamapsHandler{suffix}) where __PatamapsHandler{suffix}: ::std::ops::Fn({args}) -> __PatamapsFuture{suffix}, __PatamapsFuture{suffix}: ::std::future::Future<Output={result}> + ::std::marker::Send {{ let _ = handler; }}\nsignature_{index}({symbol});\nlet _: axum::routing::MethodRouter<{state}> = axum::routing::{method}({symbol});\n",
            symbol=b.symbol,method=b.backend.method.to_ascii_lowercase()));
        out.push_str(&format!(
            "let _ = ({:?},{:?},{:?},{:?});\n",
            b.id, b.source, b.backend.method, b.backend.path
        ));
    }
    out.push_str("}\n");
    Ok(out)
}

fn validator(name: &str, schema: &Schema, limits: &Limits) -> String {
    format!(
        "function {name}(value: unknown): boolean {{ return httpJsonBoundary(value,{}, {}) && ({}); }}\n",
        limits.depth,
        limits.values,
        schema.typescript()
    )
}

pub fn emit_http_client(projection: &CheckedProjection) -> Result<String, CheckError> {
    let entries = bindings(projection)?;
    let mut out = format!(
        "// Checked HTTP transport profile {PROFILE}.\nexport const PROJECTION_DIGEST = {};\nexport type SemanticId = {};\n",
        js_string(&projection.record().digest),
        entries
            .iter()
            .map(|b| js_string(b.id))
            .collect::<Vec<_>>()
            .join(" | ")
    );
    out.push_str(crate::http_schema::TYPESCRIPT_RUNTIME);
    out.push_str("function unicodeScalars(value: string): boolean { for (const c of value) { const n=c.codePointAt(0)!; if(n>=0xd800 && n<=0xdfff)return false; } return true; }\n");
    for (name, getter) in [
        ("Requests", 0),
        ("Responses", 1),
        ("PathParameters", 2),
        ("QueryParameters", 3),
        ("HeaderParameters", 4),
    ] {
        out.push_str(&format!("export interface {name} {{\n"));
        for b in &entries {
            let schema = match getter {
                0 => &b.body,
                1 => &b.response,
                2 => &b.path,
                3 => &b.query,
                _ => &b.headers,
            };
            out.push_str(&format!("{}: {};\n", js_string(b.id), schema.ts()));
        }
        out.push_str("}\n");
    }
    out.push_str("export interface Results {\n");
    for b in &entries {
        out.push_str(&format!(
            "{}: {{status:{};body:Responses[{}]}};\n",
            js_string(b.id),
            b.backend.success_status,
            js_string(b.id)
        ));
    }
    out.push_str("}\nexport interface Errors {\n");
    for b in &entries {
        let types = b
            .handler
            .errors
            .iter()
            .zip(&b.errors)
            .map(|(e, s)| format!("{{status:{};body:{}}}", e.status, s.ts()))
            .collect::<Vec<_>>();
        out.push_str(&format!(
            "{}: {};\n",
            js_string(b.id),
            if types.is_empty() {
                "never".into()
            } else {
                types.join(" | ")
            }
        ));
    }
    out.push_str("}\n");
    for (i, b) in entries.iter().enumerate() {
        for (name, schema) in [
            ("body", &b.body),
            ("response", &b.response),
            ("path", &b.path),
            ("query", &b.query),
            ("headers", &b.headers),
        ] {
            out.push_str(&validator(
                &format!("{name}_{i}"),
                schema,
                &b.handler.limits,
            ));
        }
        for (j, schema) in b.errors.iter().enumerate() {
            out.push_str(&validator(
                &format!("error_{i}_{j}"),
                schema,
                &b.handler.limits,
            ));
        }
    }
    out.push_str("export const OPERATIONS = [\n");
    for (i, b) in entries.iter().enumerate() {
        let has_body = b
            .handler
            .arguments
            .iter()
            .any(|a| matches!(a, Argument::Json { .. } | Argument::JsonResult { .. }));
        let errors = b
            .handler
            .errors
            .iter()
            .enumerate()
            .map(|(j, e)| format!("{{status:{},valid:error_{i}_{j}}}", e.status))
            .collect::<Vec<_>>()
            .join(",");
        out.push_str(&format!("{{id:{},frontend:{{method:{},path:{}}},backend:{{method:{},path:{}}},successStatus:{},hasBody:{has_body},requestBytes:{},responseBytes:{},validBody:body_{i},validResponse:response_{i},validPath:path_{i},validQuery:query_{i},validHeaders:headers_{i},errors:[{errors}]}},\n",
            js_string(b.id),js_string(&b.frontend.method),js_string(&b.frontend.path),js_string(&b.backend.method),js_string(&b.backend.path),b.backend.success_status,b.handler.limits.request_bytes,b.handler.limits.response_bytes));
    }
    out.push_str("] as const;\n");
    out.push_str(CLIENT_RUNTIME);
    Ok(out)
}

const CLIENT_RUNTIME: &str = r#"
type RuntimeOptions<I extends SemanticId> = {
 base?: string; endpoint?: 'frontend'|'backend'; transport?: typeof fetch; signal?: AbortSignal;
 path?: PathParameters[I]; query?: QueryParameters[I]; headers?: HeaderParameters[I];
};
export type CallOptions<I extends SemanticId> = Omit<RuntimeOptions<I>, 'path'|'query'|'headers'>
 & ({} extends PathParameters[I] ? {path?:PathParameters[I]} : {path:PathParameters[I]})
 & ({} extends QueryParameters[I] ? {query?:QueryParameters[I]} : {query:QueryParameters[I]})
 & ({} extends HeaderParameters[I] ? {headers?:HeaderParameters[I]} : {headers:HeaderParameters[I]});
type CallArguments<I extends SemanticId> = {} extends CallOptions<I> ? [options?:CallOptions<I>] : [options:CallOptions<I>];
function encodePath(template: string, parameters: Record<string,unknown>): string {
 return template.replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}|:([A-Za-z_][A-Za-z0-9_]*)/g,(_,brace:string,colon:string)=>{
  const key=brace??colon;
  const raw=String(parameters[key]);
  if(raw==='' || raw==='.' || raw==='..')throw new Error('HTTP_INVALID_PATH');
  return encodeURIComponent(raw).replace(/[!'()*]/g,c=>'%'+c.charCodeAt(0).toString(16).toUpperCase());
 });
}
async function readJson(response: Response,maximum: number,head: boolean): Promise<unknown> {
 if(head){if(response.body)await response.body.cancel();return null;}
 if(response.headers.get('content-type')?.split(';')[0].trim().toLowerCase()!=='application/json')throw new Error('HTTP_CONTENT_TYPE');
 if(!response.body)throw new Error('HTTP_INVALID_JSON');
 const reader=response.body.getReader();const chunks:Uint8Array[]=[];let total=0;
 try {
  while(true){
   const next=await reader.read();if(next.done)break;
   total+=next.value.byteLength;
   if(total>maximum){await reader.cancel();throw new Error('HTTP_RESPONSE_LIMIT');}
   chunks.push(next.value);
  }
 } finally {reader.releaseLock();}
 const data=new Uint8Array(total);let offset=0;
 for(const chunk of chunks){data.set(chunk,offset);offset+=chunk.byteLength;}
 try{return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(data));}
 catch{throw new Error('HTTP_INVALID_JSON');}
}
interface TransportOperation {
 id:string;frontend:{method:string;path:string};backend:{method:string;path:string};successStatus:number;hasBody:boolean;requestBytes:number;responseBytes:number;
 validBody:(value:unknown)=>boolean;validResponse:(value:unknown)=>boolean;validPath:(value:unknown)=>boolean;validQuery:(value:unknown)=>boolean;validHeaders:(value:unknown)=>boolean;
 errors:readonly {status:number;valid:(value:unknown)=>boolean}[];
}
export async function callOperation<I extends SemanticId>(id:I,input:Requests[I],...configuration:CallArguments<I>):Promise<Results[I]|Errors[I]> {
 const options=(configuration[0]??{}) as RuntimeOptions<I>;
 const operations:readonly TransportOperation[]=OPERATIONS;
 const op=operations.find(op=>op.id===id);
 const path=options.path??{},query=options.query??{},headers=options.headers??{};
 if(!op || !op.validBody(input) || !op.validPath(path) || !op.validQuery(query) || !op.validHeaders(headers))throw new Error('HTTP_INVALID_REQUEST');
 const endpoint=op[options.endpoint??'frontend'];
 const route=encodePath(endpoint.path,path as Record<string,unknown>);
 const base=options.base??globalThis.location?.origin;
 if(!base)throw new Error('HTTP_BASE_REQUIRED');
 const url=new URL(route,base);
 const qs=query as Record<string,unknown>;
 for(const key of Object.keys(qs).sort())url.searchParams.append(key,String(qs[key]));
 const wireHeaders=new Headers();let headerBytes=0;
 for(const [name,value] of Object.entries(headers)){
  const text=String(value);
  if(!/^[\x20-\x7e]*$/.test(text) || text.trim()!==text)throw new Error('HTTP_INVALID_HEADERS');
  headerBytes+=name.length+text.length+4;
  if(headerBytes>8192)throw new Error('HTTP_HEADER_LIMIT');
  wireHeaders.set(name,text);
 }
 let body:string|undefined;
 if(op.hasBody){
  body=JSON.stringify(input);
  if(new TextEncoder().encode(body).byteLength>op.requestBytes)throw new Error('HTTP_INPUT_LIMIT');
  wireHeaders.set('content-type','application/json');
 }
 const response=await (options.transport??fetch)(url,{method:endpoint.method,headers:wireHeaders,body,cache:'no-store',signal:options.signal});
 const result=await readJson(response,op.responseBytes,endpoint.method==='HEAD' || response.status===204 || response.status===205);
 if(response.status===op.successStatus){
  if(!op.validResponse(result))throw new Error('HTTP_RESPONSE_CONTRACT');
  return {status:response.status,body:result} as Results[I];
 }
 const error=op.errors.find(error=>error.status===response.status);
 if(!error || !error.valid(result))throw new Error('HTTP_ERROR_CONTRACT');
 return {status:response.status,body:result} as Errors[I];
}
"#;

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn uri_templates_are_bounded_and_do_not_normalize_identity() {
        assert_eq!(
            template("/items/{id}").unwrap(),
            BTreeSet::from(["id".into()])
        );
        assert!(template("/").unwrap().is_empty());
        for value in [
            "/a//b",
            "/a/../b",
            "/a/{id}/{id}",
            "/a/{id}suffix",
            "/a/*rest",
            "/a/%2e",
            "/a?query=x",
        ] {
            assert!(template(value).is_none(), "{value}");
        }
    }
    #[test]
    fn parameter_schemas_refuse_implicit_wire_coercions() {
        let schema = serde_json::json!({"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","additionalProperties":false,
            "properties":{"limit":{"type":"integer","minimum":0}}});
        assert!(parameters(Some(&schema), "query").is_ok());
        let mut bad = schema;
        bad["properties"]["limit"] = serde_json::json!({"type":"array","items":{"type":"string"}});
        assert!(parameters(Some(&bad), "query").is_err());
    }
    #[test]
    fn rust_types_do_not_admit_arbitrary_source() {
        for value in ["State", "crate::domain::Response", "serde_json::Value"] {
            assert!(rust_type(value));
        }
        for value in ["Vec<String>", "A; panic!()", "&State", "crate::::Type"] {
            assert!(!rust_type(value));
        }
    }
}
