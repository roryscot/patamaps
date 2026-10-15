#![forbid(unsafe_code)]

mod capture;
mod compare;
mod http;
mod path_tree;
pub use capture::{
    CaptureInputs, CaptureRecord, CaptureVersion, SourceReceipt, VerifiedReplay, capture, evaluate,
    executor_id, replay,
};
pub use compare::{compare, compare_with_origins};
pub use http::{emit_http_rust, emit_http_typescript};
pub use path_tree::{
    CheckedPathTree, HydratedTree, PathNode, PathTreeRecord, compile_path_tree,
    emit_typescript_path_tree, hydrate,
};

use patamaps_contracts::*;
use patamaps_core::{AdmittedGeneration, CheckError, Issue};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectedSlot {
    pub name: String,
    pub relation: String,
    pub direction: SlotDirection,
    pub cardinality: SlotCardinality,
    pub mappings: Vec<String>,
    pub targets: Vec<Entity>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectedEntry {
    pub subject: Entity,
    pub slots: Vec<ProjectedSlot>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectionRecord {
    pub schema_version: ProtocolVersion,
    pub document_type: &'static str,
    pub profile: &'static str,
    pub id: String,
    pub digest: String,
    pub graph: GraphBinding,
    pub generation: GraphBinding,
    pub spec: GraphBinding,
    pub entries: Vec<ProjectedEntry>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub semantics: Option<ProjectionSemantics>,
}

/// Only a successful projection of an admitted immutable session creates this.
///
/// ```compile_fail
/// use patamaps_projection::CheckedProjection;
/// let forged: CheckedProjection = serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug)]
pub struct CheckedProjection {
    record: ProjectionRecord,
}

impl CheckedProjection {
    pub fn record(&self) -> &ProjectionRecord {
        &self.record
    }
}

fn unique_nonempty(values: &[String]) -> bool {
    !values.is_empty()
        && values.iter().all(|s| !s.is_empty())
        && values.iter().collect::<BTreeSet<_>>().len() == values.len()
}
fn slot_name(value: &str) -> bool {
    value.starts_with(|c: char| c.is_ascii_alphabetic())
        && value
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"._-".contains(&c))
}
fn projected_entity(entity: &Entity) -> Entity {
    let mut value = entity.clone();
    // Provenance belongs to the captured graph and typed uncertainty records.
    // Preserve the reference portable projected-entity contract exactly.
    value.provenance = None;
    value
}

pub fn project(
    generation: &AdmittedGeneration<'_>,
    spec: &ProjectionSpec,
) -> Result<CheckedProjection, CheckError> {
    patamaps_core::check_metadata_bounds(
        spec.metadata.iter().map(|v| (v, 2)),
        &spec.id,
        "PROJECTION_RESOURCE_LIMIT",
    )?;
    parse_value(&canonical_bytes(spec)?)?;
    let graph = generation.graph();
    let mut issues = Vec::new();
    if spec.consumer.as_ref().is_some_and(|consumer| {
        !patamaps_core::valid_identifier(consumer)
            || spec
                .semantics
                .as_ref()
                .is_some_and(|semantics| semantics.consumer != *consumer)
    }) {
        issues.push(Issue::error(
            "INVALID_PROJECTION_CONSUMER",
            "Consumer identity must be valid and consistent with semantic requirements",
            &spec.id,
        ));
    }
    if !patamaps_core::valid_identifier(&spec.id)
        || (spec.select.ids.is_none() && spec.select.kinds.is_none())
        || [&spec.select.ids, &spec.select.kinds]
            .into_iter()
            .flatten()
            .any(|v| !unique_nonempty(v))
    {
        issues.push(Issue::error(
            "INVALID_PROJECTION_SPEC",
            "Projection needs a valid identity and nonempty unique selection fields",
            &spec.id,
        ));
    }
    for id in spec.select.ids.iter().flatten() {
        if graph.entity(id).is_none() {
            issues.push(Issue::error(
                "PROJECTION_UNKNOWN_SUBJECT",
                "Selected subject is absent",
                id,
            ));
        }
    }
    let mut slots = BTreeSet::new();
    for s in &spec.slots {
        if !slot_name(&s.name)
            || !slots.insert(&s.name)
            || s.target_kinds.as_ref().is_some_and(|v| !unique_nonempty(v))
        {
            issues.push(Issue::error(
                "INVALID_PROJECTION_SLOT",
                "Slots need unique valid names and kind lists",
                &spec.id,
            ));
        }
        if graph.relation(&s.relation).is_none() {
            issues.push(Issue::error(
                "PROJECTION_UNKNOWN_RELATION",
                "Slot relation is absent",
                &spec.id,
            ));
        }
    }
    if spec.slots.len() > 128
        || graph
            .document()
            .entities
            .len()
            .saturating_mul(spec.slots.len())
            > 2_000_000
    {
        return Err(CheckError(vec![Issue::error(
            "PROJECTION_WORK_LIMIT",
            "Projection exceeds the declared slot/work budget",
            &spec.id,
        )]));
    }
    if !issues.is_empty() {
        return Err(CheckError(issues));
    }
    let mut selected: Vec<_> = graph
        .document()
        .entities
        .iter()
        .filter(|e| {
            spec.select.ids.as_ref().is_none_or(|v| v.contains(&e.id))
                && spec
                    .select
                    .kinds
                    .as_ref()
                    .is_none_or(|v| v.contains(&e.kind))
        })
        .collect();
    selected.sort_by(|a, b| a.id.cmp(&b.id));
    let mut entries = Vec::new();
    let mut work = 0usize;
    let mut output_bytes = 0usize;
    let mut entity_bytes = BTreeMap::new();
    // Resolve only incident mappings, retaining the reference's indexed lookup.
    for e in selected {
        let size = if let Some(size) = entity_bytes.get(&e.id) {
            *size
        } else {
            let size = canonical_bytes(e)?.len();
            entity_bytes.insert(e.id.clone(), size);
            size
        };
        output_bytes = output_bytes.saturating_add(size);
        if output_bytes > MAX_INPUT_BYTES {
            return Err(CheckError(vec![Issue::error(
                "PROJECTION_BYTE_LIMIT",
                "Projection exceeds output byte limit",
                &spec.id,
            )]));
        }
        let mut projected_slots = Vec::new();
        for s in &spec.slots {
            let mut targets = BTreeMap::new();
            let mut mapping_ids = BTreeSet::new();
            for m in graph
                .incident(&e.id)
                .filter(|m| generation.active(&m.id) && m.relation == s.relation)
            {
                work = work
                    .saturating_add(1)
                    .saturating_add(m.sources.len())
                    .saturating_add(m.targets.len());
                if work > 2_000_000 {
                    return Err(CheckError(vec![Issue::error(
                        "PROJECTION_WORK_LIMIT",
                        "Projection endpoint scanning exceeds work limit",
                        &spec.id,
                    )]));
                }
                let (from, to) = match s.direction {
                    SlotDirection::Outgoing => (&m.sources, &m.targets),
                    SlotDirection::Incoming => (&m.targets, &m.sources),
                };
                if !from.contains(&e.id) {
                    continue;
                }
                mapping_ids.insert(m.id.clone());
                if m.lossiness != Lossiness::Lossless && s.allow_lossy != Some(true) {
                    issues.push(Issue::error(
                        "LOSSY_PROJECTION_LINK",
                        format!("Slot {} forbids lossy runtime bindings", s.name),
                        &e.id,
                    ));
                }
                for id in to {
                    let Some(target) = graph.entity(id) else {
                        continue;
                    };
                    if s.target_kinds
                        .as_ref()
                        .is_some_and(|v| !v.contains(&target.kind))
                    {
                        issues.push(Issue::error(
                            "PROJECTION_TARGET_KIND_MISMATCH",
                            format!("Slot {} has disallowed target kind", s.name),
                            &e.id,
                        ));
                    }
                    if !targets.contains_key(id) {
                        let size = if let Some(size) = entity_bytes.get(id) {
                            *size
                        } else {
                            let size = canonical_bytes(target)?.len();
                            entity_bytes.insert(id.clone(), size);
                            size
                        };
                        output_bytes = output_bytes.saturating_add(size);
                        if output_bytes > MAX_INPUT_BYTES {
                            return Err(CheckError(vec![Issue::error(
                                "PROJECTION_BYTE_LIMIT",
                                "Projection exceeds output byte limit",
                                &spec.id,
                            )]));
                        }
                        targets.insert(id.clone(), projected_entity(target));
                    }
                }
            }
            let count = targets.len();
            let valid = match s.cardinality {
                SlotCardinality::ExactlyOne => count == 1,
                SlotCardinality::ZeroOrOne => count <= 1,
                SlotCardinality::OneOrMore => count >= 1,
                SlotCardinality::Many => true,
            };
            if !valid {
                issues.push(Issue::error(
                    if count == 0 {
                        "REQUIRED_PROJECTION_TARGET_MISSING"
                    } else {
                        "AMBIGUOUS_PROJECTION_TARGET"
                    },
                    format!("Slot {} has {count} targets", s.name),
                    &e.id,
                ));
            }
            projected_slots.push(ProjectedSlot {
                name: s.name.clone(),
                relation: s.relation.clone(),
                direction: s.direction,
                cardinality: s.cardinality,
                mappings: mapping_ids.into_iter().collect(),
                targets: targets.into_values().collect(),
            });
        }
        projected_slots.sort_by(|a, b| a.name.cmp(&b.name));
        entries.push(ProjectedEntry {
            subject: projected_entity(e),
            slots: projected_slots,
        });
    }
    if !issues.is_empty() {
        issues.sort_by(|a, b| {
            (&a.code, &a.subject_id, &a.message).cmp(&(&b.code, &b.subject_id, &b.message))
        });
        issues.dedup();
        return Err(CheckError(issues));
    }
    let direct = entries
        .iter()
        .flat_map(|e| e.slots.iter().flat_map(|s| s.mappings.clone()))
        .collect();
    let semantics = patamaps_core::project_semantics(generation, spec, &direct)?;
    let mut record = ProjectionRecord {
        schema_version: ProtocolVersion::Draft1,
        document_type: "projection",
        profile: generation.record().profile,
        id: String::new(),
        digest: String::new(),
        graph: generation.record().graph.clone(),
        generation: GraphBinding {
            id: generation.record().id.clone(),
            revision: None,
            digest: Some(generation.record().digest.clone()),
        },
        spec: GraphBinding {
            id: spec.id.clone(),
            revision: None,
            digest: Some(canonical_digest(spec).map_err(CheckError::from)?),
        },
        entries,
        semantics,
    };
    let mut value = serde_json::to_value(&record)
        .map_err(ContractError::from)
        .map_err(CheckError::from)?;
    let object = value.as_object_mut().expect("projection is an object");
    object.remove("id");
    object.remove("digest");
    record.digest = canonical_digest(&value).map_err(CheckError::from)?;
    record.id = format!("urn:patamaps:projection:{}", &record.digest[7..]);
    let encoded = canonical_bytes(&record)?;
    if encoded.len() > MAX_INPUT_BYTES {
        return Err(CheckError(vec![Issue::error(
            "PROJECTION_BYTE_LIMIT",
            "Addressed projection exceeds output byte limit",
            &spec.id,
        )]));
    }
    parse_value(&encoded)?;
    Ok(CheckedProjection { record })
}

fn table(projection: &CheckedProjection) -> Result<serde_json::Value, CheckError> {
    let mut table = serde_json::Map::new();
    for entry in &projection.record.entries {
        let mut slots = serde_json::Map::new();
        for s in &entry.slots {
            let value = match s.cardinality {
                SlotCardinality::ExactlyOne | SlotCardinality::ZeroOrOne => s
                    .targets
                    .first()
                    .map(serde_json::to_value)
                    .transpose()
                    .map_err(ContractError::from)?
                    .unwrap_or(serde_json::Value::Null),
                _ => serde_json::to_value(&s.targets).map_err(ContractError::from)?,
            };
            slots.insert(s.name.clone(), value);
        }
        table.insert(entry.subject.id.clone(), slots.into());
    }
    Ok(table.into())
}

fn js_string(s: &str) -> String {
    serde_json::to_string(s)
        .expect("string serialization cannot fail")
        .replace('\u{2028}', "\\u2028")
        .replace('\u{2029}', "\\u2029")
}

fn typescript_type(v: &serde_json::Value) -> String {
    match v {
        serde_json::Value::Null => "null".into(),
        serde_json::Value::Bool(b) => b.to_string(),
        serde_json::Value::Number(_) => "number".into(),
        serde_json::Value::String(s) => js_string(s),
        serde_json::Value::Array(a) => format!(
            "readonly [{}]",
            a.iter().map(typescript_type).collect::<Vec<_>>().join(", ")
        ),
        serde_json::Value::Object(o) => format!(
            "{{ {} }}",
            o.iter()
                .map(|(k, v)| format!("readonly [{}]: {}", js_string(k), typescript_type(v)))
                .collect::<Vec<_>>()
                .join("; ")
        ),
    }
}

fn language_identifier(s: &str) -> bool {
    s.starts_with(|c: char| c.is_ascii_alphabetic() || c == '_')
        && s.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_')
}

fn native_target<'a>(entry: &'a ProjectedEntry, slot: &str) -> Result<&'a Entity, CheckError> {
    let Some(s) = entry.slots.iter().find(|s| s.name == slot) else {
        return Err(CheckError(vec![Issue::error(
            "NATIVE_BINDING_MISSING",
            "Selected binding slot is absent",
            &entry.subject.id,
        )]));
    };
    if s.targets.len() != 1 {
        return Err(CheckError(vec![Issue::error(
            "NATIVE_BINDING_AMBIGUOUS",
            "Native dispatch requires exactly one target",
            &entry.subject.id,
        )]));
    }
    Ok(&s.targets[0])
}

fn locator<'a>(entity: &'a Entity, scheme: &str) -> Result<&'a str, CheckError> {
    let found: Vec<_> = entity
        .locators
        .iter()
        .flatten()
        .filter_map(|l| l.uri.strip_prefix(scheme))
        .collect();
    if let [one] = found.as_slice() {
        Ok(one)
    } else {
        Err(CheckError(vec![Issue::error(
            "NATIVE_LOCATOR_AMBIGUOUS",
            "Exactly one target-language locator is required",
            &entity.id,
        )]))
    }
}

const TYPESCRIPT_RESERVED: &[&str] = &[
    "default",
    "class",
    "function",
    "const",
    "let",
    "var",
    "import",
    "export",
    "interface",
    "type",
    "enum",
    "await",
    "yield",
    "new",
    "return",
    "switch",
    "case",
    "delete",
    "extends",
    "implements",
    "static",
    "null",
    "true",
    "false",
    "dispatch",
    "SemanticId",
    "break",
    "catch",
    "continue",
    "debugger",
    "do",
    "else",
    "finally",
    "for",
    "if",
    "in",
    "instanceof",
    "super",
    "this",
    "throw",
    "try",
    "typeof",
    "void",
    "while",
    "with",
    "abstract",
    "declare",
    "private",
    "protected",
    "public",
    "readonly",
    "require",
    "global",
    "arguments",
    "eval",
    "JSON",
];
fn typescript_export_name(name: &str) -> bool {
    language_identifier(name) && !TYPESCRIPT_RESERVED.contains(&name)
}

/// Typed static data; JSON.parse avoids object-literal __proto__ interpretation.
/// An optional binding slot adds the draft fn(string)->string demonstration.
pub fn emit_typescript(
    projection: &CheckedProjection,
    export: &str,
    binding_slot: Option<&str>,
) -> Result<String, CheckError> {
    if !language_identifier(export)
        || TYPESCRIPT_RESERVED.contains(&export)
        || (binding_slot.is_some()
            && export
                .strip_prefix("handler")
                .is_some_and(|s| !s.is_empty() && s.bytes().all(|c| c.is_ascii_digit())))
    {
        return Err(CheckError(vec![Issue::error(
            "INVALID_EXPORT_NAME",
            "Invalid or reserved TypeScript export name",
            export,
        )]));
    }
    let mut imports = String::new();
    let mut arms = String::new();
    if let Some(slot) = binding_slot {
        for (i, e) in projection.record.entries.iter().enumerate() {
            let target = native_target(e, slot)?;
            let location = locator(target, "typescript:")?;
            let Some((module, symbol)) = location.rsplit_once('#') else {
                return Err(CheckError(vec![Issue::error(
                    "INVALID_NATIVE_LOCATOR",
                    "TypeScript locator needs a module#symbol",
                    &target.id,
                )]));
            };
            if !module.starts_with("./")
                || module.contains(['\n', '\r', '\\', '\0'])
                || module.split('/').any(|s| s == "..")
                || !language_identifier(symbol)
                || TYPESCRIPT_RESERVED.contains(&symbol)
            {
                return Err(CheckError(vec![Issue::error(
                    "INVALID_NATIVE_LOCATOR",
                    "TypeScript bindings need a relative module and valid symbol",
                    &target.id,
                )]));
            }
            // Explicitly target .js imports so ordinary NodeNext tsc resolves .ts.
            let module = module
                .strip_suffix(".ts")
                .map_or(module.to_owned(), |m| format!("{m}.js"));
            imports.push_str(&format!(
                "import {{ {symbol} as handler{i} }} from {};\n",
                js_string(&module)
            ));
            arms.push_str(&format!(
                "    case {}: return handler{i}(input);\n",
                js_string(&e.subject.id)
            ));
        }
    }
    let value = table(projection)?;
    let json = canonical_bytes(&value).map_err(CheckError::from)?;
    let json = String::from_utf8(json).expect("canonical JSON is UTF-8");
    let mut source = format!(
        "// Generated from {}; regenerate after correspondence changes.\n{imports}export const {export} = JSON.parse({}) as {};\nexport type SemanticId = keyof typeof {export};\n",
        projection.record.digest,
        js_string(&json),
        typescript_type(&value)
    );
    if binding_slot.is_some() {
        source.push_str(&format!("export function dispatch(id: SemanticId, input: string): string {{\n  switch (id) {{\n{arms}    default: throw new Error(\"Unknown semantic identity\");\n  }}\n}}\n"));
    }
    Ok(source)
}

pub fn emit_rust(
    projection: &CheckedProjection,
    binding_slot: Option<&str>,
) -> Result<String, CheckError> {
    let json = String::from_utf8(canonical_bytes(&projection.record).map_err(CheckError::from)?)
        .expect("canonical JSON is UTF-8");
    let mut source = format!(
        "// Generated from {}; regenerate after correspondence changes.\npub const PROJECTION_JSON: &str = {json:?};\n#[derive(Debug, Clone, Copy, PartialEq, Eq)]\npub struct SemanticId(&'static str);\nimpl SemanticId {{\n  pub fn as_str(self) -> &'static str {{ self.0 }}\n  pub fn parse(id: &str) -> Option<Self> {{\n    match id {{\n",
        projection.record.digest
    );
    for e in &projection.record.entries {
        source.push_str(&format!(
            "      {id:?} => Some(Self({id:?})),\n",
            id = e.subject.id
        ));
    }
    source.push_str("      _ => None,\n    }\n  }\n}\n");
    if let Some(slot) = binding_slot {
        source.push_str(
            "pub fn dispatch(id: SemanticId, input: &str) -> String {\n  match id.as_str() {\n",
        );
        const KEYWORDS: &[&str] = &[
            "self", "Self", "super", "fn", "mod", "use", "pub", "struct", "enum", "impl", "trait",
            "type", "const", "static", "let", "match", "if", "else", "for", "while", "loop", "in",
            "as", "where", "async", "await", "move", "return", "break", "continue", "unsafe",
            "extern", "crate", "_", "dyn", "false", "true", "mut", "ref", "abstract", "become",
            "box", "do", "final", "gen", "macro", "override", "priv", "try", "typeof", "unsized",
            "virtual", "yield",
        ];
        for e in &projection.record.entries {
            let target = native_target(e, slot)?;
            let symbol = locator(target, "rust:")?;
            let parts: Vec<_> = symbol.split("::").collect();
            if parts.len() < 2
                || parts[0] != "crate"
                || parts[1..]
                    .iter()
                    .any(|s| !language_identifier(s) || KEYWORDS.contains(s))
            {
                return Err(CheckError(vec![Issue::error(
                    "INVALID_NATIVE_LOCATOR",
                    "Rust binding must be a simple crate::module::symbol path",
                    &target.id,
                )]));
            }
            source.push_str(&format!("    {:?} => {symbol}(input),\n", e.subject.id));
        }
        source.push_str("    _ => unreachable!(\"SemanticId can only be constructed from known identities\"),\n  }\n}\n");
    }
    Ok(source)
}
