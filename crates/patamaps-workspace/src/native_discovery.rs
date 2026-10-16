//! Bounded native observations over explicitly nonsecret captured inputs.
//! Syntax and Cargo metadata are facts about sources/tools, not admission or execution evidence.
use crate::{
    AdapterRequest, AdapterResponse, Error, InputReceipt, PROFILE, ResponseType, process,
    relative_path,
};
use patamaps_contracts::{
    GraphDocument, MAX_INPUT_BYTES, ProtocolVersion, SafeInteger, byte_digest, canonical_digest,
    parse,
};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::Read,
    path::{Path, PathBuf},
};
use toml_edit::{Document, Item, Table, Value as TomlValue};

const VERSION: &str = "patamaps-native-observations-1";
const NODE_LIMIT: usize = 10_000;
const OBSERVATION_BYTES: usize = 8 * 1024 * 1024;
struct TomlNodes {
    values: Vec<Value>,
    encoded_bytes: usize,
}

type Inputs<'a> = BTreeMap<&'a str, &'a str>;

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct TomlSelection {
    path: String,
    /// Explicit key prefixes; an empty path selects the whole declared nonsecret document.
    fields: Vec<Vec<String>>,
}
#[derive(Deserialize)]
#[serde(
    tag = "provider",
    rename_all = "kebab-case",
    rename_all_fields = "camelCase",
    deny_unknown_fields
)]
enum Config {
    Toml {
        nonsecret_inputs: bool,
        files: Vec<TomlSelection>,
    },
    Files {
        nonsecret_inputs: bool,
    },
    Cargo(Box<CargoConfig>),
    Dockerfile(Box<crate::native_docker::DockerConfig>),
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct CargoConfig {
    nonsecret_inputs: bool,
    manifest: String,
    workspace_manifest: String,
    #[serde(default)]
    root_mode: CargoRootMode,
    lockfile: String,
    cargo: String,
    cargo_digest: String,
    rustc: String,
    rustc_digest: String,
    cargo_home: String,
    platform: String,
    features: Vec<String>,
    default_features: bool,
    view: DependencyView,
}

#[derive(Clone, Copy, Default, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
enum CargoRootMode {
    #[default]
    ExplicitWorkspace,
    StandalonePackage,
}

/// Standalone packages are opt-in. Probe ancestor manifest existence without
/// reading its bytes: Cargo must never discover an undeclared parent workspace.
fn validate_cargo_root(
    mode: CargoRootMode,
    manifest: &Path,
    workspace: &Path,
    declared: &Document<String>,
) -> Result<(), Error> {
    let has_workspace = declared
        .get("workspace")
        .and_then(Item::as_table_like)
        .is_some();
    if mode == CargoRootMode::ExplicitWorkspace {
        if !has_workspace {
            return Err(refused(
                "NATIVE_CARGO_ROOT_ISOLATION",
                "The declared workspace manifest must explicitly contain [workspace]",
            ));
        }
        return Ok(());
    }
    if manifest != workspace
        || has_workspace
        || declared
            .get("package")
            .and_then(Item::as_table_like)
            .is_none()
        || declared
            .get("package")
            .and_then(Item::as_table_like)
            .is_some_and(|p| p.get("workspace").is_some())
    {
        return Err(refused(
            "NATIVE_CARGO_ROOT_ISOLATION",
            "Standalone mode requires the same explicit package/root manifest without workspace selection",
        ));
    }
    let directory = workspace.parent().expect("manifest parent");
    for ancestor in directory.ancestors().skip(1) {
        match fs::symlink_metadata(ancestor.join("Cargo.toml")) {
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            _ => {
                return Err(refused(
                    "NATIVE_CARGO_ROOT_ISOLATION",
                    "Standalone mode refuses any ancestor Cargo manifest or unavailable ancestor probe; its values were not read",
                ));
            }
        }
    }
    Ok(())
}

#[derive(Clone, Copy, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
enum DependencyView {
    DeclaredLocal,
    Resolved,
}

fn refused(code: &'static str, message: impl Into<String>) -> Error {
    Error::refused(code, message)
}
fn span(range: Option<std::ops::Range<usize>>) -> Value {
    range.map_or(Value::Null, |v| json!([v.start, v.end]))
}
fn node(
    path: &[Value],
    key_span: Value,
    range: Option<std::ops::Range<usize>>,
    value: Value,
    raw: &str,
) -> Value {
    // Container syntax is retained in the raw input; duplicating whole nested
    // subtrees would amplify a bounded source into unbounded observation text.
    let container = matches!(
        value.get("type").and_then(Value::as_str),
        Some("table" | "inline-table" | "array" | "array-of-tables")
    );
    let lexeme = if container {
        None
    } else {
        range.clone().and_then(|v| raw.get(v)).map(str::to_owned)
    };
    json!({"key":path,"keySpan":key_span,"valueSpan":span(range),"lexeme":lexeme,"value":value})
}
fn push(nodes: &mut TomlNodes, value: Value, depth: usize) -> Result<(), Error> {
    if depth > 64 || nodes.values.len() >= NODE_LIMIT {
        return Err(refused(
            "NATIVE_TOML_LIMIT",
            "TOML nesting or node bound exceeded",
        ));
    }
    let encoded = serde_json::to_vec(&value)
        .map_err(|error| refused("NATIVE_TOML_LIMIT", error.to_string()))?;
    nodes.encoded_bytes = nodes.encoded_bytes.saturating_add(encoded.len());
    if nodes.encoded_bytes > OBSERVATION_BYTES {
        return Err(refused(
            "NATIVE_TOML_LIMIT",
            "Aggregate TOML observation budget exceeded",
        ));
    }
    nodes.values.push(value);
    Ok(())
}
fn table_nodes(
    table: &Table,
    raw: &str,
    path: &mut Vec<Value>,
    key_span: Value,
    nodes: &mut TomlNodes,
    depth: usize,
) -> Result<(), Error> {
    push(
        nodes,
        node(
            path,
            key_span,
            table.span(),
            json!({"type":"table","keys":table.iter().map(|(k,_)| k).collect::<Vec<_>>()}),
            raw,
        ),
        depth,
    )?;
    for (key, item) in table.iter() {
        path.push(json!(key));
        let key_span = span(table.key(key).and_then(|k| k.span()));
        item_nodes(item, raw, path, key_span, nodes, depth + 1)?;
        path.pop();
    }
    Ok(())
}
fn item_nodes(
    item: &Item,
    raw: &str,
    path: &mut Vec<Value>,
    key_span: Value,
    nodes: &mut TomlNodes,
    depth: usize,
) -> Result<(), Error> {
    match item {
        Item::Value(value) => value_nodes(value, raw, path, key_span, nodes, depth),
        Item::Table(table) => table_nodes(table, raw, path, key_span, nodes, depth),
        Item::ArrayOfTables(tables) => {
            push(
                nodes,
                node(
                    path,
                    key_span,
                    tables.span(),
                    json!({"type":"array-of-tables","length":tables.len()}),
                    raw,
                ),
                depth,
            )?;
            for (i, table) in tables.iter().enumerate() {
                path.push(json!(i));
                table_nodes(table, raw, path, Value::Null, nodes, depth + 1)?;
                path.pop();
            }
            Ok(())
        }
        Item::None => Err(refused("NATIVE_TOML_VALUE", "Unavailable parser item")),
    }
}
fn value_nodes(
    value: &TomlValue,
    raw: &str,
    path: &mut Vec<Value>,
    key_span: Value,
    nodes: &mut TomlNodes,
    depth: usize,
) -> Result<(), Error> {
    let typed = match value {
        TomlValue::String(v) => json!({"type":"string","value":v.value()}),
        TomlValue::Integer(v) => json!({"type":"integer","decimal":v.value().to_string()}),
        TomlValue::Float(v) => {
            json!({"type":"float","ieee754Bits":format!("{:016x}",v.value().to_bits())})
        }
        TomlValue::Boolean(v) => json!({"type":"boolean","value":v.value()}),
        TomlValue::Datetime(v) => json!({"type":"datetime","canonical":v.value().to_string()}),
        TomlValue::Array(v) => json!({"type":"array","length":v.len()}),
        TomlValue::InlineTable(v) => {
            json!({"type":"inline-table","keys":v.iter().map(|(k,_)| k).collect::<Vec<_>>()})
        }
    };
    push(nodes, node(path, key_span, value.span(), typed, raw), depth)?;
    match value {
        TomlValue::Array(values) => {
            for (i, value) in values.iter().enumerate() {
                path.push(json!(i));
                value_nodes(value, raw, path, Value::Null, nodes, depth + 1)?;
                path.pop();
            }
        }
        TomlValue::InlineTable(values) => {
            for (key, value) in values.iter() {
                path.push(json!(key));
                value_nodes(
                    value,
                    raw,
                    path,
                    span(values.key(key).and_then(|v| v.span())),
                    nodes,
                    depth + 1,
                )?;
                path.pop();
            }
        }
        _ => {}
    }
    Ok(())
}
fn parse_toml(path: &str, raw: &str) -> Result<Document<String>, Error> {
    Document::parse(raw.to_owned())
        .map_err(|e| refused("NATIVE_TOML_SYNTAX", format!("{path}: {e}")))
}
fn entity(id: String, kind: &str, path: &str, attributes: Value) -> Value {
    json!({"id":id,"kind":kind,"locators":[{"uri":format!("workspace:{path}")}],"attributes":attributes})
}
pub(super) fn physical_id(namespace: &str, kind: &str, identity: &Value) -> Result<String, Error> {
    Ok(format!(
        "urn:patamaps:observed:{kind}:{}",
        canonical_digest(&json!([namespace, identity]))?
    ))
}
fn toml_entities(
    namespace: &str,
    inputs: &Inputs<'_>,
    selections: &[TomlSelection],
) -> Result<(Vec<Value>, usize), Error> {
    if selections.is_empty() || selections.len() > 1024 {
        return Err(refused(
            "NATIVE_TOML_SELECTION",
            "Select bounded explicit nonsecret files",
        ));
    }
    let mut entities = Vec::new();
    let mut seen = BTreeSet::new();
    let mut excluded = 0;
    let mut encoded_bytes = 0;
    for selection in selections {
        if !seen.insert(&selection.path)
            || selection.fields.is_empty()
            || selection.fields.len() > 256
        {
            return Err(refused(
                "NATIVE_TOML_SELECTION",
                "Select unique files and nonempty explicit field selections",
            ));
        }
        let raw = inputs
            .get(selection.path.as_str())
            .ok_or_else(|| refused("NATIVE_INPUT_UNAVAILABLE", &selection.path))?;
        let document = parse_toml(&selection.path, raw)?;
        let mut nodes = TomlNodes {
            values: Vec::new(),
            encoded_bytes,
        };
        table_nodes(
            document.as_table(),
            raw,
            &mut Vec::new(),
            Value::Null,
            &mut nodes,
            0,
        )?;
        encoded_bytes = nodes.encoded_bytes;
        for field in &selection.fields {
            if !nodes.values.iter().any(|n| n["key"] == json!(field)) {
                return Err(refused(
                    "NATIVE_TOML_FIELD",
                    format!("{}: required field {field:?} unavailable", selection.path),
                ));
            }
        }
        for n in nodes.values {
            let key = n["key"].as_array().expect("constructed key");
            if !selection.fields.iter().any(|prefix| {
                key.len() >= prefix.len()
                    && prefix.iter().zip(key).all(|(a, b)| b.as_str() == Some(a))
            }) {
                excluded += 1;
                continue;
            }
            if entities.len() >= NODE_LIMIT {
                return Err(refused(
                    "NATIVE_TOML_LIMIT",
                    "Combined selected node bound exceeded",
                ));
            }
            let id = physical_id(namespace, "toml-key", &json!([selection.path, key]))?;
            entities.push(entity(
                id,
                "toml-key",
                &selection.path,
                json!({"path":selection.path,"evidenceClass":"observed-syntax","observation":n}),
            ));
        }
    }
    Ok((entities, excluded))
}
fn live_path(root: &Path, path: &str) -> Result<PathBuf, Error> {
    if !relative_path(path) {
        return Err(refused(
            "NATIVE_SOURCE_PATH",
            "Expected normalized owner-relative path",
        ));
    }
    let p = fs::canonicalize(root.join(path))?;
    if !p.starts_with(root) || !p.is_file() {
        return Err(refused("NATIVE_SOURCE_ESCAPE", path));
    }
    Ok(p)
}
fn same_sources(root: &Path, inputs: &Inputs<'_>) -> Result<(), Error> {
    for (name, raw) in inputs {
        let p = live_path(root, name)?;
        let mut bytes = Vec::new();
        fs::File::open(p)?
            .take((MAX_INPUT_BYTES + 1) as u64)
            .read_to_end(&mut bytes)?;
        if bytes != raw.as_bytes() {
            return Err(refused("NATIVE_SOURCE_CHANGED", *name));
        }
    }
    Ok(())
}
fn tool_digest(path: &str) -> Result<(PathBuf, String), Error> {
    if !Path::new(path).is_absolute() {
        return Err(refused("NATIVE_TOOL_PATH", "Tool paths must be absolute"));
    }
    let path = fs::canonicalize(path)?;
    if path.to_str().is_none() {
        return Err(refused("NATIVE_TOOL_PATH", "Tool path is not UTF-8"));
    }
    let digest = crate::hash_executable(&path).map_err(|error|
        refused("NATIVE_CARGO_TOOL_REFUSED",format!("Selected tool must satisfy the existing bounded regular-file executable contract: {error}")))?;
    Ok((path, digest))
}

fn config_inputs(
    root: &Path,
    manifest: &Path,
    cargo_home: &Path,
    inputs: &Inputs<'_>,
    platform: &str,
) -> Result<Vec<String>, Error> {
    let mut found = Vec::new();
    let mut dirs = manifest
        .parent()
        .expect("manifest parent")
        .ancestors()
        .map(Path::to_path_buf)
        .collect::<Vec<_>>();
    dirs.push(cargo_home.to_path_buf());
    let mut selected_toolchain = false;
    for dir in dirs {
        let prefix = if dir == cargo_home {
            dir.clone()
        } else {
            dir.join(".cargo")
        };
        let configs = [prefix.join("config"), prefix.join("config.toml")];
        if configs.iter().all(|p| p.exists()) {
            return Err(refused(
                "NATIVE_CARGO_CONFIG",
                "Ambiguous legacy and TOML Cargo configuration",
            ));
        }
        let mut paths = configs.to_vec();
        // Cargo configuration accumulates along the ancestor chain. Rustup
        // toolchain selection uses only the nearest file and shadows ancestors.
        if dir != cargo_home && !selected_toolchain {
            let toolchain_files = [dir.join("rust-toolchain"), dir.join("rust-toolchain.toml")];
            if toolchain_files.iter().all(|p| p.exists()) {
                return Err(refused(
                    "NATIVE_CARGO_TOOLCHAIN",
                    "Ambiguous toolchain files",
                ));
            }
            if toolchain_files.iter().any(|p| p.exists()) {
                selected_toolchain = true;
                paths.extend(toolchain_files);
            }
        }
        for p in paths.into_iter().filter(|p| p.exists()) {
            let actual = fs::canonicalize(&p)?;
            if !actual.starts_with(root) {
                return Err(refused(
                    "NATIVE_CARGO_AMBIENT_CONFIG",
                    "Cargo/toolchain configuration outside declared owner root is unavailable; no values captured",
                ));
            }
            let relative = actual
                .strip_prefix(root)
                .expect("contained")
                .to_str()
                .ok_or_else(|| refused("NATIVE_SOURCE_UTF8", "Filesystem paths must be UTF-8"))?
                .replace('\\', "/");
            let raw = inputs.get(relative.as_str()).ok_or_else(|| {
                refused(
                    "NATIVE_CARGO_CONFIG_INPUT",
                    format!("Configuration not captured: {relative}"),
                )
            })?;
            if p.file_name().and_then(|p| p.to_str()) == Some("rust-toolchain") {
                if raw.trim().is_empty() || raw.lines().count() != 1 {
                    return Err(refused(
                        "NATIVE_CARGO_TOOLCHAIN",
                        "Unsupported legacy toolchain file",
                    ));
                }
            } else {
                let document = parse_toml(&relative, raw)?;
                if p.file_name().and_then(|p| p.to_str()) != Some("rust-toolchain.toml") {
                    // Refuse executable overrides and unimplemented config rather than inheriting them invisibly.
                    for (key, value) in document.iter() {
                        let table = value.as_table_like().ok_or_else(|| {
                            refused("NATIVE_CARGO_CONFIG", "Unsupported Cargo configuration")
                        })?;
                        for (setting, value) in table.iter() {
                            let allowed = match (key, setting) {
                                ("build", "target") => value.as_str() == Some(platform),
                                ("net", "offline") => value.as_bool() == Some(true),
                                _ => false,
                            };
                            if !allowed {
                                return Err(refused(
                                    "NATIVE_CARGO_CONFIG",
                                    format!(
                                        "Unsupported required Cargo configuration key: {key}.{setting}"
                                    ),
                                ));
                            }
                        }
                    }
                } else {
                    let table = document
                        .get("toolchain")
                        .and_then(Item::as_table_like)
                        .ok_or_else(|| {
                            refused("NATIVE_CARGO_TOOLCHAIN", "Missing toolchain table")
                        })?;
                    if table
                        .iter()
                        .any(|(k, _)| !["channel", "components", "targets", "profile"].contains(&k))
                    {
                        return Err(refused(
                            "NATIVE_CARGO_TOOLCHAIN",
                            "Unsupported toolchain selection",
                        ));
                    }
                }
            }
            found.push(relative);
        }
    }
    found.sort();
    found.dedup();
    Ok(found)
}
fn validate_manifest_paths(root: &Path, inputs: &Inputs<'_>) -> Result<(), Error> {
    fn required(
        root: &Path,
        base: &Path,
        value: &str,
        inputs: &Inputs<'_>,
        append: &str,
    ) -> Result<(), Error> {
        let path = base.join(value).join(append);
        let canonical = fs::canonicalize(path)?;
        if !canonical.starts_with(root) {
            return Err(refused(
                "NATIVE_CARGO_PATH_ESCAPE",
                "Manifest dependency/member escapes declared owner root",
            ));
        }
        let relative = canonical
            .strip_prefix(root)
            .expect("contained")
            .to_str()
            .ok_or_else(|| refused("NATIVE_SOURCE_UTF8", "Filesystem paths must be UTF-8"))?
            .replace('\\', "/");
        if !inputs.contains_key(relative.as_str()) {
            return Err(refused(
                "NATIVE_CARGO_MANIFEST_INPUT",
                format!("Required manifest not captured: {relative}"),
            ));
        }
        Ok(())
    }
    fn dependencies(
        root: &Path,
        base: &Path,
        table: &dyn toml_edit::TableLike,
        inputs: &Inputs<'_>,
    ) -> Result<(), Error> {
        for (key, item) in table.iter() {
            if let Some(nested) = item.as_table_like() {
                if ["dependencies", "dev-dependencies", "build-dependencies"].contains(&key) {
                    for (_, dep) in nested.iter() {
                        if let Some(path) = dep
                            .as_table_like()
                            .and_then(|v| v.get("path"))
                            .and_then(Item::as_str)
                        {
                            required(root, base, path, inputs, "Cargo.toml")?;
                        }
                    }
                } else if key != "metadata" {
                    dependencies(root, base, nested, inputs)?;
                }
            }
        }
        Ok(())
    }
    for (path, raw) in inputs.iter().filter(|(p, _)| p.ends_with("Cargo.toml")) {
        let document = parse_toml(path, raw)?;
        let base = root
            .join(path)
            .parent()
            .expect("manifest parent")
            .to_path_buf();
        if let Some(workspace) = document.get("workspace").and_then(Item::as_table_like)
            && let Some(members) = workspace.get("members").and_then(Item::as_array)
        {
            for member in members {
                let value = member
                    .as_str()
                    .ok_or_else(|| refused("NATIVE_CARGO_MEMBERS", "Member is not a string"))?;
                if value.contains(['*', '?', '[', ']', '{', '}']) {
                    return Err(refused(
                        "NATIVE_CARGO_MEMBERS",
                        "Glob workspace members are unsupported in this profile",
                    ));
                }
                required(root, &base, value, inputs, "Cargo.toml")?;
            }
        }
        if let Some(value) = document
            .get("package")
            .and_then(Item::as_table_like)
            .and_then(|p| p.get("workspace"))
            .and_then(Item::as_str)
        {
            required(root, &base, value, inputs, "Cargo.toml")?;
        }
        dependencies(root, &base, document.as_table(), inputs)?;
    }
    Ok(())
}
fn tool(
    invocation: &crate::Invocation,
    path: &Path,
    root: &Path,
    args: &[String],
    env: &[(&str, &str)],
    limit: u64,
) -> Result<Vec<u8>, Error> {
    let call = crate::Invocation {
        executable: path
            .to_str()
            .ok_or_else(|| refused("NATIVE_SOURCE_UTF8", "Filesystem paths must be UTF-8"))?
            .into(),
        arguments: args.to_vec(),
        code_inputs: Vec::new(),
        bounds: crate::ProcessBounds {
            maximum_elapsed_ms: invocation.bounds.maximum_elapsed_ms,
            maximum_stdout_bytes: SafeInteger::new(limit).expect("bounded output"),
            maximum_stderr_bytes: SafeInteger::new(65536).expect("bounded diagnostics"),
        },
    };
    let (out, _) = process::invoke_tool(&call, path, root, &[], env).map_err(|error| {
        match error {
            Error::Refused {code: "ADAPTER_EXIT", ..} => refused("NATIVE_CARGO_UNAVAILABLE",
                format!("Offline locked Cargo/tool observation unavailable at stage {:?}; no resolution/compilation established", args.first())),
            other => other,
        }
    })?;
    Ok(out)
}
fn cargo_entities(
    request: &AdapterRequest,
    inputs: &Inputs<'_>,
    root: &Path,
    config: &CargoConfig,
) -> Result<(Vec<Value>, Value), Error> {
    let manifest = config.manifest.as_str();
    let workspace_manifest = config.workspace_manifest.as_str();
    let lockfile = config.lockfile.as_str();
    let cargo = config.cargo.as_str();
    let cargo_digest = config.cargo_digest.as_str();
    let rustc = config.rustc.as_str();
    let rustc_digest = config.rustc_digest.as_str();
    let cargo_home = config.cargo_home.as_str();
    let platform = config.platform.as_str();
    let features = config.features.as_slice();
    let default_features = config.default_features;
    let view = config.view;
    for path in [manifest, workspace_manifest, lockfile] {
        if !inputs.contains_key(path) {
            return Err(refused(
                "NATIVE_CARGO_INPUT",
                format!("Required captured input unavailable: {path}"),
            ));
        }
    }
    if features.len() > 64
        || features.iter().any(|v| {
            v.is_empty()
                || v.len() > 128
                || !v
                    .chars()
                    .all(|c| c.is_ascii_alphanumeric() || "_-/".contains(c))
        })
        || platform.is_empty()
        || platform.len() > 128
        || !platform
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || "-_.".contains(c))
    {
        return Err(refused(
            "NATIVE_CARGO_CONTEXT",
            "Invalid feature/platform context",
        ));
    }
    parse_toml(lockfile, inputs[lockfile])?;
    let manifest_path = live_path(root, manifest)?;
    let workspace_path = live_path(root, workspace_manifest)?;
    let workspace_root = workspace_path.parent().expect("manifest parent");
    let declared = parse_toml(workspace_manifest, inputs[workspace_manifest])?;
    validate_cargo_root(config.root_mode, &manifest_path, &workspace_path, &declared)?;

    if live_path(root, lockfile)? != workspace_root.join("Cargo.lock") {
        return Err(refused(
            "NATIVE_CARGO_LOCK",
            "Lockfile does not belong to declared workspace root",
        ));
    }
    let cargo_home = Path::new(cargo_home);
    if !cargo_home.is_absolute() || !cargo_home.is_dir() {
        return Err(refused(
            "NATIVE_CARGO_HOME",
            "Configure an existing absolute Cargo home",
        ));
    }
    same_sources(root, inputs)?;
    validate_manifest_paths(root, inputs)?;
    let configs = config_inputs(root, &manifest_path, cargo_home, inputs, platform)?;
    let (cargo_path, actual_cargo) = tool_digest(cargo)?;
    let (rustc_path, actual_rustc) = tool_digest(rustc)?;
    if actual_cargo != cargo_digest || actual_rustc != rustc_digest {
        return Err(refused(
            "NATIVE_CARGO_TOOL_CHANGED",
            "Cargo/rustc bytes differ from declared identities",
        ));
    }
    let cargo_home = cargo_home
        .to_str()
        .ok_or_else(|| refused("NATIVE_SOURCE_UTF8", "Filesystem paths must be UTF-8"))?
        .to_owned();
    let rustc_text = rustc_path
        .to_str()
        .ok_or_else(|| refused("NATIVE_SOURCE_UTF8", "Filesystem paths must be UTF-8"))?
        .to_owned();
    let search = format!(
        "{}:/usr/bin:/bin",
        rustc_path.parent().expect("tool parent").display()
    );
    let env = [
        ("CARGO_HOME", cargo_home.as_str()),
        ("RUSTC", rustc_text.as_str()),
        ("PATH", search.as_str()),
        ("CARGO_NET_OFFLINE", "true"),
    ];
    let invocation = crate::Invocation {
        executable: cargo.into(),
        arguments: Vec::new(),
        code_inputs: Vec::new(),
        bounds: crate::ProcessBounds {
            maximum_elapsed_ms: SafeInteger::new(30000).expect("bounded deadline"),
            maximum_stdout_bytes: SafeInteger::new(4 * 1024 * 1024).expect("bounded metadata"),
            maximum_stderr_bytes: SafeInteger::new(65536).expect("bounded diagnostics"),
        },
    };
    let cargo_version = tool(&invocation, &cargo_path, root, &["-Vv".into()], &env, 16384)?;
    let rustc_version = tool(&invocation, &rustc_path, root, &["-Vv".into()], &env, 16384)?;
    let version_text = std::str::from_utf8(&rustc_version)
        .map_err(|_| refused("NATIVE_TOOL_UTF8", "Rustc version output is not UTF-8"))?;
    let release = version_text
        .lines()
        .find_map(|line| line.strip_prefix("release: "))
        .ok_or_else(|| {
            refused(
                "NATIVE_CARGO_TOOLCHAIN",
                "Rustc release identity unavailable",
            )
        })?;
    for path in &configs {
        let channel = if path.ends_with("rust-toolchain.toml") {
            let document = parse_toml(path, inputs[path.as_str()])?;
            document
                .get("toolchain")
                .and_then(Item::as_table_like)
                .and_then(|v| v.get("channel"))
                .and_then(Item::as_str)
                .map(str::to_owned)
        } else if path.ends_with("rust-toolchain") {
            Some(inputs[path.as_str()].trim().to_owned())
        } else {
            None
        };
        if let Some(channel) = channel {
            if channel != release {
                return Err(refused(
                    "NATIVE_CARGO_TOOLCHAIN",
                    "Declared toolchain channel does not match the explicitly selected rustc release; unpinned aliases are unsupported",
                ));
            }
        } else if path.ends_with("rust-toolchain.toml") {
            return Err(refused(
                "NATIVE_CARGO_TOOLCHAIN",
                "A toolchain file requires an exact pinned channel in this profile",
            ));
        }
    }

    let mut args = vec![
        "metadata".into(),
        "--format-version".into(),
        "1".into(),
        "--locked".into(),
        "--offline".into(),
        "--manifest-path".into(),
        manifest_path
            .to_str()
            .ok_or_else(|| refused("NATIVE_SOURCE_UTF8", "Filesystem paths must be UTF-8"))?
            .into(),
        "--filter-platform".into(),
        platform.into(),
    ];
    if !default_features {
        args.push("--no-default-features".into());
    }
    if !features.is_empty() {
        args.extend(["--features".into(), features.join(",")]);
    }
    if view == DependencyView::DeclaredLocal {
        args.push("--no-deps".into());
    }
    let raw = tool(
        &invocation,
        &cargo_path,
        manifest_path.parent().expect("manifest parent"),
        &args,
        &env,
        4 * 1024 * 1024,
    )?;
    same_sources(root, inputs)?;
    validate_cargo_root(config.root_mode, &manifest_path, &workspace_path, &declared)?;
    if tool_digest(cargo)?.1 != actual_cargo || tool_digest(rustc)?.1 != actual_rustc {
        return Err(refused(
            "NATIVE_CARGO_TOOL_CHANGED",
            "Tool bytes changed during observation",
        ));
    }
    let metadata: Value = serde_json::from_slice(&raw)
        .map_err(|e| refused("NATIVE_CARGO_METADATA", e.to_string()))?;
    if metadata["version"] != 1
        || metadata["workspace_root"].as_str() != workspace_root.to_str()
        || (view == DependencyView::Resolved && !metadata["resolve"].is_object())
    {
        return Err(refused(
            "NATIVE_CARGO_METADATA",
            "Cargo output does not bind the declared workspace/resolution view",
        ));
    }
    let members = metadata["workspace_members"]
        .as_array()
        .ok_or_else(|| refused("NATIVE_CARGO_METADATA", "Missing member inventory"))?;
    let packages = metadata["packages"]
        .as_array()
        .ok_or_else(|| refused("NATIVE_CARGO_METADATA", "Missing package inventory"))?;
    let mut entities = Vec::new();
    for package in packages.iter().filter(|p| members.contains(&p["id"])) {
        let manifest = package["manifest_path"]
            .as_str()
            .ok_or_else(|| refused("NATIVE_CARGO_METADATA", "Missing member manifest"))?;
        let relative = Path::new(manifest)
            .strip_prefix(root)
            .map_err(|_| {
                refused(
                    "NATIVE_CARGO_PATH_ESCAPE",
                    "Resolved package outside declared owner",
                )
            })?
            .to_str()
            .ok_or_else(|| refused("NATIVE_SOURCE_UTF8", "Filesystem paths must be UTF-8"))?
            .replace('\\', "/");
        if !inputs.contains_key(relative.as_str()) {
            return Err(refused("NATIVE_CARGO_MANIFEST_INPUT", relative));
        }
        let name = package["name"]
            .as_str()
            .ok_or_else(|| refused("NATIVE_CARGO_METADATA", "Package name missing"))?;
        let package_id = physical_id(
            &request.namespace,
            "cargo-package",
            &json!([relative, name]),
        )?;
        let mut declarations = package["dependencies"]
            .as_array()
            .ok_or_else(|| refused("NATIVE_CARGO_METADATA", "Dependency declarations missing"))?
            .clone();
        for dep in &mut declarations {
            if let Some(path) = dep.get("path").and_then(Value::as_str).map(str::to_owned) {
                let relative = Path::new(&path)
                    .strip_prefix(root)
                    .map_err(|_| {
                        refused(
                            "NATIVE_CARGO_PATH_ESCAPE",
                            "Resolved path dependency outside owner",
                        )
                    })?
                    .to_str()
                    .ok_or_else(|| refused("NATIVE_SOURCE_UTF8", "Filesystem paths must be UTF-8"))?
                    .replace('\\', "/");
                dep["path"] = json!(relative);
            }
        }
        let resolved_features = metadata["resolve"]["nodes"]
            .as_array()
            .and_then(|v| v.iter().find(|n| n["id"] == package["id"]))
            .map(|n| n["features"].clone());
        entities.push(entity(package_id.clone(),"cargo-package",&relative,json!({"name":name,"version":package["version"],"manifest":relative,
            "featuresDeclared":package["features"],"featuresResolved":resolved_features,"dependenciesDeclared":declarations,
            "evidenceClass":if view==DependencyView::Resolved {"cargo-resolved"} else {"cargo-declared-local"},"compilationEstablished":false})));
        for target in package["targets"]
            .as_array()
            .ok_or_else(|| refused("NATIVE_CARGO_METADATA", "Target inventory missing"))?
        {
            let source = target["src_path"]
                .as_str()
                .ok_or_else(|| refused("NATIVE_CARGO_METADATA", "Target source unavailable"))?;
            let source = Path::new(source)
                .strip_prefix(root)
                .map_err(|_| refused("NATIVE_CARGO_PATH_ESCAPE", "Target source outside owner"))?
                .to_str()
                .ok_or_else(|| refused("NATIVE_SOURCE_UTF8", "Filesystem paths must be UTF-8"))?
                .replace('\\', "/");
            let id = physical_id(
                &request.namespace,
                "cargo-target",
                &json!([relative, target["name"], target["kind"]]),
            )?;
            let executable = target["kind"]
                .as_array()
                .is_some_and(|v| v.iter().any(|k| k == "custom-build" || k == "proc-macro"));
            entities.push(entity(id,"cargo-target",&source,json!({"package":package_id,"name":target["name"],"kind":target["kind"],
                "crateTypes":target["crate_types"],"requiredFeatures":target.get("required-features").cloned().unwrap_or(json!([])),
                "source":source,"possibleExecutableInput":executable,"executionObserved":false,"compilationEstablished":false,
                "evidenceClass":"cargo-declared-target", "discoveryContext":{"manifest":config.manifest,"packageManifest":relative,"workspaceManifest":workspace_manifest,"platformFilter":platform,"features":features,"defaultFeatures":default_features,"view":if view==DependencyView::Resolved {"resolved"}else{"declared-local"},"workingDirectory":"owner-root","compilationEstablished":false}})));
        }
    }
    let mut executable_inputs = Vec::new();
    for package in packages {
        for target in package["targets"]
            .as_array()
            .ok_or_else(|| refused("NATIVE_CARGO_METADATA", "Target inventory missing"))?
        {
            if !target["kind"]
                .as_array()
                .is_some_and(|v| v.iter().any(|k| k == "custom-build" || k == "proc-macro"))
            {
                continue;
            }
            if executable_inputs.len() >= NODE_LIMIT {
                return Err(refused(
                    "NATIVE_DISCOVERY_LIMIT",
                    "Possible executable input inventory exceeds its bound",
                ));
            }
            let source = target["src_path"].as_str().ok_or_else(|| {
                refused("NATIVE_CARGO_METADATA", "Executable source locator missing")
            })?;
            let captured = Path::new(source)
                .strip_prefix(root)
                .ok()
                .and_then(Path::to_str)
                .is_some_and(|p| inputs.contains_key(p));
            executable_inputs.push(json!({"packageName":package["name"],"packageVersion":package["version"],
                "cargoTargetKind":target["kind"],"sourceLocator":source,"workspaceMember":members.contains(&package["id"]),
                "sourceContentsCaptured":captured,"executionObserved":false}));
        }
    }
    let mut receipt = json!({"evidenceClass":"cargo-tool-observation","view":if view==DependencyView::Resolved {"resolved"} else {"declared-local"},
        "manifest":manifest,"workspaceManifest":workspace_manifest,"lockfile":lockfile,"platformFilter":platform,
        "features":features,"defaultFeatures":default_features,"configurationInputs":configs,
        "cargo":{"path":cargo_path,"digest":actual_cargo,"version":std::str::from_utf8(&cargo_version).map_err(|_|refused("NATIVE_TOOL_UTF8","Cargo version output is not UTF-8"))?},
        "rustc":{"path":rustc_path,"digest":actual_rustc,"version":std::str::from_utf8(&rustc_version).map_err(|_|refused("NATIVE_TOOL_UTF8","Rustc version output is not UTF-8"))?},
        "argv":args,"metadataDigest":byte_digest(&raw),"metadataBytes":std::str::from_utf8(&raw).map_err(|_|refused("NATIVE_TOOL_UTF8","Cargo metadata is not UTF-8"))?,
        "possibleExecutableInputs":executable_inputs,"dependencyExecutableInventoryAvailable":view==DependencyView::Resolved,"compilationEstablished":false,"buildScriptsExecuted":false,"completeExecutableDependencyClosureEstablished":false});
    if config.root_mode == CargoRootMode::StandalonePackage {
        receipt["rootMode"] = json!("standalone-package");
    }
    Ok((entities, receipt))
}

/// Reuse the existing bounded process request/response and workspace lineage contract.
pub fn discover_native(request: &AdapterRequest, root: &Path) -> Result<AdapterResponse, Error> {
    if request.profile != PROFILE || request.inputs.is_empty() || request.inputs.len() > 1024 {
        return Err(refused(
            "NATIVE_DISCOVERY_REQUEST",
            "Unsupported or empty workspace request",
        ));
    }
    let mut unsigned = request.clone();
    unsigned.request_digest.clear();
    if canonical_digest(&unsigned)? != request.request_digest {
        return Err(refused(
            "NATIVE_DISCOVERY_REQUEST",
            "Request digest mismatch",
        ));
    }
    let mut inputs = Inputs::new();
    let mut bytes = 0usize;
    for input in &request.inputs {
        bytes = bytes.saturating_add(input.content.len());
        if bytes > MAX_INPUT_BYTES
            || !relative_path(&input.receipt.path)
            || inputs.insert(&input.receipt.path, &input.content).is_some()
            || byte_digest(input.content.as_bytes()) != input.receipt.digest
            || input.receipt.byte_length.get() != input.content.len() as u64
        {
            return Err(refused(
                "NATIVE_DISCOVERY_INPUT",
                "Invalid, changed, duplicated or oversized captured input",
            ));
        }
    }
    let config: Config = serde_json::from_value(json!(request.config))
        .map_err(|e| refused("NATIVE_DISCOVERY_CONFIG", e.to_string()))?;
    let (mut entities, metadata) = match config {
        Config::Toml {
            nonsecret_inputs,
            files,
        } => {
            if !nonsecret_inputs {
                return Err(refused(
                    "NATIVE_SECRET_INPUT",
                    "Only explicitly declared nonsecret inputs may be captured",
                ));
            }
            let (entities, excluded) = toml_entities(&request.namespace, &inputs, &files)?;
            (
                entities,
                json!({"profile":VERSION,"evidenceClass":"observed-syntax","parser":"toml_edit=0.23.7","testedTomlProfile":"1.0-values",
                "excludedNodeCount":excluded,"compilationEstablished":false,"semanticMeaning":"owner-authored"}),
            )
        }
        Config::Files { nonsecret_inputs } => {
            if !nonsecret_inputs {
                return Err(refused(
                    "NATIVE_SECRET_INPUT",
                    "Only explicitly declared complete nonsecret files may be captured",
                ));
            }
            let mut entities = Vec::new();
            for (path, raw) in &inputs {
                if path.len() > 4096 {
                    return Err(refused(
                        "NATIVE_DISCOVERY_INPUT",
                        "Captured file path exceeds the observation bound",
                    ));
                }
                entities.push(entity(physical_id(&request.namespace, "input", &json!(path))?, "build:input", path,
                    json!({"file":path,"digest":byte_digest(raw.as_bytes()),"byteLength":raw.len(),"evidenceClass":"captured-file-receipt","contentStoredInCapture":true,"compilationEstablished":false})));
            }
            (
                entities,
                json!({"profile":VERSION,"evidenceClass":"captured-file-receipts","compilationEstablished":false,"semanticMeaning":"owner-authored"}),
            )
        }
        Config::Dockerfile(config) => {
            let (entities, observation) =
                crate::native_docker::observe(&request.namespace, &inputs, &config)?;
            (
                entities,
                json!({"profile":VERSION,"observation":observation}),
            )
        }
        Config::Cargo(config) => {
            if !config.nonsecret_inputs {
                return Err(refused(
                    "NATIVE_SECRET_INPUT",
                    "Only explicitly declared nonsecret inputs may be captured",
                ));
            }
            let root = fs::canonicalize(root)?;
            let (entities, observation) = cargo_entities(request, &inputs, &root, &config)?;
            (
                entities,
                json!({"profile":VERSION,"observation":observation}),
            )
        }
    };
    if entities.len() > NODE_LIMIT {
        return Err(refused("NATIVE_DISCOVERY_LIMIT", "Entity bound exceeded"));
    }
    entities.sort_by(|a, b| a["id"].as_str().cmp(&b["id"].as_str()));
    let graph:GraphDocument=parse(&serde_json::to_vec(&json!({"schemaVersion":"0.1.0","documentType":"graph",
        "id":physical_id(&request.namespace,"shard",&json!(request.source_id))?,"namespace":request.namespace,
        "entities":entities,"mappings":[],"authorities":[],"metadata":metadata})).map_err(|e|refused("NATIVE_DISCOVERY_RESPONSE",e.to_string()))?)?;
    Ok(AdapterResponse {
        schema_version: ProtocolVersion::Draft1,
        document_type: ResponseType::Record,
        profile: PROFILE.into(),
        source_id: request.source_id.clone(),
        adapter_version: VERSION.into(),
        request_digest: request.request_digest.clone(),
        inputs: request
            .inputs
            .iter()
            .map(|v| v.receipt.clone())
            .collect::<Vec<InputReceipt>>(),
        shard: graph,
        diagnostics: Vec::new(),
    })
}

#[cfg(test)]
#[path = "native_discovery_tests.rs"]
mod tests;
