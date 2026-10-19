//! Original v2 shape/content/helper contracts. These reports are not native
//! admitted generations and do not supply the unfinished v2 compiler/replay.
use crate::legacy_viability::{items, project, s, strings};
use crate::legacy_workspace::{error, get, native, obj, raw, scalar};
use crate::{LegacyPortableSchema, LegacyWorkspaceError, legacy_registry_request};
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyPackJson, LegacyReadOnlyJson as Data,
    canonical_digest,
};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

pub(crate) const RESOURCES: [&str; 8] = [
    include_str!("../package-inputs/fixtures/reference/schemas/metamap-graph.schema.json"),
    include_str!("../package-inputs/fixtures/reference/schemas/metamap-viability.schema.json"),
    include_str!("../package-inputs/fixtures/reference/schemas/metamap-generation.schema.json"),
    include_str!("../package-inputs/fixtures/reference/schemas/relation-pack.schema.json"),
    include_str!("../package-inputs/fixtures/reference/schemas/relation-pack-v2.schema.json"),
    include_str!("../package-inputs/fixtures/reference/schemas/metamap-derivation.schema.json"),
    include_str!("../package-inputs/fixtures/reference/schemas/metamap-viability-v2.schema.json"),
    include_str!("../package-inputs/fixtures/reference/schemas/metamap-generation-v2.schema.json"),
];
fn schema(kind: &str) -> &'static LegacyPortableSchema {
    static POLICY: OnceLock<LegacyPortableSchema> = OnceLock::new();
    static GENERATION: OnceLock<LegacyPortableSchema> = OnceLock::new();
    static PROOF: OnceLock<LegacyPortableSchema> = OnceLock::new();
    match kind {
        "policy" => {
            POLICY.get_or_init(|| LegacyPortableSchema::with_resources(RESOURCES[6], &RESOURCES))
        }
        "generation" => GENERATION
            .get_or_init(|| LegacyPortableSchema::with_resources(RESOURCES[7], &RESOURCES)),
        _ => PROOF.get_or_init(|| LegacyPortableSchema::with_resources(RESOURCES[5], &RESOURCES)),
    }
}
fn issue(code: &str, message: &str, subject: Option<&str>) -> J {
    let mut fields = vec![
        ("severity", scalar("error")),
        ("code", scalar(code)),
        ("message", scalar(message)),
    ];
    if let Some(subject) = subject.filter(|s| !s.is_empty()) {
        fields.push(("subjectId", scalar(subject)));
    }
    obj(fields)
}
fn shape(
    value: &J,
    kind: &str,
    code: &str,
    canonical_error: Option<&str>,
) -> Result<Vec<J>, LegacyWorkspaceError> {
    if let Some(message) = canonical_error {
        return Ok(vec![issue(code, message, None)]);
    }
    Ok(schema(kind)
        .legacy_issues(value, &HashSet::new())
        .into_iter()
        .map(|finding| {
            obj(vec![
                ("severity", scalar("error")),
                ("code", scalar(code)),
                ("message", scalar(&finding.message)),
                (
                    "path",
                    scalar(if finding.path.is_empty() {
                        "$"
                    } else {
                        &finding.path
                    }),
                ),
            ])
        })
        .collect())
}
fn addressed_content(value: &J) -> Result<J, LegacyWorkspaceError> {
    let J::Object(fields) = value else {
        return Err(error(
            "TypeError",
            "Semantic address input requires a captured object-rest snapshot",
        ));
    };
    Ok(J::Object(
        fields
            .iter()
            .filter(|(key, _)| !["id", "digest"].contains(&key.as_str()))
            .cloned()
            .collect(),
    ))
}
fn digest(value: &J) -> Result<String, LegacyWorkspaceError> {
    canonical_digest(&project(value)?).map_err(|e| error("Error", &e.to_string()))
}
fn validate_policy(
    value: &J,
    canonical_error: Option<&str>,
) -> Result<Vec<J>, LegacyWorkspaceError> {
    let mut issues = shape(value, "policy", "INVALID_SEMANTIC_POLICY", canonical_error)?;
    if !issues.is_empty() {
        return Ok(issues);
    }
    let mut identities = HashSet::new();
    let mut ids = vec![s(value, "id")];
    for field in [
        "constraints",
        "evidence",
        "waivers",
        "derivations",
        "assessments",
        "uncertaintyRequirements",
        "riskBudgets",
    ] {
        ids.extend(items(value, field).iter().map(|record| s(record, "id")));
    }
    for id in ids {
        if !identities.insert(id) {
            issues.push(issue(
                "DUPLICATE_SEMANTIC_POLICY_ID",
                "Policy record identities must be unique",
                Some(id),
            ));
        }
    }
    Ok(issues)
}
pub(crate) fn uncertainty_summary_issues(summaries: &[J]) -> Vec<J> {
    let mut issues = Vec::new();
    let mut ids = HashSet::new();
    for summary in summaries {
        let id = s(summary, "mapping");
        if !ids.insert(id) {
            issues.push(issue(
                "DUPLICATE_UNCERTAINTY_SUMMARY",
                "Each mapping requires one uncertainty summary",
                Some(id),
            ));
        }
        let dimensions = items(summary, "dimensions");
        if dimensions.len() != 6
            || dimensions
                .iter()
                .map(|entry| s(entry, "dimension"))
                .collect::<HashSet<_>>()
                .len()
                != 6
        {
            issues.push(issue(
                "INCOMPLETE_UNCERTAINTY_SUMMARY",
                "Each uncertainty dimension must appear exactly once",
                Some(id),
            ));
        }
        for entry in dimensions {
            if s(entry, "status") != "unknown" && items(entry, "assessments").is_empty() {
                issues.push(issue(
                    "UNBOUND_UNCERTAINTY_STATE",
                    "A known state requires contributing assessment identities",
                    Some(id),
                ));
            }
            for field in [
                "evidence",
                "assessments",
                "measurementModels",
                "sourceRevisions",
            ] {
                let values = items(entry, field);
                if values
                    .iter()
                    .filter_map(J::string)
                    .collect::<HashSet<_>>()
                    .len()
                    != values.len()
                {
                    issues.push(issue(
                        "DUPLICATE_UNCERTAINTY_REFERENCE",
                        "Summary references must be unique",
                        Some(id),
                    ));
                }
            }
        }
    }
    issues
}
fn parse_proof(proof: &J) -> Result<(), LegacyWorkspaceError> {
    let findings = schema("proof").legacy_issues(proof, &HashSet::new());
    if !findings.is_empty() {
        return Err(error(
            "Error",
            &format!(
                "Invalid correspondence derivation: {}",
                findings
                    .iter()
                    .map(|e| format!(
                        "{} {}",
                        if e.path.is_empty() { "$" } else { &e.path },
                        e.message
                    ))
                    .collect::<Vec<_>>()
                    .join("; ")
            ),
        ));
    }
    if items(proof, "uncertainty")
        .iter()
        .map(|v| s(v, "dimension"))
        .collect::<HashSet<_>>()
        .len()
        != 6
    {
        return Err(error(
            "Error",
            "Derivation requires each uncertainty dimension exactly once",
        ));
    }
    let digest = digest(&addressed_content(proof)?)?;
    if s(proof, "digest") != digest
        || s(proof, "id")
            != format!(
                "urn:metamap:derivation:{}",
                digest.trim_start_matches("sha256:")
            )
    {
        return Err(error("Error", "Derivation content binding mismatch"));
    }
    Ok(())
}
fn registry_call(state: &Value, action: Value) -> Result<Value, LegacyWorkspaceError> {
    let request = serde_json::from_value(json!({"state":state,"action":action}))
        .map_err(|e| error("TypeError", &e.to_string()))?;
    legacy_registry_request(request).map_err(|e| error("Error", &e.message))
}
fn captured_packs(semantic: &J) -> Result<(), LegacyWorkspaceError> {
    let mut state = json!({"packs":[],"definitions":[],"laws":[]});
    for pack in items(semantic, "packs") {
        let value = get(pack, "value")?;
        let encoded = raw(value)?;
        let registered = registry_call(&state, json!({"operation":"register","json":encoded}))?;
        if registered["inserted"] == true {
            state["packs"]
                .as_array_mut()
                .expect("pack state")
                .push(json!({"key":s(value,"id"),"json":encoded}));
            state["definitions"]
                .as_array_mut()
                .expect("definition state")
                .extend(
                    registered["relationIds"]
                        .as_array()
                        .expect("registered relations")
                        .iter()
                        .cloned(),
                );
            for (index, id) in registered["lawIds"]
                .as_array()
                .expect("registered laws")
                .iter()
                .enumerate()
            {
                state["laws"]
                    .as_array_mut()
                    .expect("law state")
                    .push(json!({"id":id,"pack":s(value,"id"),"index":index}));
            }
        }
    }
    for pack in items(semantic, "packs") {
        let value = get(pack, "value")?;
        let binding = get(pack, "binding")?;
        let parsed = LegacyPackJson::parse(raw(value)?.into_bytes(), COMPATIBILITY_JSON_LIMITS)
            .map_err(|e| error("Error", &e.to_string()))?;
        let address = patamaps_contracts::byte_digest(
            &parsed
                .portable_digest_bytes()
                .map_err(|e| error("Error", &e.to_string()))?,
        );
        if s(binding, "id") != s(value, "id")
            || s(binding, "version") != s(value, "version")
            || s(binding, "digest") != address
        {
            return Err(error("Error", "Captured pack does not match its binding"));
        }
    }
    for pack in items(semantic, "packs").iter().filter(|pack| {
        pack.get("value")
            .is_some_and(|v| s(v, "schemaVersion") == "2.0.0")
    }) {
        for law in items(get(pack, "value")?, "laws") {
            registry_call(&state, json!({"operation":"get-law","id":s(law,"id")}))?;
        }
    }
    Ok(())
}
fn validate_generation(
    value: &J,
    canonical_error: Option<&str>,
) -> Result<Vec<J>, LegacyWorkspaceError> {
    let mut issues = shape(
        value,
        "generation",
        "INVALID_SEMANTIC_GENERATION",
        canonical_error,
    )?;
    if !issues.is_empty() {
        return Ok(issues);
    }
    let digest = digest(&addressed_content(value)?)?;
    let id = s(value, "id");
    if s(value, "digest") != digest
        || id
            != format!(
                "urn:metamap:generation:{}",
                digest.trim_start_matches("sha256:")
            )
    {
        return Ok(vec![issue(
            "SEMANTIC_GENERATION_DIGEST_MISMATCH",
            "Generation content binding does not match its identity",
            Some(id),
        )]);
    }
    let semantic = get(value, "semantic")?;
    let summaries = items(semantic, "uncertainty");
    issues.extend(uncertainty_summary_issues(summaries));
    let assessments = items(semantic, "assessments")
        .iter()
        .map(|entry| (s(entry, "id"), entry))
        .collect::<HashMap<_, _>>();
    let declarations = items(semantic, "declarations")
        .iter()
        .map(|entry| s(entry, "mapping"))
        .collect::<HashSet<_>>();
    let summary_ids = summaries
        .iter()
        .map(|entry| s(entry, "mapping"))
        .collect::<HashSet<_>>();
    if assessments.len() != items(semantic, "assessments").len()
        || declarations.len() != summary_ids.len()
        || declarations.iter().any(|id| !summary_ids.contains(id))
    {
        issues.push(issue(
            "INCOMPLETE_GENERATION_UNCERTAINTY",
            "Captured assessments and mapping summaries must be complete and unique",
            Some(id),
        ));
    }
    for summary in summaries {
        for dimension in items(summary, "dimensions") {
            let references = strings(dimension, "assessments");
            if references.iter().any(|id| {
                assessments
                    .get(id.as_str())
                    .is_none_or(|entry| s(entry, "dimension") != s(dimension, "dimension"))
            }) || strings(dimension, "evidence").iter().any(|id| {
                !references.iter().any(|reference| {
                    assessments
                        .get(reference.as_str())
                        .is_some_and(|entry| strings(entry, "evidence").contains(id))
                })
            }) {
                issues.push(issue("UNBOUND_GENERATION_UNCERTAINTY","Summary references must name captured contributing assessments and their evidence",Some(s(summary,"mapping"))));
            }
        }
    }
    if s(semantic, "riskEvaluation")
        != if items(semantic, "riskBudgets").is_empty() {
            "not-evaluated"
        } else {
            "available-for-projection"
        }
    {
        issues.push(issue(
            "INVALID_GENERATION_RISK_STATE",
            "Risk availability must match captured budgets",
            Some(id),
        ));
    }
    if !issues.is_empty() {
        return Ok(issues);
    }
    for proof in items(semantic, "derivations") {
        if let Err(cause) = parse_proof(proof) {
            let message: String = serde_json::from_str(cause.message.get()).expect("error text");
            return Ok(vec![issue(
                "SEMANTIC_DERIVATION_BINDING_MISMATCH",
                &message,
                Some(id),
            )]);
        }
    }
    if let Err(cause) = captured_packs(semantic) {
        let message: String = serde_json::from_str(cause.message.get()).expect("error text");
        return Ok(vec![issue(
            "SEMANTIC_PACK_BINDING_MISMATCH",
            &message,
            Some(id),
        )]);
    }
    Ok(issues)
}
fn report(value: J) -> J {
    let keys = items(&value, "issues")
        .iter()
        .map(|issue| match issue {
            J::Object(fields) => fields
                .iter()
                .map(|(name, _)| name.clone())
                .collect::<Vec<_>>(),
            _ => vec![],
        })
        .collect::<Vec<_>>();
    obj(vec![("value", value), ("issueKeys", native(keys))])
}
fn validation(issues: Vec<J>) -> J {
    report(obj(vec![
        ("valid", J::Bool(issues.is_empty())),
        ("issues", J::Array(issues)),
    ]))
}
pub(crate) fn request(operation: &str, input: &J) -> Result<J, LegacyWorkspaceError> {
    let null = J::Null;
    let value = input.get("value").unwrap_or(&null);
    let canonical_error = input.get("canonicalError").and_then(J::string);
    match operation {
        "semantic-validate-policy" => Ok(validation(validate_policy(value, canonical_error)?)),
        "semantic-validate-generation" => {
            Ok(validation(validate_generation(value, canonical_error)?))
        }
        "semantic-parse-policy" | "semantic-parse-generation" => {
            let issues = if operation == "semantic-parse-policy" {
                validate_policy(value, canonical_error)?
            } else {
                validate_generation(value, canonical_error)?
            };
            if !issues.is_empty() {
                return Err(error(
                    "Error",
                    &issues
                        .iter()
                        .map(|i| {
                            format!(
                                "{} {}",
                                i.get("path").and_then(J::string).unwrap_or("$"),
                                s(i, "message")
                            )
                        })
                        .collect::<Vec<_>>()
                        .join("; "),
                ));
            }
            Ok(report(value.clone()))
        }
        "semantic-digest" => Ok(report(scalar(&digest(&addressed_content(value)?)?))),
        "semantic-view" => {
            let fields = get(input, "fields")?
                .array()
                .ok_or_else(|| error("TypeError", "Policy-view fields require an array"))?;
            let keep = fields
                .iter()
                .enumerate()
                .filter(|(_, value)| {
                    !matches!(
                        value.string(),
                        Some(
                            "derivations"
                                | "derivationLimits"
                                | "assessments"
                                | "uncertaintyRequirements"
                                | "riskBudgets"
                        )
                    )
                })
                .map(|(index, _)| index)
                .collect::<Vec<_>>();
            Ok(report(native(json!({"keep":keep,"schemaVersion":"1.0.0"}))))
        }
        "semantic-dependencies" => {
            let graph = get(input, "graph")?;
            let active = strings(input, "active").into_iter().collect::<HashSet<_>>();
            let records = items(input, "records")
                .iter()
                .map(|record| (s(record, "id"), record))
                .collect::<HashMap<_, _>>();
            let mut mappings = items(graph, "mappings")
                .iter()
                .filter(|mapping| active.contains(s(mapping, "id")))
                .collect::<Vec<_>>();
            mappings.sort_by_key(|mapping| Data::string_units(s(mapping, "id")));
            let result = mappings
                .into_iter()
                .map(|mapping| {
                    let proof = mapping
                        .get("attributes")
                        .and_then(|attributes| attributes.get("metamap:derivation"))
                        .and_then(J::string)
                        .and_then(|id| records.get(id));
                    let mut fields = vec![("mapping", scalar(s(mapping, "id")))];
                    let mut premises = proof
                        .map(|proof| {
                            items(proof, "premises")
                                .iter()
                                .map(|entry| s(entry, "mapping").to_owned())
                                .collect::<HashSet<_>>()
                                .into_iter()
                                .collect::<Vec<_>>()
                        })
                        .unwrap_or_default();
                    premises.sort_by_key(|id| Data::string_units(id));
                    fields.push(("premises", native(premises)));
                    if let Some(proof) = proof {
                        fields.push((
                            "derivation",
                            obj(vec![
                                ("id", get(proof, "id").expect("proof id").clone()),
                                (
                                    "digest",
                                    get(proof, "digest").expect("proof digest").clone(),
                                ),
                            ]),
                        ));
                    }
                    obj(fields)
                })
                .collect();
            Ok(report(J::Array(result)))
        }
        _ => Err(error(
            "TypeError",
            "Unknown original semantic helper operation",
        )),
    }
}
