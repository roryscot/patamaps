//! Original workspace config observations, alongside its SSSOM dependency.
//! Configs are returned unchanged; parsing never admits graphs or activates policy.
use crate::parse_sssom_source_config;
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson, LegacyPackJson, LegacyReadOnlyJson,
    parse_value_with_limits,
};
use patamaps_core::LegacyPortableSchema;
use serde::{Deserialize, Serialize};
use serde_json::value::RawValue;
use std::{collections::HashSet, path::Path, sync::OnceLock};

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyConfigError {
    pub code: String,
    pub name: String,
    pub message: Box<RawValue>,
}
fn failure(code: &str, name: &str, message: &str) -> LegacyConfigError {
    LegacyConfigError {
        code: code.into(),
        name: name.into(),
        message: LegacyReadOnlyJson::string_json(&LegacyReadOnlyJson::string_units(message)),
    }
}
fn schema() -> &'static LegacyPortableSchema {
    static CONFIG: OnceLock<LegacyPortableSchema> = OnceLock::new();
    CONFIG.get_or_init(|| {
        LegacyPortableSchema::new(include_str!(
            "../package-inputs/fixtures/reference/schemas/metamap-config.schema.json"
        ))
    })
}
fn read_json(bytes: &[u8]) -> Result<LegacyReadOnlyJson, LegacyConfigError> {
    let text = String::from_utf8_lossy(bytes);
    LegacyReadOnlyJson::parse(&text, COMPATIBILITY_JSON_LIMITS).map_err(|error| {
        // The existing file parser supplies pinned Node syntax diagnostics. Its
        // version dispatch is consulted only after read-only JSON parsing fails.
        let diagnostic = LegacyPackJson::parse(bytes.to_vec(), COMPATIBILITY_JSON_LIMITS)
            .err()
            .unwrap_or(error)
            .json_diagnostic(COMPATIBILITY_JSON_LIMITS);
        failure(
            diagnostic.code,
            if diagnostic.code == "INVALID_JSON_SYNTAX" {
                "SyntaxError"
            } else {
                "Error"
            },
            &diagnostic.message,
        )
    })
}
/// Schema first, then source/correspondence semantics in original source order.
pub fn parse_legacy_metamap_config(bytes: &[u8]) -> Result<Box<RawValue>, LegacyConfigError> {
    let json = read_json(bytes)?;
    let projection = json
        .schema_projection()
        .map_err(|e| failure("LEGACY_CONFIG_INPUT", "Error", &e.to_string()))?;
    let issues = schema().issues(&projection);
    if !issues.is_empty() {
        let message = issues
            .iter()
            .map(|issue| {
                format!(
                    "{} {}",
                    if issue.path.is_empty() {
                        "$config"
                    } else {
                        &issue.path
                    },
                    issue.message
                )
            })
            .collect::<Vec<_>>()
            .join("; ");
        return Err(failure(
            "LEGACY_CONFIG_SCHEMA",
            "Error",
            &format!("Metamap config does not match the portable schema: {message}"),
        ));
    }
    let value = json.value();
    let sources = value
        .get("sources")
        .and_then(LegacyOrderedJson::array)
        .expect("schema sources");
    let mut source_ids = HashSet::new();
    for source in sources {
        let id = source
            .get("id")
            .and_then(LegacyOrderedJson::string)
            .expect("schema source id");
        if !source_ids.insert(id) {
            return Err(failure(
                "LEGACY_CONFIG_SEMANTIC",
                "Error",
                &format!("Duplicate source id {id}"),
            ));
        }
        if source.get("adapter").and_then(LegacyOrderedJson::string) == Some("sssom-tsv") {
            let raw = LegacyReadOnlyJson::json_raw(source).expect("checked JSON serialization");
            // Original SSSOM parsing first canonicalizes. Preserve its strict
            // Unicode refusal rather than interpreting projected scalar runes.
            if let Err(error) =
                parse_value_with_limits(raw.get().as_bytes(), COMPATIBILITY_JSON_LIMITS)
            {
                let diagnostic = error.json_diagnostic(COMPATIBILITY_JSON_LIMITS);
                return Err(failure(
                    diagnostic.code,
                    "CanonicalJsonError",
                    &diagnostic.message,
                ));
            }
            parse_sssom_source_config(raw.get().as_bytes())
                .map_err(|e| failure(e.code, "SssomError", &e.message))?;
        }
    }
    let mut correspondence_ids = HashSet::new();
    for (index, correspondence) in value
        .get("correspondences")
        .and_then(LegacyOrderedJson::array)
        .expect("schema correspondences")
        .iter()
        .enumerate()
    {
        let id = correspondence
            .get("id")
            .and_then(LegacyOrderedJson::string)
            .expect("schema correspondence id");
        if !correspondence_ids.insert(id) {
            return Err(failure(
                "LEGACY_CONFIG_SEMANTIC",
                "Error",
                &format!("Duplicate correspondence id {id}"),
            ));
        }
        for side in ["source", "target"] {
            let source_id = correspondence
                .get(side)
                .and_then(|r| r.get("sourceId"))
                .and_then(LegacyOrderedJson::string)
                .expect("schema reference source id");
            if !source_ids.contains(source_id) {
                return Err(failure(
                    "LEGACY_CONFIG_SEMANTIC",
                    "Error",
                    &format!(
                        "$config.correspondences[{index}].{side} references unknown source {source_id}"
                    ),
                ));
            }
        }
    }
    LegacyReadOnlyJson::json_raw(value)
        .map_err(|e| failure("LEGACY_CONFIG_INPUT", "Error", &e.to_string()))
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LegacyConfigRequest {
    pub input: String,
}
pub fn legacy_config_request(
    request: LegacyConfigRequest,
) -> Result<Box<RawValue>, LegacyConfigError> {
    parse_legacy_metamap_config(request.input.as_bytes())
}
/// POSIX lexical resolution mirrors node:path.resolve; no realpath/symlink IO.
fn resolve_units(directory: &[u16], value: &[u16]) -> Vec<u16> {
    let mut joined = if value.first() == Some(&47) {
        Vec::new()
    } else {
        directory.to_vec()
    };
    joined.push(47);
    joined.extend_from_slice(value);
    let mut parts: Vec<&[u16]> = Vec::new();
    for part in joined.split(|u| *u == 47) {
        if part.is_empty() || part == [46] {
            continue;
        }
        if part == [46, 46] {
            parts.pop();
        } else {
            parts.push(part);
        }
    }
    let mut resolved = vec![47];
    for (index, part) in parts.iter().enumerate() {
        if index > 0 {
            resolved.push(47);
        }
        resolved.extend_from_slice(part);
    }
    resolved
}
pub fn resolve_legacy_config_path(path: &Path) -> std::io::Result<std::path::PathBuf> {
    let cwd = std::env::current_dir()?;
    let units = resolve_units(
        &cwd.to_string_lossy().encode_utf16().collect::<Vec<_>>(),
        &path.to_string_lossy().encode_utf16().collect::<Vec<_>>(),
    );
    Ok(String::from_utf16(&units)
        .expect("scalar filesystem path")
        .into())
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyLoadedConfig {
    pub config: Box<RawValue>,
    pub config_path: String,
    pub config_directory: String,
    pub repository_root: Box<RawValue>,
}
pub fn load_legacy_metamap_config_bytes(
    bytes: &[u8],
    path: &Path,
) -> Result<LegacyLoadedConfig, LegacyConfigError> {
    let config = parse_legacy_metamap_config(bytes)?;
    let json = read_json(config.get().as_bytes())?;
    let directory = path
        .parent()
        .expect("resolved absolute config parent")
        .to_string_lossy()
        .into_owned();
    let root = json
        .value()
        .get("repositoryRoot")
        .and_then(LegacyOrderedJson::string)
        .expect("schema root");
    let units = resolve_units(
        &directory.encode_utf16().collect::<Vec<_>>(),
        &LegacyReadOnlyJson::string_units(root),
    );
    Ok(LegacyLoadedConfig {
        config,
        config_path: path.to_string_lossy().into_owned(),
        config_directory: directory,
        repository_root: LegacyReadOnlyJson::string_json(&units),
    })
}
