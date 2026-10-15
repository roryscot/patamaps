use crate::{CheckedProjection, ProjectedEntry};
use patamaps_contracts::*;
use patamaps_core::{CheckError, Issue};
use serde::Serialize;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

const MAX_PATH_DEPTH: usize = 48;
const MAX_PATH_NODES: usize = 200_000;
#[derive(Debug, Clone, Serialize)]
pub struct PathOccupant {
    pub id: String,
    pub kind: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
    pub slots: BTreeMap<String, Value>,
}
#[derive(Debug, Clone, Serialize)]
pub struct PathNode {
    #[serde(rename = "_")]
    pub path: String,
    #[serde(rename = "$", skip_serializing_if = "Option::is_none")]
    pub occupant: Option<PathOccupant>,
    #[serde(flatten)]
    pub children: BTreeMap<String, PathNode>,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PathTreeRecord {
    pub schema_version: ProtocolVersion,
    pub document_type: &'static str,
    pub profile: &'static str,
    pub id: String,
    pub digest: String,
    pub projection: ContentBinding,
    pub spec: ContentBinding,
    pub attribute: String,
    pub delimiter: PathDelimiter,
    pub params: Vec<String>,
    pub tree: PathNode,
}
/// The only constructor consumes a checked projection and its exact bound spec.
/// ```compile_fail
/// use patamaps_projection::CheckedPathTree;
/// let forged: CheckedPathTree = serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug)]
pub struct CheckedPathTree {
    record: PathTreeRecord,
}
impl CheckedPathTree {
    pub fn record(&self) -> &PathTreeRecord {
        &self.record
    }
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HydratedTree {
    pub document_type: &'static str,
    pub template: ContentBinding,
    pub parameters: BTreeMap<String, String>,
    pub tree: PathNode,
}
fn error(code: &str, message: &str, subject: &str) -> CheckError {
    CheckError(vec![Issue::error(code, message, subject)])
}
fn param(segment: &str) -> bool {
    let Some(first) = segment.as_bytes().first() else {
        return false;
    };
    if !b":*".contains(first) {
        return false;
    }
    let mut name = &segment[1..];
    if *first == b'*' {
        name = name.strip_suffix('?').unwrap_or(name);
    }
    name.starts_with(|c: char| c.is_ascii_alphabetic())
        && name.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'_')
}
fn safe_segment(s: &str) -> bool {
    param(s)
        || !s.is_empty()
            && s.bytes()
                .all(|c| c.is_ascii_alphanumeric() || b"._~-".contains(&c))
}
fn path_at(segments: &[&str], delimiter: &str) -> String {
    format!("{delimiter}{}", segments.join(delimiter))
}
fn occupant(entry: &ProjectedEntry) -> Result<PathOccupant, ContractError> {
    let mut slots = BTreeMap::new();
    for s in &entry.slots {
        let value = match s.cardinality {
            SlotCardinality::ExactlyOne | SlotCardinality::ZeroOrOne => s
                .targets
                .first()
                .map(serde_json::to_value)
                .transpose()?
                .unwrap_or(Value::Null),
            SlotCardinality::OneOrMore | SlotCardinality::Many => serde_json::to_value(&s.targets)?,
        };
        slots.insert(s.name.clone(), value);
    }
    Ok(PathOccupant {
        id: entry.subject.id.clone(),
        kind: entry.subject.kind.clone(),
        label: entry.subject.label.clone(),
        slots,
    })
}
pub fn compile_path_tree(
    projection: &CheckedProjection,
    spec: &ProjectionSpec,
) -> Result<CheckedPathTree, CheckError> {
    let Some(config) = &spec.path_tree else {
        return Err(error(
            "PATH_TREE_SPEC_MISSING",
            "Specification must explicitly declare pathTree",
            &spec.id,
        ));
    };
    if projection.record().spec.id != spec.id
        || projection.record().spec.digest.as_deref() != Some(canonical_digest(spec)?.as_str())
    {
        return Err(error(
            "PATH_TREE_SPEC_DIGEST_MISMATCH",
            "Tree spec differs from the exact checked projection binding",
            &spec.id,
        ));
    }
    let delimiter = config.delimiter.unwrap_or_default();
    let sep = delimiter.as_str();
    let attribute = config.attribute.clone().unwrap_or_else(|| "path".into());
    if attribute.is_empty() {
        return Err(error(
            "INVALID_PATH_TREE_SPEC",
            "Attribute must be nonempty",
            &spec.id,
        ));
    }
    let mut root = PathNode {
        path: sep.into(),
        occupant: None,
        children: BTreeMap::new(),
    };
    let mut params = BTreeSet::new();
    let mut occupied = BTreeSet::new();
    let mut nodes = 1usize;
    let mut bytes = 256usize;
    for entry in &projection.record().entries {
        let id = &entry.subject.id;
        let raw = entry
            .subject
            .attributes
            .as_ref()
            .and_then(|a| a.get(&attribute))
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
            .ok_or_else(|| {
                error(
                    "PATH_TREE_PATH_MISSING",
                    "Selected subject lacks a nonempty string path",
                    id,
                )
            })?;
        let rest = raw.strip_prefix(sep).ok_or_else(|| {
            error(
                "PATH_TREE_INVALID_PATH",
                "Path must begin with its declared delimiter",
                id,
            )
        })?;
        let segments: Vec<_> = if rest.is_empty() {
            vec![]
        } else {
            rest.split(sep).collect()
        };
        if segments.len() > MAX_PATH_DEPTH {
            return Err(error(
                "PATH_TREE_RESOURCE_LIMIT",
                "Path exceeds 48 template levels",
                id,
            ));
        }
        if segments.iter().any(|s| ["_", "$"].contains(s)) {
            return Err(error(
                "PATH_TREE_RESERVED_SEGMENT",
                "Path uses a reserved tree key",
                id,
            ));
        }
        if segments.iter().any(|s| !safe_segment(s)) || path_at(&segments, sep) != raw {
            return Err(error(
                "PATH_TREE_INVALID_PATH",
                "Path contains an empty or unsafe segment",
                id,
            ));
        }
        if !occupied.insert(raw) {
            return Err(error(
                "PATH_TREE_COLLISION",
                "More than one selected identity claims this exact path",
                id,
            ));
        }
        let mut current = &mut root;
        for (i, segment) in segments.iter().enumerate() {
            if param(segment) {
                params.insert((*segment).to_owned());
            }
            if !current.children.contains_key(*segment) {
                nodes += 1;
                let path = path_at(&segments[..=i], sep);
                bytes = bytes.saturating_add(path.len() + segment.len() + 32);
                if nodes > MAX_PATH_NODES || bytes > MAX_INPUT_BYTES {
                    return Err(error(
                        "PATH_TREE_RESOURCE_LIMIT",
                        "Tree construction exceeds node/byte limits",
                        id,
                    ));
                }
                current.children.insert(
                    (*segment).into(),
                    PathNode {
                        path,
                        occupant: None,
                        children: BTreeMap::new(),
                    },
                );
            }
            current = current.children.get_mut(*segment).expect("inserted child");
        }
        let value = occupant(entry)?;
        bytes = bytes.saturating_add(canonical_bytes(&value)?.len());
        if bytes > MAX_INPUT_BYTES {
            return Err(error(
                "PATH_TREE_RESOURCE_LIMIT",
                "Tree occupants exceed output byte bounds",
                id,
            ));
        }
        current.occupant = Some(value);
    }
    let mut record = PathTreeRecord {
        schema_version: ProtocolVersion::Draft1,
        document_type: "path-tree",
        profile: projection.record().profile,
        id: String::new(),
        digest: String::new(),
        projection: ContentBinding {
            id: projection.record().id.clone(),
            digest: projection.record().digest.clone(),
        },
        spec: ContentBinding {
            id: spec.id.clone(),
            digest: canonical_digest(spec)?,
        },
        attribute,
        delimiter,
        params: params.into_iter().collect(),
        tree: root,
    };
    let mut content = serde_json::to_value(&record).map_err(ContractError::from)?;
    let obj = content.as_object_mut().expect("tree object");
    obj.remove("id");
    obj.remove("digest");
    record.digest = canonical_digest(&content)?;
    record.id = format!("urn:patamaps:path-tree:{}", &record.digest[7..]);
    parse_value(&canonical_bytes(&record)?)?;
    Ok(CheckedPathTree { record })
}
fn resolve<'a>(token: &str, values: &'a BTreeMap<String, String>) -> Option<&'a str> {
    let bare = token[1..].trim_end_matches('?');
    [
        token.to_owned(),
        bare.to_owned(),
        format!(":{bare}"),
        format!("*{bare}"),
        format!("*{bare}?"),
    ]
    .iter()
    .find_map(|key| values.get(key).map(String::as_str))
}
fn whitespace(c: char) -> bool {
    matches!(c,'\u{0009}'..='\u{000d}'|'\u{0020}'|'\u{00a0}'|'\u{1680}'|'\u{2000}'..='\u{200a}'|'\u{2028}'|'\u{2029}'|'\u{202f}'|'\u{205f}'|'\u{3000}'|'\u{feff}')
}
fn hydrated_path(
    path: &str,
    params: &BTreeMap<String, String>,
    delimiter: PathDelimiter,
    subject: &str,
) -> Result<String, CheckError> {
    let sep = delimiter.as_str();
    let mut output = String::new();
    for segment in path
        .strip_prefix(sep)
        .expect("checked path prefix")
        .split(sep)
    {
        let value = if param(segment) {
            match resolve(segment, params) {
                None if segment.starts_with('*') && segment.ends_with('?') => "",
                None => {
                    return Err(error(
                        "MISSING_PATH_PARAMETER",
                        "Required path parameter is unavailable",
                        segment,
                    ));
                }
                Some(value) => {
                    if value.is_empty()
                        || value.chars().any(|c| whitespace(c) || c == '?' || c == '#')
                        || delimiter != PathDelimiter::Slash && value.contains(sep)
                        || !segment.starts_with('*') && value.contains('/')
                    {
                        return Err(error(
                            "UNSAFE_PATH_PARAMETER",
                            "Parameter contains a forbidden delimiter or character",
                            segment,
                        ));
                    }
                    value
                }
            }
        } else {
            segment
        };
        if !value.is_empty() {
            output.push_str(sep);
            output.push_str(value);
            if output.len() > MAX_INPUT_BYTES {
                return Err(error(
                    "PATH_TREE_RESOURCE_LIMIT",
                    "Hydrated path exceeds output bounds",
                    subject,
                ));
            }
        }
    }
    if delimiter == PathDelimiter::Slash {
        let parts: Vec<_> = output.split('/').filter(|s| !s.is_empty()).collect();
        Ok(path_at(&parts, "/"))
    } else {
        Ok(if output.is_empty() {
            sep.into()
        } else {
            output
        })
    }
}
/// Hydration returns data, without any checked compiler/activation capability.
/// Only `_` strings change; template child keys and occupants remain identical.
pub fn hydrate(
    tree: &CheckedPathTree,
    parameters: BTreeMap<String, String>,
) -> Result<HydratedTree, CheckError> {
    if parameters.len() > 1024
        || parameters
            .iter()
            .map(|(k, v)| k.len().saturating_add(v.len()))
            .sum::<usize>()
            > MAX_INPUT_BYTES
    {
        return Err(error(
            "PATH_TREE_RESOURCE_LIMIT",
            "Parameter input exceeds bounds",
            &tree.record.id,
        ));
    }
    fn visit(
        node: &PathNode,
        parameters: &BTreeMap<String, String>,
        delimiter: PathDelimiter,
        bytes: &mut usize,
    ) -> Result<PathNode, CheckError> {
        let path = hydrated_path(&node.path, parameters, delimiter, &node.path)?;
        *bytes = bytes.saturating_add(path.len());
        if *bytes > MAX_INPUT_BYTES {
            return Err(error(
                "PATH_TREE_RESOURCE_LIMIT",
                "Hydrated strings exceed output bounds",
                &node.path,
            ));
        }
        let children = node
            .children
            .iter()
            .map(|(k, n)| Ok((k.clone(), visit(n, parameters, delimiter, bytes)?)))
            .collect::<Result<_, CheckError>>()?;
        Ok(PathNode {
            path,
            occupant: node.occupant.clone(),
            children,
        })
    }
    let result = HydratedTree {
        document_type: "hydrated-path-tree",
        template: ContentBinding {
            id: tree.record.id.clone(),
            digest: tree.record.digest.clone(),
        },
        tree: visit(
            &tree.record.tree,
            &parameters,
            tree.record.delimiter,
            &mut 0,
        )?,
        parameters,
    };
    parse_value(&canonical_bytes(&result)?)?;
    Ok(result)
}

/// Emit a standalone data module from a checked tree. The helper returns data;
/// it does not create checked policy, graph, replay or activation capabilities.
pub fn emit_typescript_path_tree(
    tree: &CheckedPathTree,
    export: &str,
) -> Result<String, CheckError> {
    if export.len() > 128 {
        return Err(error(
            "INVALID_EXPORT_NAME",
            "TypeScript tree export name exceeds 128 bytes",
            "export",
        ));
    }
    const GLOBALS: &[&str] = &[
        "Object",
        "Array",
        "Error",
        "Set",
        "TextEncoder",
        "undefined",
    ];
    if !super::typescript_export_name(export) || GLOBALS.contains(&export) {
        return Err(error(
            "INVALID_EXPORT_NAME",
            "Invalid or reserved TypeScript tree export name",
            export,
        ));
    }
    let value = serde_json::to_value(&tree.record.tree).map_err(ContractError::from)?;
    let json = String::from_utf8(canonical_bytes(&value)?).expect("canonical Unicode");
    let params =
        String::from_utf8(canonical_bytes(&tree.record.params)?).expect("canonical Unicode");
    let type_name = format!("{}{}", export[..1].to_ascii_uppercase(), &export[1..]);
    let params_name = format!("{export}Params");
    let mut prefix = "_patamaps".to_owned();
    while export.starts_with(&prefix) {
        prefix.push('_');
    }
    let runtime = TYPESCRIPT_TREE_RUNTIME
        .replace("@@HYDRATE@@", &format!("hydrate{type_name}"))
        .replace("@@EXPORT@@", export)
        .replace("@@TYPE@@", &type_name)
        .replace("@@PARAMS@@", &params_name)
        .replace("@@P@@", &prefix)
        .replace(
            "@@DELIMITER@@",
            &super::js_string(tree.record.delimiter.as_str()),
        )
        .replace("@@LIMIT@@", &MAX_INPUT_BYTES.to_string());
    Ok(format!(
        "// Generated from {}; regenerate after correspondence changes.\nexport const {export} = JSON.parse({}) as {};\nexport const {params_name} = {params} as const;\nexport type {type_name}Param = (typeof {params_name})[number];\nexport type {type_name}HydratedNode<T> = {{ readonly [K in keyof T]: K extends \"_\" ? string : K extends \"$\" ? T[K] : T[K] extends object ? {type_name}HydratedNode<T[K]> : T[K] }};\n{runtime}",
        tree.record.id,
        super::js_string(&json),
        super::typescript_type(&value),
    ))
}

// Segment-wise substitution, owned data and bounds match native hydration.
// Keep this consumer runtime inside the hashed Rust source inventory.
const TYPESCRIPT_TREE_RUNTIME: &str = r###"
export function @@HYDRATE@@(@@P@@params: Record<string, string>): @@TYPE@@HydratedNode<typeof @@EXPORT@@> {
  if (@@P@@params === null || typeof @@P@@params !== "object" || Array.isArray(@@P@@params)) {
    throw new Error("Path parameters must be a string map");
  }
  const @@P@@encoder = new TextEncoder();
  const @@P@@unicode = (text: string): boolean => {
    for (const character of text) {
      const point = character.codePointAt(0)!;
      if (point >= 0xd800 && point <= 0xdfff) return false;
    }
    return true;
  };
  const @@P@@bytes = (text: string): number => @@P@@encoder.encode(text).length;
  const @@P@@entries = Object.entries(@@P@@params);
  if (@@P@@entries.length > 1024) throw new Error("Path parameter resource limit");
  const @@P@@values: Record<string, string> = Object.create(null);
  let @@P@@inputBytes = 0;
  for (const [key, value] of @@P@@entries) {
    if (typeof value !== "string" || !@@P@@unicode(key) || !@@P@@unicode(value)) {
      throw new Error("Path parameters must contain Unicode scalar strings");
    }
    @@P@@inputBytes += @@P@@bytes(key) + @@P@@bytes(value);
    if (@@P@@inputBytes > @@LIMIT@@) throw new Error("Path parameter resource limit");
    @@P@@values[key] = value;
  }
  const @@P@@resolve = (token: string): string | undefined => {
    const bare = token.slice(1).replace(/\?$/, "");
    for (const key of [token, bare, ":" + bare, "*" + bare, "*" + bare + "?"]) {
      if (Object.hasOwn(@@P@@values, key)) return @@P@@values[key];
    }
    return undefined;
  };
  const @@P@@delimiter: string = @@DELIMITER@@;
  const @@P@@tokens = new Set<string>(@@PARAMS@@ as readonly string[]);
  let @@P@@outputBytes = 0;
  const @@P@@path = (path: string): string => {
    if (!path.startsWith(@@P@@delimiter)) throw new Error("Invalid path template");
    let output = "";
    let pathBytes = 0;
    for (const token of path.slice(@@P@@delimiter.length).split(@@P@@delimiter)) {
      let value = token;
      if (@@P@@tokens.has(token)) {
        const supplied = @@P@@resolve(token);
        if (supplied === undefined && token.startsWith("*") && token.endsWith("?")) {
          value = "";
        } else {
          if (supplied === undefined || supplied.length === 0 || /[\s?#]/u.test(supplied)
              || (!token.startsWith("*") && supplied.includes("/"))
              || (@@P@@delimiter !== "/" && supplied.includes(@@P@@delimiter))) {
            throw new Error("Missing or unsafe path parameter " + token);
          }
          value = supplied;
        }
      }
      if (value.length !== 0) {
        pathBytes += @@P@@bytes(@@P@@delimiter) + @@P@@bytes(value);
        if (pathBytes > @@LIMIT@@) throw new Error("Hydrated path resource limit");
        output += @@P@@delimiter + value;
      }
    }
    if (@@P@@delimiter === "/") {
      output = "/" + output.split("/").filter(part => part.length !== 0).join("/");
    } else if (output.length === 0) {
      output = @@P@@delimiter;
    }
    @@P@@outputBytes += @@P@@bytes(output);
    if (@@P@@outputBytes > @@LIMIT@@) throw new Error("Hydrated path resource limit");
    return output;
  };
  const @@P@@walk = (node: Record<string, unknown>): Record<string, unknown> => {
    if (!Object.hasOwn(node, "_") || typeof node._ !== "string") throw new Error("Invalid path node");
    const result: Record<string, unknown> = Object.create(null);
    for (const [key, value] of Object.entries(node)) {
      if (key === "_") result[key] = @@P@@path(value as string);
      else if (key === "$") result[key] = JSON.parse(JSON.stringify(value));
      else {
        if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid path child");
        result[key] = @@P@@walk(value as Record<string, unknown>);
      }
    }
    return result;
  };
  const @@P@@result = @@P@@walk(@@EXPORT@@);
  if (@@P@@bytes(JSON.stringify(@@P@@result)) > @@LIMIT@@) {
    throw new Error("Hydrated tree resource limit");
  }
  return @@P@@result as @@TYPE@@HydratedNode<typeof @@EXPORT@@>;
}
"###;
