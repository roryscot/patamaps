//! Workspace observations share the existing merge, correspondence, validation,
//! stable digest and reporting engines. No graph is admitted or activated here.
use crate::legacy_composition::{selected, validate_shards};
use crate::legacy_references::component;
use crate::legacy_reporting::js_text;
use crate::{
    LegacyCorrespondenceRequest, LegacyGraphRegistry, LegacyReportingAction,
    LegacyReportingRequest, legacy_correspondence_request, legacy_reporting_request,
    validate_legacy_document,
};
use icu_collator::{Collator, CollatorBorrowed, CollatorPreferences};
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyPackJson, LegacyReadOnlyJson as Data,
    byte_digest,
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, value::RawValue};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LegacyWorkspaceRequest {
    pub operation: String,
    pub input: String,
    #[serde(default = "default_locale")]
    pub locale: String,
}
fn default_locale() -> String {
    "en-US".into()
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyWorkspaceError {
    pub code: Box<str>,
    pub name: String,
    pub message: Box<RawValue>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub identifier: Option<Box<RawValue>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<Box<str>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub errno: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub syscall: Option<Box<str>>,
}
pub(crate) fn error(name: &str, message: &str) -> LegacyWorkspaceError {
    LegacyWorkspaceError {
        code: "LEGACY_WORKSPACE_INPUT".into(),
        name: name.into(),
        message: Data::string_json(&Data::string_units(message)),
        identifier: None,
        path: None,
        errno: None,
        syscall: None,
    }
}
fn composition_error(e: crate::LegacyCompositionError) -> LegacyWorkspaceError {
    let mut e2 = error(&e.name, &e.message);
    e2.identifier = e
        .identifier
        .map(|s| Data::string_json(&Data::string_units(&s)));
    e2
}
pub(crate) fn parse(text: &str) -> Result<J, LegacyWorkspaceError> {
    Data::parse(text, COMPATIBILITY_JSON_LIMITS)
        .map(|d| d.value().clone())
        .map_err(|e| error("Error", &e.to_string()))
}
pub(crate) fn raw(v: &J) -> Result<String, LegacyWorkspaceError> {
    Data::json_raw(v)
        .map(|r| r.get().to_owned())
        .map_err(|e| error("Error", &e.to_string()))
}
pub(crate) fn native(v: impl Serialize) -> J {
    let text = serde_json::to_string(&v).expect("native serializable workspace observation");
    serde_json::from_str(&text).expect("projected scalar workspace result")
}
pub(crate) fn observed(v: impl Serialize) -> J {
    parse(&serde_json::to_string(&v).expect("native legacy JSON result"))
        .expect("native UTF-16 JSON result")
}
pub(crate) fn scalar(v: &str) -> J {
    Data::string_value(&v.encode_utf16().collect::<Vec<_>>())
}
pub(crate) fn obj(pairs: Vec<(&str, J)>) -> J {
    J::Object(pairs.into_iter().map(|(k, v)| (k.into(), v)).collect())
}
pub(crate) fn get<'a>(v: &'a J, key: &str) -> Result<&'a J, LegacyWorkspaceError> {
    v.get(key)
        .ok_or_else(|| error("TypeError", &format!("Workspace input requires {key}")))
}
pub(crate) fn list<'a>(v: &'a J, key: &str) -> Result<&'a [J], LegacyWorkspaceError> {
    get(v, key)?
        .array()
        .ok_or_else(|| error("TypeError", &format!("Workspace {key} requires an array")))
}
pub(crate) fn text<'a>(v: &'a J, key: &str) -> Result<&'a str, LegacyWorkspaceError> {
    get(v, key)?
        .string()
        .ok_or_else(|| error("TypeError", &format!("Workspace {key} requires a string")))
}
pub(crate) fn fallback<'a>(v: Option<&'a J>, other: &'a J) -> &'a J {
    v.filter(|v| !matches!(v, J::Null)).unwrap_or(other)
}
pub(crate) fn truthy(v: Option<&J>) -> bool {
    match v {
        None | Some(J::Null) | Some(J::Bool(false)) => false,
        Some(J::Number(n)) => *n != 0.0,
        Some(J::String(s)) => !s.is_empty(),
        _ => true,
    }
}
fn set(v: &mut J, key: &str, value: J) {
    let J::Object(items) = v else {
        panic!("checked workspace object")
    };
    if let Some((_, slot)) = items.iter_mut().find(|(k, _)| k == key) {
        *slot = value
    } else {
        items.push((key.into(), value))
    }
}
fn hash(v: &J, col: &CollatorBorrowed<'_>) -> Result<J, LegacyWorkspaceError> {
    Data::stable_bytes(v, col)
        .map(|b| scalar(&byte_digest(&b)))
        .map_err(|e| error("Error", &e.to_string()))
}
pub(crate) fn pretty(v: &J, col: &CollatorBorrowed<'_>) -> Result<J, LegacyWorkspaceError> {
    let b = Data::stable_pretty_bytes(v, col).map_err(|e| error("Error", &e.to_string()))?;
    Ok(scalar(std::str::from_utf8(&b).expect("JSON UTF8 bytes")))
}
pub(crate) fn locale(value: &str) -> Result<CollatorBorrowed<'static>, LegacyWorkspaceError> {
    let p = CollatorPreferences::from_locale_strict(
        &value
            .parse()
            .map_err(|_| error("Error", "Invalid workspace locale"))?,
    )
    .map_err(|_| error("Error", "Unsupported workspace locale preferences"))?;
    Collator::try_new(p, Default::default()).map_err(|e| error("Error", &e.to_string()))
}
fn projection(v: &J) -> Result<Value, LegacyWorkspaceError> {
    Data::projected_value(v).map_err(|e| error("Error", &e.to_string()))
}
fn binding(target: Vec<J>, source: Vec<J>) -> J {
    obj(vec![
        ("target", J::Array(target)),
        ("source", J::Array(source)),
    ])
}
fn path(s: &str) -> J {
    scalar(s)
}
fn index(n: usize) -> J {
    J::Number(n as f64)
}
fn property<'a>(v: &'a J, parts: &[&str]) -> Option<&'a J> {
    parts.iter().try_fold(v, |v, key| v.get(key))
}
struct Document {
    value: J,
    origins: HashMap<(String, usize), Vec<J>>,
}
fn compose(
    documents: &[Document],
    options: J,
    col: &CollatorBorrowed<'_>,
) -> Result<Document, LegacyWorkspaceError> {
    if documents.is_empty() {
        return Err(composition_error(crate::LegacyCompositionError {
            code: "LEGACY_COMPOSITION_INPUT".into(),
            name: "MetamapCompositionError".into(),
            message: "At least one metamap shard is required".into(),
            identifier: None,
        }));
    }
    let values: Vec<J> = documents.iter().map(|d| d.value.clone()).collect();
    validate_shards(&values).map_err(composition_error)?;
    let mut graph = obj(vec![
        ("$schema", scalar("./schemas/metamap-graph.schema.json")),
        ("schemaVersion", scalar("2.0.0")),
    ]);
    for field in ["id", "namespace", "label", "revision"] {
        if let Some(value) = options.get(field) {
            set(&mut graph, field, value.clone())
        }
    }
    let mut origins = HashMap::new();
    for (field, kind) in [
        ("relationPacks", "relation pack"),
        ("entities", "entity"),
        ("mappings", "mapping"),
        ("authorities", "authority"),
    ] {
        let handles = selected(&values, field, kind, col, true).map_err(composition_error)?;
        let mut entries = Vec::new();
        for h in handles {
            let di = h["document"].as_u64().expect("selected document") as usize;
            let ii = h["item"].as_u64().expect("selected item") as usize;
            let out = entries.len();
            entries.push(list(&documents[di].value, field)?[ii].clone());
            if let Some(p) = documents[di].origins.get(&(field.into(), ii)) {
                origins.insert((field.into(), out), p.clone());
            }
        }
        set(&mut graph, field, J::Array(entries));
    }
    set(
        &mut graph,
        "metadata",
        obj(vec![(
            "composedFrom",
            J::Array(
                values
                    .iter()
                    .map(|v| get(v, "id").expect("checked shard id").clone())
                    .collect(),
            ),
        )]),
    );
    Ok(Document {
        value: graph,
        origins,
    })
}
fn snapshot(
    graph: &J,
    adapters: &[J],
    config_digest: J,
    col: &CollatorBorrowed<'_>,
) -> Result<J, LegacyWorkspaceError> {
    let mut sources = Vec::new();
    for a in adapters {
        sources.push(obj(vec![
            ("id", get(a, "sourceId")?.clone()),
            ("adapter", get(a, "adapter")?.clone()),
            ("adapterVersion", get(a, "adapterVersion")?.clone()),
            ("inputs", get(a, "inputs")?.clone()),
        ]));
    }
    Ok(obj(vec![
        ("schemaVersion", scalar("1.0.0")),
        ("graphId", get(graph, "id")?.clone()),
        (
            "graphRevision",
            fallback(graph.get("revision"), &scalar("unversioned")).clone(),
        ),
        ("graphDigest", hash(graph, col)?),
        ("configDigest", config_digest),
        ("sources", J::Array(sources)),
        (
            "counts",
            obj(vec![
                ("entities", index(list(graph, "entities")?.len())),
                ("mappings", index(list(graph, "mappings")?.len())),
                ("authorities", index(list(graph, "authorities")?.len())),
            ]),
        ),
    ]))
}
fn unconfigured(config: &J, graph: &J, configured: &[J]) -> Result<Vec<J>, LegacyWorkspaceError> {
    let severity = fallback(
        property(config, &["policy", "unconfiguredStructures"]),
        &scalar("ignore"),
    )
    .clone();
    if severity.string() == Some("ignore") {
        return Ok(Vec::new());
    }
    let ids: HashSet<&str> = configured.iter().filter_map(J::string).collect();
    let mut groups: Vec<(String, Vec<&J>)> = Vec::new();
    let mut slots = HashMap::new();
    for e in list(graph, "entities")? {
        let kind = property(e, &["attributes", "structureKind"]).and_then(J::string);
        if !matches!(kind, Some("model" | "schema" | "enum"))
            || matches!(
                property(e, &["attributes", "externalReference"]),
                Some(J::Bool(true))
            )
            || ids.contains(text(e, "id")?)
        {
            continue;
        }
        let sid = js_text(Some(fallback(
            property(e, &["attributes", "sourceId"]),
            &scalar("unknown"),
        )));
        let projected = Data::string_value(&sid.0)
            .string()
            .expect("source text")
            .to_owned();
        let slot = *slots.entry(projected.clone()).or_insert_with(|| {
            let i = groups.len();
            groups.push((projected, Vec::new()));
            i
        });
        groups[slot].1.push(e);
    }
    Ok(groups
        .into_iter()
        .map(|(sid, entities)| {
            let names = entities
                .iter()
                .take(12)
                .map(|e| js_text(property(e, &["attributes", "name"])))
                .collect::<Vec<_>>();
            let names = crate::legacy_reporting::LegacyReportText::join(&names, ", ");
            let mut units = Data::string_units(&sid);
            units.extend(
                format!(
                    " has {} structure(s) outside the configured vertical slice: ",
                    entities.len()
                )
                .encode_utf16(),
            );
            units.extend(names.0);
            if entities.len() > 12 {
                units.extend(", …".encode_utf16())
            }
            obj(vec![
                ("severity", severity.clone()),
                ("code", scalar("UNCONFIGURED_STRUCTURES")),
                ("message", Data::string_value(&units)),
                ("sourceId", J::String(sid)),
                ("fact", scalar("coverage")),
            ])
        })
        .collect())
}
fn pack_digest(pack: &J, locale: &str) -> Result<J, LegacyWorkspaceError> {
    let raw = raw(pack)?;
    let parsed = LegacyPackJson::parse(raw.into_bytes(), COMPATIBILITY_JSON_LIMITS)
        .map_err(|e| error("Error", &e.to_string()))?;
    let bytes = parsed
        .digest_bytes_for_locale(locale)
        .map_err(|e| error("Error", &e.to_string()))?;
    Ok(scalar(&byte_digest(&bytes)))
}
fn assemble(
    input: &J,
    col: &CollatorBorrowed<'_>,
    locale: &str,
) -> Result<J, LegacyWorkspaceError> {
    let config = get(input, "config")?;
    let adapters = list(input, "adapters")?;
    let configured = list(input, "configuredPacks")?;
    let config_digest = hash(config, col)?;
    let revision_sources = adapters
        .iter()
        .map(|a| {
            Ok(obj(vec![
                ("id", get(a, "sourceId")?.clone()),
                ("adapterVersion", get(a, "adapterVersion")?.clone()),
                ("inputs", get(a, "inputs")?.clone()),
            ]))
        })
        .collect::<Result<Vec<_>, LegacyWorkspaceError>>()?;
    let revision = hash(
        &obj(vec![
            ("configDigest", config_digest.clone()),
            ("sources", J::Array(revision_sources)),
        ]),
        col,
    )?;
    let docs = adapters
        .iter()
        .enumerate()
        .map(|(i, a)| {
            let value = get(a, "document")?.clone();
            let mut origins = HashMap::new();
            for field in ["relationPacks", "entities", "mappings", "authorities"] {
                if let Some(entries) = value.get(field).and_then(J::array) {
                    for j in 0..entries.len() {
                        origins.insert(
                            (field.into(), j),
                            vec![
                                path("adapters"),
                                index(i),
                                path("document"),
                                path(field),
                                index(j),
                            ],
                        );
                    }
                }
            }
            Ok(Document { value, origins })
        })
        .collect::<Result<Vec<_>, LegacyWorkspaceError>>()?;
    let id = text(config, "id")?;
    let namespace = get(config, "namespace")?.clone();
    let discovered = compose(
        &docs,
        obj(vec![
            ("id", J::String(format!("{id}:discovered"))),
            ("namespace", namespace.clone()),
            ("label", scalar("Observed repository structures")),
            ("revision", revision.clone()),
        ]),
        col,
    )?;
    let request = obj(vec![
        ("namespace", namespace.clone()),
        ("documentId", J::String(format!("{id}:declared"))),
        ("discovered", discovered.value.clone()),
        ("configurations", get(config, "correspondences")?.clone()),
        ("configRevision", config_digest.clone()),
    ]);
    let response = legacy_correspondence_request(LegacyCorrespondenceRequest {
        input: raw(&request)?,
    })
    .map_err(|e| error(&e.name, &e.message))?;
    let declared_response = parse(response.get())?;
    let mut declared = Document {
        value: get(&declared_response, "document")?.clone(),
        origins: HashMap::new(),
    };
    let core: Value = serde_json::from_str(include_str!(
        "../package-inputs/fixtures/reference/relation-packs/core.json"
    ))
    .expect("pinned core pack");
    let core_j = native(&core);
    let core_digest = pack_digest(&core_j, locale)?;
    if let Some(exact) = discovered
        .value
        .get("relationPacks")
        .and_then(J::array)
        .and_then(|entries| {
            entries.iter().find(|r| {
                r.get("id").and_then(J::string) == core["id"].as_str()
                    && r.get("version").and_then(J::string) == core["version"].as_str()
                    && r.get("digest").and_then(J::string) == core_digest.string()
            })
        })
    {
        let mut refs = list(&declared.value, "relationPacks")?.to_vec();
        for r in &mut refs {
            if r.get("id").and_then(J::string) == exact.get("id").and_then(J::string) {
                *r = exact.clone()
            }
        }
        set(&mut declared.value, "relationPacks", J::Array(refs));
    }
    // Keep generated record addresses so correspondence bindings and undefined
    // properties can be lifted into the final selected graph without heuristics.
    for field in ["entities", "mappings", "authorities"] {
        for j in 0..list(&declared.value, field)?.len() {
            declared.origins.insert(
                (field.into(), j),
                vec![path("declared"), path("document"), path(field), index(j)],
            );
        }
    }
    let mut graph = compose(
        &[discovered, declared],
        obj(vec![
            ("id", get(config, "id")?.clone()),
            ("namespace", namespace),
            (
                "label",
                fallback(config.get("label"), &scalar("Metamap")).clone(),
            ),
            ("revision", revision),
        ]),
        col,
    )?;
    let mut references = list(&graph.value, "relationPacks")?.to_vec();
    let portable = property(input, &["options", "portablePackUris"])
        .is_some_and(|v| matches!(v, J::Bool(true)));
    for configured in configured {
        let pack = get(configured, "pack")?;
        let pid = text(pack, "id")?;
        let version = get(pack, "version")?;
        let position = references
            .iter()
            .position(|r| r.get("id").and_then(J::string) == Some(pid));
        let digest = pack_digest(pack, locale)?;
        if let Some(i) = position {
            let existing = &references[i];
            if existing.get("version").and_then(J::string) != version.string() {
                return Err(error(
                    "Error",
                    &format!(
                        "Relation pack {pid} is referenced at both {} and {}",
                        text(existing, "version")?,
                        text(pack, "version")?
                    ),
                ));
            }
            if pack.get("schemaVersion").and_then(J::string) == Some("2.0.0")
                && existing.get("digest").and_then(J::string) != digest.string()
            {
                return Err(error(
                    "Error",
                    &format!(
                        "SOURCE_PACK_MISMATCH: Configured executable pack {pid} cannot replace a missing or different shard digest"
                    ),
                ));
            }
        }
        let mut reference = position
            .map(|i| references[i].clone())
            .unwrap_or_else(|| obj(Vec::new()));
        set(&mut reference, "id", get(pack, "id")?.clone());
        set(&mut reference, "version", version.clone());
        let configured_path = get(configured, "configuredPath")?;
        let uri = if portable || pack.get("schemaVersion").and_then(J::string) == Some("2.0.0") {
            let encoded = component(&Data::string_units(text(configured, "configuredPath")?))
                .map_err(|e| error(&e.name, &e.message))?;
            scalar(&format!("repo:{encoded}"))
        } else {
            configured_path.clone()
        };
        set(&mut reference, "uri", uri);
        set(&mut reference, "digest", digest);
        if let Some(i) = position {
            references[i] = reference;
            graph.origins.remove(&("relationPacks".into(), i));
        } else {
            references.push(reference)
        }
    }
    let mut ranked: Vec<(usize, J)> = references.into_iter().enumerate().collect();
    ranked.sort_by(|a, b| {
        col.compare_legacy_utf16(
            &Data::string_units(a.1.get("id").and_then(J::string).expect("reference id")),
            &Data::string_units(b.1.get("id").and_then(J::string).expect("reference id")),
        )
    });
    let mut origins = graph.origins.clone();
    origins.retain(|(f, _), _| f != "relationPacks");
    for (out, (previous, _)) in ranked.iter().enumerate() {
        if let Some(p) = graph.origins.get(&("relationPacks".into(), *previous)) {
            origins.insert(("relationPacks".into(), out), p.clone());
        }
    }
    graph.origins = origins;
    set(
        &mut graph.value,
        "relationPacks",
        J::Array(ranked.into_iter().map(|(_, r)| r).collect()),
    );
    let mut drift = list(&declared_response, "issues")?.to_vec();
    drift.extend(unconfigured(
        config,
        &graph.value,
        list(&declared_response, "configuredStructureIds")?,
    )?);
    let registry: LegacyGraphRegistry =
        serde_json::from_value(projection(get(input, "registry")?)?)
            .map_err(|e| error("Error", &e.to_string()))?;
    let validation = native(validate_legacy_document(
        &projection(&graph.value)?,
        &registry,
    ));
    let snap = snapshot(&graph.value, adapters, config_digest, col)?;
    let result = obj(vec![
        ("graph", graph.value),
        ("adapters", J::Array(adapters.to_vec())),
        ("driftIssues", J::Array(drift)),
        ("validation", validation),
        ("snapshot", snap),
        ("cacheHits", J::Array(Vec::new())),
    ]);
    let mut bindings = Vec::new();
    for i in 0..adapters.len() {
        bindings.push(binding(
            vec![path("adapters"), index(i)],
            vec![path("adapters"), index(i)],
        ));
        bindings.push(binding(
            vec![path("snapshot"), path("sources"), index(i), path("inputs")],
            vec![path("adapters"), index(i), path("inputs")],
        ));
    }
    for ((field, i), origin) in graph.origins {
        bindings.push(binding(vec![path("graph"), path(&field), index(i)], origin));
    }
    Ok(obj(vec![
        ("value", result),
        ("bindings", J::Array(bindings)),
        ("declared", declared_response),
    ]))
}
pub(crate) fn has_errors(value: &J) -> Result<bool, LegacyWorkspaceError> {
    if !truthy(property(value, &["validation", "valid"])) {
        return Ok(true);
    }
    for adapter in list(value, "adapters")? {
        if list(adapter, "diagnostics")?
            .iter()
            .any(|d| d.get("severity").and_then(J::string) == Some("error"))
        {
            return Ok(true);
        }
    }
    Ok(list(value, "driftIssues")?
        .iter()
        .any(|i| i.get("severity").and_then(J::string) == Some("error")))
}
/// Native semantic operations; filesystem requests are handled by the workspace crate.
pub fn legacy_workspace_request(
    request: LegacyWorkspaceRequest,
) -> Result<Box<RawValue>, LegacyWorkspaceError> {
    let input = parse(&request.input)?;
    let col = locale(&request.locale)?;
    let result = match request.operation.as_str() {
        "assemble" => assemble(&input, &col, &request.locale)?,
        "snapshot" => {
            let adapters = list(&input, "adapters")?;
            obj(vec![
                (
                    "value",
                    snapshot(
                        get(&input, "graph")?,
                        adapters,
                        get(&input, "configDigest")?.clone(),
                        &col,
                    )?,
                ),
                (
                    "bindings",
                    J::Array(
                        (0..adapters.len())
                            .map(|i| {
                                binding(
                                    vec![path("sources"), index(i), path("inputs")],
                                    vec![path("adapters"), index(i), path("inputs")],
                                )
                            })
                            .collect(),
                    ),
                ),
            ])
        }
        "has-errors" => J::Bool(has_errors(get(&input, "discovery")?)?),
        "adapter-registry" => {
            let ids = list(&input, "ids")?;
            let id = input.get("id");
            let found = ids
                .iter()
                .position(|v| v.string() == id.and_then(J::string));
            match text(&input, "action")? {
                "register" => {
                    if found.is_some() {
                        return Err(error(
                            "Error",
                            &format!("Adapter {} is already registered", text(&input, "id")?),
                        ));
                    }
                    J::Null
                }
                "get" => found.map(index).unwrap_or(J::Null),
                "ids" => {
                    let mut ids = ids.to_vec();
                    ids.sort_by(|a, b| {
                        Data::string_units(a.string().expect("adapter id"))
                            .cmp(&Data::string_units(b.string().expect("adapter id")))
                    });
                    J::Array(ids)
                }
                "require" => {
                    if let Some(i) = found {
                        index(i)
                    } else {
                        let mut ids = ids.iter().filter_map(J::string).collect::<Vec<_>>();
                        ids.sort_by_key(|s| Data::string_units(s));
                        let suffix = if ids.is_empty() {
                            String::new()
                        } else {
                            format!("; available adapters: {}", ids.join(", "))
                        };
                        return Err(error(
                            "Error",
                            &format!("Adapter {} is not registered{suffix}", text(&input, "id")?),
                        ));
                    }
                }
                _ => return Err(error("Error", "Unknown adapter registry operation")),
            }
        }
        "cache-key" => {
            let source = get(&input, "config")?;
            let units = Data::string_units(text(source, "id")?);
            let safe = units
                .into_iter()
                .map(|u| {
                    if matches!(u,65..=90|97..=122|48..=57|46|95|45) {
                        char::from_u32(u as u32).expect("ASCII")
                    } else {
                        '_'
                    }
                })
                .collect::<String>();
            let value = obj(vec![
                ("adapter", get(&input, "adapter")?.clone()),
                ("adapterVersion", get(&input, "adapterVersion")?.clone()),
                ("config", source.clone()),
                ("inputs", get(&input, "inputs")?.clone()),
            ]);
            obj(vec![
                ("key", hash(&value, &col)?),
                ("filename", scalar(&format!("{safe}.json"))),
            ])
        }
        "cache-check" => {
            let cached = input.get("cached");
            let hit = cached.is_some_and(|c| {
                c.get("cacheVersion").and_then(J::string) == Some("1.0.0")
                    && c.get("key").and_then(J::string) == input.get("key").and_then(J::string)
                    && c.get("result").is_some()
            });
            let mut response = obj(vec![("hit", J::Bool(hit))]);
            if hit {
                set(
                    &mut response,
                    "result",
                    get(cached.expect("cache hit"), "result")?.clone(),
                )
            }
            response
        }
        "cache-entry" => pretty(
            &obj(vec![
                ("cacheVersion", scalar("1.0.0")),
                ("key", get(&input, "key")?.clone()),
                ("result", get(&input, "result")?.clone()),
            ]),
            &col,
        )?,
        "check" => {
            let current = get(&input, "current")?;
            let baseline = input.get("baseline").filter(|v| truthy(Some(v)));
            let registry: LegacyGraphRegistry =
                serde_json::from_value(projection(get(&input, "registry")?)?)
                    .map_err(|e| error("Error", &e.to_string()))?;
            let valid = baseline.filter(|b| {
                projection(b).is_ok_and(|v| validate_legacy_document(&v, &registry).valid)
            });
            let diff = legacy_reporting_request(LegacyReportingRequest {
                locale: request.locale.clone(),
                action: if let Some(b) = valid {
                    LegacyReportingAction::Diff {
                        before: raw(b)?,
                        after: raw(get(current, "graph")?)?,
                    }
                } else {
                    LegacyReportingAction::EmptyDiff
                },
            })
            .map_err(|e| error(&e.name, &e.message))?;
            let diff = observed(diff);
            let severity = fallback(
                property(&input, &["config", "policy", "baselineChanges"]),
                &scalar("error"),
            )
            .clone();
            let mut issues = list(current, "driftIssues")?.to_vec();
            if valid.is_none() {
                issues.push(obj(vec![
                    ("severity", scalar("error")),
                    ("code", scalar("BASELINE_MISSING_OR_INVALID")),
                    (
                        "message",
                        J::String(format!(
                            "{} is missing or invalid; run metamap generate",
                            text(get(get(&input, "config")?, "outputs")?, "graph")?
                        )),
                    ),
                ]))
            } else if !list(&diff, "changes")?.is_empty() && severity.string() != Some("ignore") {
                issues.push(obj(vec![
                    ("severity", severity.clone()),
                    ("code", scalar("BASELINE_DRIFT")),
                    (
                        "message",
                        scalar(&format!(
                            "{} graph record(s) differ from the committed baseline",
                            list(&diff, "changes")?.len()
                        )),
                    ),
                ]))
            }
            let mut result = current.clone();
            set(&mut result, "driftIssues", J::Array(issues));
            if let Some(b) = valid {
                set(&mut result, "baseline", b.clone())
            }
            set(&mut result, "diff", diff);
            set(&mut result, "baselineSeverity", severity);
            obj(vec![
                ("value", result),
                ("baselinePresent", J::Bool(valid.is_some())),
            ])
        }
        "outputs" => {
            let discovery = get(&input, "discovery")?;
            let mut reporting = discovery.clone();
            set(&mut reporting, "cacheHits", J::Array(Vec::new()));
            set(
                &mut reporting,
                "diff",
                native(crate::legacy_reporting::LegacyGraphDiff::default()),
            );
            let report = legacy_reporting_request(LegacyReportingRequest {
                locale: request.locale.clone(),
                action: LegacyReportingAction::DriftReport {
                    input: raw(&reporting)?,
                },
            })
            .map_err(|e| error(&e.name, &e.message))?;
            let doc = legacy_reporting_request(LegacyReportingRequest {
                locale: request.locale.clone(),
                action: LegacyReportingAction::GraphDocumentation {
                    graph: raw(get(discovery, "graph")?)?,
                    correspondences: raw(get(get(&input, "config")?, "correspondences")?)?,
                },
            })
            .map_err(|e| error(&e.name, &e.message))?;
            obj(vec![
                ("graph", pretty(get(discovery, "graph")?, &col)?),
                ("snapshot", pretty(get(discovery, "snapshot")?, &col)?),
                ("report", observed(report)),
                ("documentation", observed(doc)),
            ])
        }
        _ => return Err(error("Error", "Unknown workspace semantic operation")),
    };
    Data::json_raw(&result).map_err(|e| error("Error", &e.to_string()))
}
