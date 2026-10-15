//! Captured Dockerfile syntax and bounded, explicit context membership.
//! No Docker instruction, shell command or image is executed here.
use crate::{Error, relative_path};
use patamaps_contracts::byte_digest;
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    ops::ControlFlow,
    time::{Duration, Instant},
};
use tree_sitter::{Node, ParseOptions, Parser};

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(crate) struct DockerConfig {
    pub nonsecret_inputs: bool,
    pub dockerfile: String,
    pub context: String,
    pub context_files: Vec<String>,
    pub complete_context_snapshot: bool,
    pub target: String,
    pub platform: String,
    pub frontend: String,
    pub build_args: BTreeMap<String, String>,
}

fn refused(code: &'static str, message: impl Into<String>) -> Error {
    Error::refused(code, message)
}
fn text<'a>(node: Node<'_>, raw: &'a str) -> &'a str {
    &raw[node.byte_range()]
}
fn children(node: Node<'_>) -> Vec<Node<'_>> {
    let mut c = node.walk();
    node.named_children(&mut c).collect()
}
fn field<'a>(node: Node<'_>, name: &str, raw: &'a str) -> Option<&'a str> {
    node.child_by_field_name(name).map(|v| text(v, raw))
}
fn id(namespace: &str, kind: &str, value: &Value) -> Result<String, Error> {
    super::native_discovery::physical_id(namespace, kind, value)
}

fn expand(value: &str, values: &BTreeMap<String, String>) -> Result<String, String> {
    let mut result = String::new();
    let mut tail = value;
    while let Some(i) = tail.find('$') {
        result.push_str(&tail[..i]);
        tail = &tail[i + 1..];
        let (key, rest) = if let Some(v) = tail.strip_prefix('{') {
            let end = v.find('}').ok_or("unterminated expansion")?;
            (&v[..end], &v[end + 1..])
        } else {
            let end = tail
                .find(|c: char| !c.is_ascii_alphanumeric() && c != '_')
                .unwrap_or(tail.len());
            (&tail[..end], &tail[end..])
        };
        if key.is_empty() || !key.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_') {
            return Err("unsupported variable expansion".into());
        }
        result.push_str(
            values
                .get(key)
                .ok_or_else(|| format!("unresolved variable {key}"))?,
        );
        tail = rest;
        if result.len() > 65536 {
            return Err("expansion output bound".into());
        }
    }
    result.push_str(tail);
    Ok(result)
}
fn literal(value: &str, values: &BTreeMap<String, String>) -> Result<String, String> {
    if value.contains(['\n', '\r', '\\', '\'', '"']) {
        return Err(
            "quoted/escaped/multiline value is outside the supported expansion profile".into(),
        );
    }
    expand(value, values)
}
fn absolute(path: &str, workdir: Option<&str>) -> Result<String, String> {
    if path.is_empty()
        || path.contains(['$', '*', '?', '[', ']', '\\', '\0'])
        || path.split('/').any(|p| p == "..")
    {
        return Err("nonliteral or parent-relative destination".into());
    }
    let joined = if path.starts_with('/') {
        path.to_owned()
    } else {
        format!(
            "{}/{}",
            workdir.ok_or("base image working directory is unavailable")?,
            path
        )
    };
    Ok(format!(
        "/{}",
        joined
            .split('/')
            .filter(|v| !v.is_empty() && *v != ".")
            .collect::<Vec<_>>()
            .join("/")
    ))
}
fn context_path(context: &str, path: &str) -> String {
    if context == "." {
        path.to_owned()
    } else {
        format!("{context}/{path}")
    }
}
fn within<'a>(context: &str, path: &'a str) -> Option<&'a str> {
    if context == "." {
        Some(path)
    } else {
        path.strip_prefix(context).and_then(|p| p.strip_prefix('/'))
    }
}

struct IgnoreRule {
    pattern: String,
    anywhere: bool,
    exclude: bool,
}
fn ignore_rules(raw: &str) -> Result<Vec<IgnoreRule>, Error> {
    let mut rules = Vec::new();
    for line in raw.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') || line == "." {
            continue;
        }
        let (exclude, line) = line.strip_prefix('!').map_or((true, line), |v| (false, v));
        let line = line.trim_matches('/');
        let (anywhere, pattern) = line
            .strip_prefix("**/")
            .map_or((false, line), |v| (true, v));
        if !relative_path(pattern) || pattern.contains(['*', '?', '[', ']', '\\']) {
            return Err(refused(
                "NATIVE_DOCKER_IGNORE_UNSUPPORTED",
                "Only literal paths, optional **/ prefix and ordered literal negation are supported",
            ));
        }
        rules.push(IgnoreRule {
            pattern: pattern.to_owned(),
            anywhere,
            exclude,
        });
        if rules.len() > 1024 {
            return Err(refused("NATIVE_DOCKER_LIMIT", "Ignore rule bound exceeded"));
        }
    }
    Ok(rules)
}
fn ignored(path: &str, rules: &[IgnoreRule]) -> bool {
    let mut result = false;
    for rule in rules {
        let matches = |v: &str| {
            v == rule.pattern
                || v.strip_prefix(&rule.pattern)
                    .is_some_and(|r| r.starts_with('/'))
        };
        let hit = matches(path)
            || rule.anywhere
                && path
                    .match_indices('/')
                    .any(|(i, _)| matches(&path[i + 1..]));
        if hit {
            result = rule.exclude;
        }
    }
    result
}

#[derive(Clone, Default)]
struct Stage {
    index: usize,
    alias: Option<String>,
    image: String,
    platform: String,
    workdir: Option<String>,
    entrypoint: Option<Vec<String>>,
    command: Option<Vec<String>>,
    user: Option<String>,
    expose: Vec<String>,
    command_set_here: bool,
    values: BTreeMap<String, String>,
    reasons: Vec<String>,
}
impl Stage {
    fn value(&self) -> Value {
        json!({"index":self.index,"alias":self.alias,"base":self.image,"platform":self.platform,"workdir":self.workdir,"entrypoint":self.entrypoint,"cmd":self.command,"user":self.user,"expose":self.expose,"unsupportedReasons":self.reasons,"baseImageIdentityObserved":false,"imageContentsEstablished":false,"runtimeListenerEstablished":false})
    }
}

fn parameter<'a>(node: Node<'_>, raw: &'a str) -> Result<(&'a str, &'a str), String> {
    let value = text(node, raw);
    let value = value.strip_prefix("--").ok_or("invalid parameter")?;
    value
        .split_once('=')
        .ok_or_else(|| "parameter without an explicit value is unsupported".into())
}
fn exec_array(node: Node<'_>, raw: &str) -> Result<Vec<String>, String> {
    let array = children(node)
        .into_iter()
        .find(|n| n.kind() == "json_string_array")
        .ok_or("shell-form launch command has opaque effects")?;
    let result: Vec<String> =
        serde_json::from_str(text(array, raw)).map_err(|_| "exec array is not strict JSON")?;
    if result.is_empty()
        || result.len() > 64
        || result.iter().any(|v| v.len() > 4096 || v.contains('\0'))
    {
        return Err("empty or oversized exec array".into());
    }
    Ok(result)
}

pub(crate) fn observe(
    namespace: &str,
    inputs: &BTreeMap<&str, &str>,
    config: &DockerConfig,
) -> Result<(Vec<Value>, Value), Error> {
    if !config.nonsecret_inputs {
        return Err(refused(
            "NATIVE_SECRET_INPUT",
            "Only explicitly declared complete nonsecret files may be captured",
        ));
    }
    if !config.complete_context_snapshot
        || config.context_files.is_empty()
        || config.context_files.len() > 1024
        || config.context != "." && !relative_path(&config.context)
        || !relative_path(&config.dockerfile)
        || !["linux/amd64", "linux/arm64"].contains(&config.platform.as_str())
    {
        return Err(refused(
            "NATIVE_DOCKER_CONTEXT",
            "A bounded complete captured context and explicit supported Linux platform are required",
        ));
    }
    let declared: BTreeSet<_> = config.context_files.iter().map(String::as_str).collect();
    let captured: BTreeSet<_> = inputs
        .keys()
        .copied()
        .filter(|p| within(&config.context, p).is_some())
        .collect();
    if declared.len() != config.context_files.len()
        || declared != captured
        || declared
            .iter()
            .any(|p| !relative_path(p) || !inputs.contains_key(p))
    {
        return Err(refused(
            "NATIVE_DOCKER_CONTEXT",
            "Context inventory and captured input paths differ",
        ));
    }
    let raw = *inputs
        .get(config.dockerfile.as_str())
        .ok_or_else(|| refused("NATIVE_DOCKER_INPUT", "Dockerfile bytes are unavailable"))?;
    if raw.len() > 1024 * 1024 {
        return Err(refused(
            "NATIVE_DOCKER_LIMIT",
            "Dockerfile byte bound exceeded",
        ));
    }
    let specific = format!("{}.dockerignore", config.dockerfile);
    let default = context_path(&config.context, ".dockerignore");
    let ignore_path = if inputs.contains_key(specific.as_str()) {
        Some(specific)
    } else if inputs.contains_key(default.as_str()) {
        Some(default)
    } else {
        None
    };
    let rules = ignore_rules(
        ignore_path
            .as_ref()
            .and_then(|p| inputs.get(p.as_str()))
            .copied()
            .unwrap_or(""),
    )?;
    let mut parser = Parser::new();
    parser
        .set_language(&tree_sitter_containerfile::LANGUAGE.into())
        .map_err(|e| refused("NATIVE_DOCKER_PARSER", e.to_string()))?;
    let start = Instant::now();
    let mut progress = |_: &tree_sitter::ParseState| {
        if start.elapsed() > Duration::from_secs(2) {
            ControlFlow::Break(())
        } else {
            ControlFlow::Continue(())
        }
    };
    let mut read = |offset: usize, _| raw.as_bytes().get(offset..).unwrap_or(&[]);
    let tree = parser
        .parse_with_options(
            &mut read,
            None,
            Some(ParseOptions::new().progress_callback(&mut progress)),
        )
        .ok_or_else(|| {
            refused(
                "NATIVE_DOCKER_PARSE_LIMIT",
                "Parser did not complete within its bound",
            )
        })?;
    let root = tree.root_node();
    if root.has_error() {
        return Err(refused(
            "NATIVE_DOCKER_SYNTAX",
            format!(
                "Pinned grammar reports a syntax error in {}",
                config.dockerfile
            ),
        ));
    }
    let mut todo = vec![(root, 0usize)];
    let mut count = 0;
    while let Some((n, depth)) = todo.pop() {
        count += 1;
        if count > 10000 || depth > 64 {
            return Err(refused(
                "NATIVE_DOCKER_LIMIT",
                "Docker AST node/depth bound exceeded",
            ));
        }
        for c in children(n) {
            todo.push((c, depth + 1));
        }
    }
    let nodes = children(root);
    let mut entities = Vec::new();
    let mut stages: Vec<Stage> = Vec::new();
    let mut global = BTreeMap::new();
    let frontend_seen = raw
        .lines()
        .next()
        .and_then(|v| v.strip_prefix('#'))
        .map(str::trim)
        == Some(format!("syntax={}", config.frontend).as_str())
        && config.frontend == "docker/dockerfile:1.10.0";
    let mut unsupported = Vec::new();
    for node in nodes {
        let lexeme = text(node, raw);
        if node.kind() == "comment" {
            if stages.is_empty()
                && lexeme.trim_start_matches('#').trim().starts_with("escape=")
                && lexeme.trim_start_matches('#').trim() != "escape=\\"
            {
                return Err(refused(
                    "NATIVE_DOCKER_FRONTEND",
                    "Non-default parser escape directives are unsupported",
                ));
            }
            continue;
        }
        if lexeme.len() > 65536 {
            return Err(refused(
                "NATIVE_DOCKER_LIMIT",
                "Instruction byte bound exceeded",
            ));
        }
        let parts = children(node);
        let mut reasons = Vec::<String>::new();
        let mut observation = json!({});
        if node.kind() == "from_instruction" {
            let image = parts
                .iter()
                .find(|n| n.kind() == "image_spec")
                .map(|n| text(*n, raw))
                .ok_or_else(|| refused("NATIVE_DOCKER_SYNTAX", "FROM image missing"))?;
            let image = match literal(image, &global) {
                Ok(v) => v,
                Err(e) => {
                    reasons.push(e);
                    image.to_owned()
                }
            };
            let alias = field(node, "as", raw).map(str::to_owned);
            if alias.as_ref().is_some_and(|v| {
                v.is_empty()
                    || v.bytes().any(|b| {
                        !b.is_ascii_lowercase() && !b.is_ascii_digit() && !b"_-".contains(&b)
                    })
                    || stages.iter().any(|s| s.alias.as_ref() == Some(v))
            }) {
                return Err(refused(
                    "NATIVE_DOCKER_STAGE_ALIAS",
                    "Stage aliases must be unique lowercase literal names",
                ));
            }
            let mut platform = config.platform.clone();
            for p in parts.iter().filter(|n| n.kind() == "param") {
                match parameter(*p, raw) {
                    Ok(("platform", v)) => match literal(v, &global) {
                        Ok(v) => platform = v,
                        Err(e) => reasons.push(e),
                    },
                    _ => reasons.push("unsupported FROM option".into()),
                }
            }
            let inherited = stages
                .iter()
                .find(|s| s.alias.as_deref() == Some(image.as_str()))
                .cloned();
            let mut stage = inherited.unwrap_or_default();
            stage.index = stages.len();
            stage.alias = alias;
            stage.image = image;
            stage.platform = platform;
            stage.command_set_here = false;
            stage.reasons.extend(reasons.clone());
            stages.push(stage);
            observation = stages.last().expect("just pushed").value();
        } else if node.kind() == "arg_instruction" || node.kind() == "env_instruction" {
            let mut pairs = Vec::new();
            let before = stages
                .last()
                .map_or_else(|| global.clone(), |s| s.values.clone());
            for pair in parts
                .iter()
                .filter(|n| ["arg_pair", "env_pair"].contains(&n.kind()))
            {
                let name = field(*pair, "name", raw)
                    .ok_or_else(|| refused("NATIVE_DOCKER_SYNTAX", "Variable name missing"))?;
                let default = field(
                    *pair,
                    if node.kind() == "arg_instruction" {
                        "default"
                    } else {
                        "value"
                    },
                    raw,
                )
                .or_else(|| {
                    if node.kind() == "env_instruction" {
                        Some("")
                    } else {
                        None
                    }
                });
                let supplied = if node.kind() == "arg_instruction" {
                    config.build_args.get(name)
                } else {
                    None
                };
                let selected = default.or_else(|| global.get(name).map(String::as_str));
                let value = if let Some(value) = supplied {
                    if value.len() > 4096 || value.contains('\0') {
                        Err("build argument value exceeds bounds".into())
                    } else {
                        Ok(Some(value.clone()))
                    }
                } else {
                    selected.map(|v| literal(v, &before)).transpose()
                };
                match value {
                    Ok(Some(value)) => {
                        if let Some(stage) = stages.last_mut() {
                            stage.values.insert(name.into(), value.clone());
                        } else if node.kind() == "arg_instruction" {
                            global.insert(name.into(), value.clone());
                        } else {
                            reasons.push("ENV before FROM".into());
                        }
                        pairs.push(json!({"name":name,"value":value}));
                    }
                    Ok(None) => {
                        pairs.push(json!({"name":name,"value":null}));
                    }
                    Err(e) => reasons.push(e),
                }
            }
            observation = json!({"declarations":pairs});
        } else {
            let stage = stages
                .last_mut()
                .ok_or_else(|| refused("NATIVE_DOCKER_STAGE", "Instruction before first FROM"))?;
            match node.kind() {
                "workdir_instruction" => {
                    match parts
                        .iter()
                        .find(|n| n.kind() == "path")
                        .ok_or("WORKDIR path missing")
                        .and_then(|n| {
                            literal(text(*n, raw), &stage.values)
                                .map_err(|_| "WORKDIR expansion unavailable")
                        })
                        .and_then(|v| {
                            absolute(&v, stage.workdir.as_deref())
                                .map_err(|_| "WORKDIR is unresolved")
                        }) {
                        Ok(v) => stage.workdir = Some(v),
                        Err(e) => {
                            stage.workdir = None;
                            reasons.push(e.into());
                        }
                    }
                    observation = json!({"resolvedWorkdir":stage.workdir});
                }
                "entrypoint_instruction" | "cmd_instruction" => match exec_array(node, raw) {
                    Ok(v) => {
                        if node.kind() == "entrypoint_instruction" {
                            stage.entrypoint = Some(v.clone());
                            if !stage.command_set_here {
                                stage.command = None;
                            }
                        } else {
                            stage.command = Some(v.clone());
                            stage.command_set_here = true;
                        }
                        observation = json!({"exec":v,"environmentExpansionPerformed":false});
                    }
                    Err(e) => {
                        if node.kind() == "entrypoint_instruction" {
                            stage.entrypoint = None;
                        } else {
                            stage.command = None;
                        }
                        reasons.push(e);
                    }
                },
                "expose_instruction" => {
                    for p in parts.iter().filter(|n| n.kind() == "expose_port") {
                        match literal(text(*p, raw), &stage.values) {
                            Ok(v) => {
                                let (port, protocol) = v.split_once('/').unwrap_or((&v, "tcp"));
                                if port.parse::<u16>().is_ok_and(|v| v > 0)
                                    && ["tcp", "udp"].contains(&protocol)
                                {
                                    stage.expose.push(v);
                                } else {
                                    reasons.push("nonliteral/range EXPOSE is unsupported".into());
                                }
                            }
                            Err(e) => reasons.push(e),
                        }
                    }
                    observation = json!({"ports":stage.expose,"listenerEstablished":false});
                }
                "user_instruction" => {
                    let user = field(node, "user", raw).unwrap_or("");
                    let group = field(node, "group", raw);
                    let value = group.map_or_else(|| user.to_owned(), |g| format!("{user}:{g}"));
                    match literal(&value, &stage.values) {
                        Ok(v) => stage.user = Some(v),
                        Err(e) => {
                            stage.user = None;
                            reasons.push(e);
                        }
                    }
                    observation = json!({"declaredUser":stage.user});
                }
                "run_instruction" => {
                    observation = json!({"effectsEstablished":false,"executionPerformed":false});
                    reasons
                        .push("RUN effects require independent compiler/artifact evidence".into());
                }
                "copy_instruction" | "add_instruction" => {
                    let mut from = None;
                    for p in parts.iter().filter(|n| n.kind() == "param") {
                        match parameter(*p, raw) {
                            Ok(("from", v)) => {
                                if from.replace(v.to_owned()).is_some() {
                                    reasons.push("duplicate COPY --from".into());
                                }
                            }
                            _ => reasons.push("unsupported COPY/ADD option".into()),
                        }
                    }
                    let array = parts.iter().find(|n| n.kind() == "json_string_array");
                    let paths: Vec<String> = if let Some(n) = array {
                        serde_json::from_str(text(*n, raw))
                            .map_err(|e| refused("NATIVE_DOCKER_SYNTAX", e.to_string()))?
                    } else {
                        parts
                            .iter()
                            .filter(|n| n.kind() == "path")
                            .map(|n| text(*n, raw).to_owned())
                            .collect()
                    };
                    if paths.len() < 2 {
                        return Err(refused(
                            "NATIVE_DOCKER_SYNTAX",
                            "COPY/ADD requires source and destination",
                        ));
                    }
                    let (destination, sources) = paths.split_last().expect("checked size");
                    if sources.len() > 1 && !destination.ends_with('/') {
                        reasons.push(
                            "multiple COPY sources require an explicit destination directory"
                                .into(),
                        );
                    }
                    let destination_expanded = literal(destination, &stage.values);
                    let resolved_destination = destination_expanded
                        .as_ref()
                        .ok()
                        .and_then(|v| absolute(v, stage.workdir.as_deref()).ok());
                    if resolved_destination.is_none() {
                        reasons.push("COPY destination is unresolved".into());
                    }
                    let from_stage = from
                        .as_ref()
                        .and_then(|v| v.parse::<usize>().ok().filter(|i| *i < stage.index));
                    // Resolve named stages after this mutable borrow ends below.
                    observation = json!({"from":from,"fromStageIndex":from_stage,"sources":sources,"destination":destination,"resolvedDestination":resolved_destination,"contextMembers":[],"contentEstablished":false});
                    if node.kind() == "add_instruction" {
                        reasons
                            .push("ADD extraction/remote/content effects are unsupported".into());
                    }
                }
                _ => {
                    reasons.push(format!("unsupported instruction {}", node.kind()));
                }
            }
        }
        // COPY's named-stage/context resolution needs only immutable stage data.
        if ["copy_instruction", "add_instruction"].contains(&node.kind()) {
            let index = stages.len() - 1;
            let from = observation["from"].as_str();
            if let Some(from) = from {
                let found = from
                    .parse::<usize>()
                    .ok()
                    .filter(|i| *i < index)
                    .or_else(|| {
                        stages[..index]
                            .iter()
                            .position(|s| s.alias.as_deref() == Some(from))
                    });
                observation["fromStageIndex"] = json!(found);
                if found.is_none() {
                    reasons.push("COPY source stage is unavailable or external".into());
                }
                for value in observation["sources"].as_array().expect("paths") {
                    if !value.as_str().is_some_and(|v| {
                        v.starts_with('/')
                            && !v.contains(['$', '*', '?', '[', ']', '\\'])
                            && !v.split('/').any(|p| p == "..")
                    }) {
                        reasons.push(
                            "stage COPY source must be an absolute literal artifact path".into(),
                        );
                    }
                }
            } else {
                let mut members = Vec::new();
                let dest = observation["resolvedDestination"]
                    .as_str()
                    .map(str::to_owned);
                for value in observation["sources"].as_array().expect("paths") {
                    let source = value.as_str().expect("string path");
                    let source = match literal(source, &stages[index].values) {
                        Ok(v) => v.trim_start_matches('/').trim_end_matches('/').to_owned(),
                        Err(e) => {
                            reasons.push(e);
                            continue;
                        }
                    };
                    if !relative_path(&source) || source.contains(['*', '?', '[', ']', '\\']) {
                        reasons.push("context COPY source is not a supported literal path".into());
                        continue;
                    }
                    let mut existing = 0;
                    let mut included = 0;
                    for full in &declared {
                        let relative = within(&config.context, full).expect("checked context");
                        let suffix = if relative == source {
                            Some(None)
                        } else {
                            relative
                                .strip_prefix(&source)
                                .and_then(|r| r.strip_prefix('/'))
                                .map(Some)
                        };
                        if let Some(suffix) = suffix {
                            existing += 1;
                            if ignored(relative, &rules) {
                                continue;
                            }
                            included += 1;
                            let destination = dest.as_ref().map(|d| {
                                if let Some(suffix) = suffix {
                                    format!("{d}/{suffix}")
                                } else if observation["destination"]
                                    .as_str()
                                    .is_some_and(|s| s.ends_with('/'))
                                {
                                    format!(
                                        "{d}/{}",
                                        source.rsplit('/').next().expect("nonempty source")
                                    )
                                } else {
                                    d.clone()
                                }
                            });
                            members.push(json!({"source":full,"destination":destination,"digest":byte_digest(inputs[full].as_bytes()),"bytesCaptured":true}));
                        }
                    }
                    if existing == 0 {
                        reasons.push(format!("missing context source {source}"));
                    } else if included == 0 {
                        reasons.push(format!("context source excluded by ignore rules {source}"));
                    }
                }
                observation["contextMembers"] = json!(members);
            }
        }
        if node.kind() != "from_instruction"
            && let Some(stage) = stages.last_mut()
        {
            stage.reasons.extend(reasons.clone());
        }
        let source_span = json!([node.start_byte(), node.end_byte()]);
        let physical = id(
            namespace,
            "docker-instruction",
            &json!([config.dockerfile, node.start_byte(), node.kind()]),
        )?;
        if !reasons.is_empty() {
            unsupported.push(json!({"entity":physical,"reasons":reasons}));
        }
        entities.push(json!({"id":physical,"kind":"docker-instruction","locators":[{"uri":format!("file:{}",config.dockerfile),"digest":byte_digest(raw.as_bytes())}],"attributes":{"file":config.dockerfile,"stageIndex":stages.last().map(|s|s.index),"instruction":node.kind(),"span":source_span,"lexeme":lexeme,"observation":observation,"supportedSyntaxAndResolution":reasons.is_empty(),"unsupportedReasons":reasons}}));
    }
    if !frontend_seen {
        return Err(refused(
            "NATIVE_DOCKER_FRONTEND",
            "The selected frontend requires an exact captured syntax directive",
        ));
    }
    let selected = stages
        .iter()
        .find(|s| s.alias.as_deref() == Some(config.target.as_str()))
        .ok_or_else(|| {
            refused(
                "NATIVE_DOCKER_TARGET",
                "Selected named stage is unavailable",
            )
        })?;
    for stage in &stages {
        entities.push(json!({"id":id(namespace,"docker-stage",&json!([config.dockerfile,stage.index]))?,"kind":"docker-stage","attributes":stage.value()}));
    }
    let encoded = entities
        .iter()
        .try_fold(0usize, |n, v| {
            serde_json::to_vec(v).map(|b| n.saturating_add(b.len()))
        })
        .map_err(|e| refused("NATIVE_DOCKER_LIMIT", e.to_string()))?;
    if encoded > 8 * 1024 * 1024 || entities.len() > 10000 {
        return Err(refused(
            "NATIVE_DOCKER_LIMIT",
            "Docker observations exceed their aggregate bound",
        ));
    }
    Ok((
        entities,
        json!({"profile":"patamaps-docker-captured-syntax-1","evidenceClass":"observed-captured-syntax","parser":{"grammar":"tree-sitter-containerfile=0.9.2","engine":"tree-sitter=0.26.5","nodeTypesDigest":byte_digest(tree_sitter_containerfile::NODE_TYPES.as_bytes())},"dockerfile":config.dockerfile,"context":config.context,"capturedContextFiles":config.context_files,"contextCompleteness":"caller-declared complete captured snapshot; live filesystem not rediscovered","ignoreFile":ignore_path,"dockerfileSpecificIgnorePrecedence":true,"buildArgs":config.build_args,"selectedStage":selected.value(),"unsupported":unsupported,"compilationEstablished":false,"instructionsExecuted":false,"imageContentsEstablished":false,"runtimeListenerEstablished":false,"baseImageIdentitiesObserved":false,"processCaching":false}),
    ))
}

#[cfg(test)]
#[path = "native_docker_tests.rs"]
mod tests;
