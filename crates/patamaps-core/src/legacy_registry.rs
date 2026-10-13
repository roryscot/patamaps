//! Ordered legacy registry decisions over live host snapshots. These reports
//! never create a checked or admitted generation. Host object identity remains
//! in the SDK; registration and executable-law decisions are made here.
use crate::ParsedLegacyRelationPack;
use patamaps_contracts::{COMPATIBILITY_JSON_LIMITS, LegacyPackJson, SafeInteger, byte_digest};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LegacyRegistryState {
    #[serde(default)]
    packs: Vec<PackSnapshot>,
    #[serde(default)]
    definitions: Vec<String>,
    #[serde(default)]
    laws: Vec<LawHandle>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct PackSnapshot {
    key: String,
    json: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct LawHandle {
    id: String,
    pack: String,
    index: SafeInteger,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "operation", rename_all = "kebab-case", deny_unknown_fields)]
pub enum LegacyRegistryOperation {
    Register { json: String },
    GetPack { id: String },
    Get { id: String },
    HasPack { id: String, version: Option<String> },
    GetLaw { id: String },
    All,
    AllPacks,
    ExecutablePacks,
    CorePack,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LegacyRegistryRequest {
    #[serde(default)]
    state: LegacyRegistryState,
    action: LegacyRegistryOperation,
}

#[derive(Debug, thiserror::Error, Serialize)]
#[error("{message}")]
pub struct LegacyRegistryError {
    pub code: String,
    pub message: String,
}

fn error(message: impl Into<String>) -> LegacyRegistryError {
    LegacyRegistryError {
        code: "LEGACY_REGISTRY".into(),
        message: message.into(),
    }
}
fn input_error(message: impl Into<String>) -> LegacyRegistryError {
    LegacyRegistryError {
        code: "LEGACY_REGISTRY_INPUT".into(),
        message: message.into(),
    }
}
fn text<'a>(value: &'a Value, key: &str) -> Result<&'a str, LegacyRegistryError> {
    value
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| input_error(format!("Legacy registry requires a string {key}")))
}
fn array<'a>(value: &'a Value, key: &str) -> Result<&'a [Value], LegacyRegistryError> {
    value
        .get(key)
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .ok_or_else(|| input_error(format!("Legacy registry requires an array {key}")))
}
struct RegistryPack {
    source: LegacyPackJson,
    value: Value,
}
impl RegistryPack {
    fn executable(&self) -> bool {
        self.source.executable()
    }
    fn value(&self) -> &Value {
        &self.value
    }
}
fn parse_snapshot(raw: &str) -> Result<RegistryPack, LegacyRegistryError> {
    LegacyPackJson::parse(raw.as_bytes().to_vec(), COMPATIBILITY_JSON_LIMITS)
        .map(|source| RegistryPack {
            value: source.registry_comparison_projection(),
            source,
        })
        .map_err(|e| input_error(e.to_string()))
}
fn validate_shape(raw: &str) -> Result<(), LegacyRegistryError> {
    ParsedLegacyRelationPack::parse(raw.as_bytes().to_vec())
        .map(|_| ())
        .map_err(|e| LegacyRegistryError {
            code: e.code,
            message: e.message,
        })
}

/// Evaluate one operation against current host-owned snapshots. Returned
/// indices select retained host handles, so changing an object's ID never
/// renames its registration key or changes another retained object reference.
pub fn legacy_registry_request(
    request: LegacyRegistryRequest,
) -> Result<Value, LegacyRegistryError> {
    let state = request.state;
    if matches!(request.action, LegacyRegistryOperation::CorePack) {
        return Ok(json!(include_str!("legacy_core.json")));
    }
    let packs = state
        .packs
        .iter()
        .map(|p| parse_snapshot(&p.json))
        .collect::<Result<Vec<_>, _>>()?;
    let find_pack = |id: &str| state.packs.iter().position(|p| p.key == id);
    match request.action {
        LegacyRegistryOperation::Register { json: raw } => {
            let pack = parse_snapshot(&raw)?;
            let value = pack.value();
            if pack.executable() {
                validate_shape(&raw)?;
                validate_executable(value, &state, &packs, &mut HashSet::new())?;
            }
            let id = text(value, "id")?;
            let version = text(value, "version")?;
            if let Some(index) = find_pack(id) {
                let existing = packs[index].value();
                if existing.get("version") != value.get("version") {
                    return Err(error(format!(
                        "Relation pack {id} is already registered at version {}",
                        text(existing, "version")?
                    )));
                }
                // Host snapshots are JSON.stringify output, whose member order
                // is observable here even when canonical addresses are equal.
                if state.packs[index].json != raw {
                    return Err(error(format!(
                        "Relation pack {id}@{version} conflicts with its registered definition"
                    )));
                }
                return Ok(json!({"inserted":false}));
            }
            let mut incoming = HashSet::new();
            let relations = array(value, "relations")?
                .iter()
                .map(|relation| {
                    let id = text(relation, "id")?;
                    if state.definitions.iter().any(|key| key == id) || !incoming.insert(id) {
                        return Err(error(format!("Relation {id} is already registered")));
                    }
                    Ok(id)
                })
                .collect::<Result<Vec<_>, _>>()?;
            let laws = if pack.executable() {
                array(value, "laws")?
                    .iter()
                    .map(|law| text(law, "id"))
                    .collect::<Result<Vec<_>, _>>()?
            } else {
                Vec::new()
            };
            Ok(
                json!({"inserted":true,"packId":id,"relationIds":relations,"lawIds":laws,"executable":pack.executable()}),
            )
        }
        LegacyRegistryOperation::GetPack { id } => Ok(json!(find_pack(&id))),
        LegacyRegistryOperation::Get { id } => {
            Ok(json!(state.definitions.iter().position(|key| key == &id)))
        }
        LegacyRegistryOperation::HasPack { id, version } => {
            Ok(json!(find_pack(&id).is_some_and(|i| {
                version.as_ref().filter(|v| !v.is_empty()).is_none_or(|v| {
                    packs[i].value().get("version").and_then(Value::as_str) == Some(v)
                })
            })))
        }
        LegacyRegistryOperation::All => Ok(json!((0..state.definitions.len()).collect::<Vec<_>>())),
        LegacyRegistryOperation::AllPacks => Ok(json!((0..packs.len()).collect::<Vec<_>>())),
        LegacyRegistryOperation::ExecutablePacks => Ok(json!(
            packs
                .iter()
                .enumerate()
                .filter_map(|(i, p)| p.executable().then_some(i))
                .collect::<Vec<_>>()
        )),
        LegacyRegistryOperation::GetLaw { id } => {
            let Some(law) = state.laws.iter().find(|law| law.id == id) else {
                return Ok(Value::Null);
            };
            let Some(index) = find_pack(&law.pack) else {
                return Err(input_error("Missing registered law pack"));
            };
            validate_executable(packs[index].value(), &state, &packs, &mut HashSet::new())?;
            Ok(json!({"pack":index,"law":law.index.get()}))
        }
        LegacyRegistryOperation::CorePack => unreachable!(),
    }
}

fn compatible(sets: &[Option<&Value>]) -> bool {
    let restricted = sets
        .iter()
        .flatten()
        .filter_map(|s| s.as_array())
        .collect::<Vec<_>>();
    restricted.first().is_none_or(|first| {
        first
            .iter()
            .any(|kind| restricted.iter().all(|s| s.contains(kind)))
    })
}
fn unconditional(law: &Value) -> bool {
    law.get("conditions")
        .is_none_or(|c| c.as_object().is_some_and(|c| c.is_empty()))
}

fn validate_executable<'a>(
    pack: &'a Value,
    state: &LegacyRegistryState,
    packs: &'a [RegistryPack],
    validated: &mut HashSet<String>,
) -> Result<(), LegacyRegistryError> {
    let id = text(pack, "id")?;
    if !validated.insert(id.into()) {
        return Ok(());
    }
    let mut definitions = HashMap::new();
    let mut imports = HashSet::new();
    for binding in pack
        .get("imports")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        let imported = text(binding, "id")?;
        if imported == id || !imports.insert(imported) {
            return Err(error(format!("Duplicate or self-imported pack {imported}")));
        }
        let missing = || {
            error(format!(
                "Missing exact imported pack {imported}@{}",
                binding["version"].as_str().unwrap_or("undefined")
            ))
        };
        let index = state
            .packs
            .iter()
            .position(|p| p.key == imported)
            .ok_or_else(missing)?;
        let dependency = &packs[index];
        let value = dependency.value();
        let digest = byte_digest(
            &dependency
                .source
                .portable_digest_bytes()
                .map_err(|e| input_error(e.to_string()))?,
        );
        if value.get("version") != binding.get("version")
            || binding["digest"].as_str() != Some(&digest)
        {
            return Err(missing());
        }
        validate_shape(&state.packs[index].json)?;
        if dependency.executable() {
            validate_executable(value, state, packs, validated)?;
        }
        for relation in array(value, "relations")? {
            definitions.insert(text(relation, "id")?, relation);
        }
    }
    let mut owned = HashSet::new();
    for relation in array(pack, "relations")? {
        let relation_id = text(relation, "id")?;
        if definitions.contains_key(relation_id) || !owned.insert(relation_id) {
            return Err(error(format!("Duplicate relation {relation_id} in {id}")));
        }
        definitions.insert(relation_id, relation);
    }
    let laws = array(pack, "laws")?;
    let mut rules = HashSet::new();
    for law in laws {
        let law_id = text(law, "id")?;
        if !rules.insert(law_id)
            || state
                .laws
                .iter()
                .any(|existing| existing.id == law_id && existing.pack != id)
        {
            return Err(error(format!("Duplicate law {law_id}")));
        }
        let operands = array(law, "operands")?
            .iter()
            .map(|operand| {
                operand
                    .as_str()
                    .and_then(|key| definitions.get(key))
                    .copied()
            })
            .collect::<Vec<_>>();
        let result = definitions.get(text(law, "resultRelation")?).copied();
        if result.is_none() || operands.iter().any(Option::is_none) {
            return Err(error(format!(
                "Law {law_id} references a relation outside its pack or exact imports"
            )));
        }
        let first = operands
            .first()
            .copied()
            .flatten()
            .ok_or_else(|| input_error("Missing executable-law operand"))?;
        let result = result.expect("validated result");
        let conditions = &law["conditions"];
        if law["operation"] == "reverse" {
            if !compatible(&[
                first.get("targetKinds"),
                result.get("sourceKinds"),
                conditions.get("sourceKinds"),
            ]) || !compatible(&[
                first.get("sourceKinds"),
                result.get("targetKinds"),
                conditions.get("targetKinds"),
            ]) {
                return Err(error(format!(
                    "Law {law_id} has incompatible reverse endpoint kinds"
                )));
            }
            if let Some(inverse) = first
                .get("inverse")
                .and_then(Value::as_str)
                .filter(|v| !v.is_empty())
                && result["id"] != inverse
            {
                return Err(error(format!("Law {law_id} contradicts inverse {inverse}")));
            }
            if first["id"] == result["id"] && first["symmetric"] == false {
                return Err(error(format!(
                    "Law {law_id} contradicts declared non-symmetry"
                )));
            }
        } else {
            let second = operands
                .get(1)
                .copied()
                .flatten()
                .ok_or_else(|| input_error("Missing executable-law chain operand"))?;
            if !compatible(&[
                first.get("targetKinds"),
                second.get("sourceKinds"),
                conditions.get("middleKinds"),
            ]) || !compatible(&[
                first.get("sourceKinds"),
                result.get("sourceKinds"),
                conditions.get("sourceKinds"),
            ]) || !compatible(&[
                second.get("targetKinds"),
                result.get("targetKinds"),
                conditions.get("targetKinds"),
            ]) {
                return Err(error(format!(
                    "Law {law_id} has incompatible chain endpoint kinds"
                )));
            }
            if first["id"] == second["id"]
                && result["id"] == first["id"]
                && first["transitive"] == false
            {
                return Err(error(format!(
                    "Law {law_id} contradicts declared non-transitivity"
                )));
            }
        }
    }
    for definition in array(pack, "relations")? {
        let relation = text(definition, "id")?;
        let reverse = |result: &str| {
            laws.iter().any(|law| {
                unconditional(law)
                    && law["operation"] == "reverse"
                    && law["operands"][0] == relation
                    && law["resultRelation"] == result
            })
        };
        if definition["symmetric"] == true && !reverse(relation) {
            return Err(error(format!(
                "Symmetric relation {relation} needs an executable reverse law"
            )));
        }
        if definition["transitive"] == true
            && !laws.iter().any(|law| {
                unconditional(law)
                    && law["operation"] == "chain"
                    && law["operands"][0] == relation
                    && law["operands"][1] == relation
                    && law["resultRelation"] == relation
            })
        {
            return Err(error(format!(
                "Transitive relation {relation} needs an executable chain law"
            )));
        }
        if let Some(inverse) = definition
            .get("inverse")
            .and_then(Value::as_str)
            .filter(|v| !v.is_empty())
            && (!definitions.contains_key(inverse) || !reverse(inverse))
        {
            return Err(error(format!(
                "Inverse relation {relation} needs a referenced inverse and executable law"
            )));
        }
        for other in definition
            .get("composesWith")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            if !laws.iter().any(|law| {
                law["operation"] == "chain"
                    && law["operands"][0] == relation
                    && law["operands"][1] == *other
            }) {
                return Err(error(format!(
                    "Relation {relation} needs an executable chain with {}",
                    other.as_str().unwrap_or("undefined")
                )));
            }
        }
        for other in definition
            .get("disjointWith")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            if other
                .as_str()
                .is_none_or(|key| !definitions.contains_key(key) || key == relation)
            {
                return Err(error(format!(
                    "Invalid disjoint relation {} for {relation}",
                    other.as_str().unwrap_or("undefined")
                )));
            }
        }
    }
    Ok(())
}
