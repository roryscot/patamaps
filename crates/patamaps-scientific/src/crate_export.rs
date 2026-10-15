use crate::*;
use patamaps_contracts::*;
use patamaps_governance::{
    ArtifactEmission, EmissionLanguage, GovernedCandidate, prepare_candidate_artifacts,
    prepare_reference_artifacts,
};
use patamaps_projection::{CaptureRecord, replay};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    sync::OnceLock,
};

const PROFILE: &str = "urn:patamaps:scientific-crate:draft:1";
const RO_CRATE: &str = "https://w3id.org/ro/crate/1.2";
const CONTEXT: &str = "https://w3id.org/ro/crate/1.2/context";
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ExternalSource {
    pub id: String,
    pub name: String,
    pub description: String,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct CrateOptions {
    pub name: String,
    pub description: String,
    pub date_published: String,
    pub consumer: String,
    pub environment: String,
    pub source: ImportOptions,
    pub tsv_receipt: String,
    #[serde(
        default,
        deserialize_with = "patamaps_contracts::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub metadata_receipt: Option<String>,
    pub external_sources: Vec<ExternalSource>,
    /// Explicit included payloads keyed by receipt ID. Omission retains the
    /// original closed-source mode; an empty map requests references only.
    /// The capture must omit content for every receipt excluded from this map.
    #[serde(
        default,
        deserialize_with = "patamaps_contracts::present",
        skip_serializing_if = "Option::is_none"
    )]
    pub raw_inputs: Option<BTreeMap<String, String>>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ScientificCrate {
    pub metadata: Value,
    pub files: BTreeMap<String, String>,
}
/// Complete regenerated inventory, including checked replay and native outputs.
/// This establishes neither scientific truth nor approval or active state.
/// ```compile_fail
/// let forged: patamaps_scientific::CheckedScientificCrate = serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug, Serialize)]
#[serde(transparent)]
pub struct CheckedScientificCrate(ScientificCrate, #[serde(skip)] usize);
impl CheckedScientificCrate {
    pub fn record(&self) -> &ScientificCrate {
        &self.0
    }
    /// Receipt references whose raw bytes are absent from the complete package.
    pub fn external_raw_inputs(&self) -> usize {
        self.1
    }
}
pub fn scientific_engine_id() -> &'static str {
    static ID: OnceLock<String> = OnceLock::new();
    ID.get_or_init(|| canonical_digest(&json!({
        "profile": PROFILE, "compiler": patamaps_projection::executor_id(),
        "artifacts": patamaps_governance::governance_executor_id(),
        "manifest": include_str!("../Cargo.toml"), "lib": include_str!("lib.rs"),
        "model": include_str!("model.rs"), "syntax": include_str!("syntax.rs"),
        "interpret": include_str!("interpret.rs"), "export": include_str!("export.rs"),
        "source": include_str!("source.rs"),
        "legacyConfig": include_str!("legacy_config.rs"),
        "legacyConfigSchema": include_str!("../../../fixtures/reference/schemas/metamap-config.schema.json"),
        "sourceSchema": include_str!("../../../fixtures/reference/schemas/metamap-sssom-source.schema.json"),
        "graph": include_str!("graph.rs"), "crate": include_str!("crate_export.rs"),
        "modelSource": include_str!("../../../fixtures/reference/standards/sssom-1.0.0/sssom_schema.yaml"),
        "schema": include_str!("../../../fixtures/reference/schemas/sssom-1.0.0.schema.json"),
        "slots": include_str!("../../../fixtures/reference/schemas/sssom-1.0.0-slots.json"),
        "pack": include_str!("../../../relation-packs/scientific-skos.json"),
        "context": include_str!("../../../fixtures/scientific/ro-crate-1.2-context.jsonld")
    })).expect("finite embedded sources"))
}
fn text(s: &str) -> bool {
    !s.is_empty() && s.len() <= 4096 && !s.chars().any(char::is_control)
}
fn iri(s: &str) -> bool {
    text(s) && !s.chars().any(char::is_whitespace) && fluent_uri::Iri::parse(s).is_ok()
}
fn settings(o: &CrateOptions) -> Result<()> {
    if !text(&o.name)
        || !text(&o.description)
        || !text(&o.environment)
        || !patamaps_core::valid_identifier(&o.consumer)
        || o.external_sources.len() > 64
    {
        return refuse("SCIENTIFIC_CRATE_OPTIONS", "Invalid bounded crate options");
    }
    let parts: Vec<_> = o.date_published.split('-').collect();
    let date = (|| {
        if parts.len() != 3 || parts[0].len() != 4 || parts[1].len() != 2 || parts[2].len() != 2 {
            return None;
        }
        time::Date::from_calendar_date(
            parts[0].parse().ok()?,
            time::Month::try_from(parts[1].parse::<u8>().ok()?).ok()?,
            parts[2].parse().ok()?,
        )
        .ok()
    })();
    if date.is_none() {
        return refuse(
            "SCIENTIFIC_CRATE_OPTIONS",
            "datePublished requires a real YYYY-MM-DD date",
        );
    }
    let mut ids = BTreeSet::from([PROFILE, RO_CRATE, CONTEXT]);
    for e in &o.external_sources {
        if !iri(&e.id) || !text(&e.name) || !text(&e.description) || !ids.insert(&e.id) {
            return refuse(
                "SCIENTIFIC_CRATE_OPTIONS",
                "Invalid or duplicate external source",
            );
        }
    }
    Ok(())
}
fn receipt<'a>(c: &'a CaptureRecord, id: &str) -> Option<&'a str> {
    c.sources
        .iter()
        .find(|s| s.id == id)
        .and_then(|s| s.content.as_deref())
}
fn json_text<T: Serialize>(v: &T) -> Result<String> {
    Ok(String::from_utf8(canonical_bytes(v)?).expect("canonical UTF-8") + "\n")
}
fn source_matches(source: &GraphDocument, candidate: &GraphDocument) -> Result<()> {
    let mut remaining: BTreeMap<_, _> = candidate
        .mappings
        .iter()
        .map(|m| (m.id.as_str(), m))
        .collect();
    for m in &source.mappings {
        let Some(actual) = remaining.remove(m.id.as_str()) else {
            return refuse(
                "SCIENTIFIC_CRATE_SOURCE",
                "Candidate omitted a source assertion",
            );
        };
        let mut expected = m.clone();
        if !matches!(actual.lossiness, Lossiness::Unknown | Lossiness::Lossy) {
            return refuse(
                "SCIENTIFIC_CRATE_SOURCE",
                "Exploratory candidate may not relabel a source lossless",
            );
        }
        expected.lossiness = actual.lossiness;
        if canonical_bytes(&expected)? != canonical_bytes(actual)? {
            return refuse(
                "SCIENTIFIC_CRATE_SOURCE",
                "Candidate changed source assertion fields/provenance",
            );
        }
    }
    // Remaining assertions must be regenerated derivations; replay checks their
    // exact premises, context and rules. No extra unproved source declarations.
    for m in remaining.values() {
        if !m
            .attributes
            .as_ref()
            .is_some_and(|a| a.contains_key("metamap:derivation"))
        {
            return refuse(
                "SCIENTIFIC_CRATE_SOURCE",
                "Extra assertion is not a captured derivation",
            );
        }
    }
    let mut a = source.clone();
    a.mappings.clear();
    let mut b = candidate.clone();
    b.mappings.clear();
    if canonical_bytes(&a)? != canonical_bytes(&b)? {
        return refuse(
            "SCIENTIFIC_CRATE_SOURCE",
            "Candidate changed source graph/entity context",
        );
    }
    Ok(())
}
/// Pure closed, single-source profile. All source payloads are supplied capture
/// bytes; this function never reads paths, fetches IRIs, signs or activates.
pub fn create_crate(c: &CaptureRecord, o: &CrateOptions) -> Result<CheckedScientificCrate> {
    settings(o)?;
    let checked = replay(c)?;
    if c.result["status"] != "viable"
        || (o.raw_inputs.is_none() && !checked.missing_sources().is_empty())
    {
        return refuse(
            "SCIENTIFIC_CRATE_REPLAY",
            "Crate requires viable replay and every declared receipt's bytes",
        );
    }
    let specs: Vec<_> = c.inputs.specs().collect();
    if specs.is_empty() {
        return refuse("SCIENTIFIC_CRATE_REPLAY", "Consumer projection required");
    }
    let source_receipts: BTreeSet<_> = std::iter::once(o.tsv_receipt.as_str())
        .chain(o.metadata_receipt.as_deref())
        .collect();
    if c.sources.len() != source_receipts.len()
        || c.sources
            .iter()
            .any(|s| !source_receipts.contains(s.id.as_str()))
    {
        return refuse(
            "SCIENTIFIC_CRATE_SOURCE",
            "Crate requires exactly the configured single source's receipts",
        );
    }
    if let Some(raw_inputs) = &o.raw_inputs {
        for (id, bytes) in raw_inputs {
            let declared = c.sources.iter().find(|s| s.id == *id).ok_or_else(|| {
                Error::new(
                    "SCIENTIFIC_CRATE_SOURCE",
                    "Raw payload has no captured receipt",
                )
            })?;
            if byte_digest(bytes.as_bytes()) != declared.digest
                || bytes.len() as u64 != declared.byte_length.get()
                || declared.content.as_ref() != Some(bytes)
            {
                return refuse(
                    "SCIENTIFIC_CRATE_SOURCE",
                    "Raw payload does not match its captured receipt and content",
                );
            }
        }
        if c.sources
            .iter()
            .any(|s| s.content.is_some() != raw_inputs.contains_key(&s.id))
        {
            return refuse(
                "SCIENTIFIC_CRATE_SOURCE",
                "Capture content must exactly match the included payload inventory",
            );
        }
    }
    if o.metadata_receipt.as_deref() == Some(o.tsv_receipt.as_str()) {
        return refuse(
            "SCIENTIFIC_CRATE_SOURCE",
            "TSV and metadata receipts must be distinct",
        );
    }
    let captured_document = c
        .inputs
        .graph
        .metadata
        .as_ref()
        .and_then(|m| m.get("sssom"))
        .and_then(|v| v.get("rawDocument"))
        .ok_or_else(|| {
            Error::new(
                "SCIENTIFIC_CRATE_SOURCE",
                "Captured SSSOM document required",
            )
        })?;
    let document: SssomDocument = parse(&canonical_bytes(captured_document)?)?;
    let sssom = check_document(&document)?;
    let metadata = o.metadata_receipt.as_deref().and_then(|id| receipt(c, id));
    if let Some(raw) = receipt(c, &o.tsv_receipt) {
        // An absent external metadata payload cannot disable checks of included
        // TSV columns/rows. Use the explicitly recorded metadata only to parse
        // those bytes; this does not verify or fetch the missing metadata bytes.
        let recorded_metadata = if o.metadata_receipt.is_some() && metadata.is_none() {
            Some(canonical_bytes(&document.metadata)?)
        } else {
            None
        };
        let parsed = parse_tsv(
            raw.as_bytes(),
            metadata.map(str::as_bytes).or(recorded_metadata.as_deref()),
        )?;
        if canonical_bytes(parsed.document())? != canonical_bytes(sssom.document())? {
            return refuse(
                "SCIENTIFIC_CRATE_SOURCE",
                "Included raw bytes disagree with the captured SSSOM document",
            );
        }
    } else if let Some(raw) = metadata {
        let parsed = crate::syntax::metadata(
            crate::syntax::text(raw.as_bytes(), STRICT_JSON_LIMITS)?,
            STRICT_JSON_LIMITS,
        )?;
        if canonical_bytes(&parsed)? != canonical_bytes(&document.metadata)? {
            return refuse(
                "SCIENTIFIC_CRATE_SOURCE",
                "Included external metadata disagrees with the captured SSSOM document",
            );
        }
    }
    let source = import_graph(&sssom, &o.source)?;
    source_matches(&source, &c.inputs.graph)?;
    let exported = export_tsv(&sssom, false)?;
    let prepare = if o.raw_inputs.is_some() {
        prepare_reference_artifacts
    } else {
        prepare_candidate_artifacts
    };
    let prepared = prepare(
        &GovernedCandidate {
            captures: vec![c.clone()],
            emissions: specs
                .iter()
                .flat_map(|spec| {
                    [EmissionLanguage::Typescript, EmissionLanguage::Rust].map(|language| {
                        ArtifactEmission {
                            projection: spec.id.clone(),
                            language,
                            binding_slot: None,
                        }
                    })
                })
                .collect(),
        },
        &o.consumer,
        &o.environment,
    )?;
    let mut files = prepared.files().clone();
    files.insert(
        "artifact-manifest.json".into(),
        json_text(prepared.manifest())?,
    );
    files.insert("scientific-profile.json".into(), json_text(&json!({"schemaVersion":"0.1.0", "documentType":"scientific-crate-profile", "profile":PROFILE, "engine":scientific_engine_id(), "options":o}))?);
    files.insert("source-import.json".into(), json_text(&json!({"document":sssom.document(), "interpretation":sssom.interpretation(), "graph":source, "sourceOptions":o.source}))?);
    files.insert("export.sssom.tsv".into(), exported.text);
    files.insert("export-loss.json".into(), json_text(&exported.loss)?);
    files.insert(
        "ro-crate-context.jsonld".into(),
        include_str!("../../../fixtures/scientific/ro-crate-1.2-context.jsonld").into(),
    );
    let mut source_parts = Vec::new();
    let mut absent = Vec::new();
    for (i, s) in c.sources.iter().enumerate() {
        let Some(content) = &s.content else {
            let id = format!("urn:patamaps:raw-input:{}", &s.digest[7..]);
            source_parts.push(json!({"@id":id}));
            absent.push((id, s));
            continue;
        };
        let path = format!("source/source-{i}.txt");
        files.insert(path.clone(), content.clone());
        source_parts.push(json!({"@id":path}));
    }
    let license = sssom
        .interpretation()
        .metadata
        .get("license")
        .and_then(Value::as_str)
        .ok_or_else(|| {
            Error::new(
                "SCIENTIFIC_CRATE_OPTIONS",
                "Source-declared license required",
            )
        })?;
    if !iri(license) {
        return refuse(
            "SCIENTIFIC_CRATE_OPTIONS",
            "License must be an absolute IRI",
        );
    }
    let creators: Vec<String> = match sssom.interpretation().metadata.get("creator_id") {
        Some(Value::Array(v)) => v
            .iter()
            .filter_map(Value::as_str)
            .map(str::to_owned)
            .collect(),
        Some(Value::String(v)) => vec![v.clone()],
        _ => vec![],
    };
    let mut entities = vec![
        json!({"@id":"ro-crate-metadata.json", "@type":"CreativeWork", "name":"Scientific crate metadata", "about":{"@id":"./"}, "conformsTo":{"@id":RO_CRATE}}),
        json!({"@id":"./", "@type":"Dataset", "name":o.name, "description":format!("{}; scientific truth, current approval and activation are not established", o.description), "datePublished":o.date_published, "license":{"@id":license}, "creditText":creators.join(", "), "conformsTo":{"@id":PROFILE}, "hasPart":files.keys().map(|p| json!({"@id":p})).collect::<Vec<_>>(), "isBasedOn":o.external_sources.iter().map(|e|json!({"@id":e.id})).collect::<Vec<_>>() }),
        json!({"@id":license, "@type":"CreativeWork", "name":"Source-declared license", "identifier":license}),
        json!({"@id":RO_CRATE, "@type":"CreativeWork", "name":"RO-Crate 1.2 specification"}),
        json!({"@id":PROFILE, "@type":"CreativeWork", "name":"Patamaps single-source scientific crate draft 1"}),
    ];
    let external_raw_inputs = absent.len();
    for (id, s) in &absent {
        entities[1]["hasPart"]
            .as_array_mut()
            .expect("constructed parts")
            .push(json!({"@id":id}));
        entities.push(json!({"@id":id,"@type":"File","name":s.locator,"description":"Raw payload not included or fetched; captured digest is a reference only","sha256":&s.digest[7..],"contentSize":s.byte_length.get().to_string(),"license":{"@id":license}}));
    }
    for (path, bytes) in &files {
        let mut e = json!({"@id":path, "@type":"File", "name":path, "contentSize":bytes.len().to_string(), "sha256":&byte_digest(bytes.as_bytes())[7..], "encodingFormat":if path.ends_with(".tsv") {"text/tab-separated-values"} else if path.ends_with(".rs") {"text/rust"} else if path.ends_with(".ts") {"text/typescript"} else if path.ends_with(".txt") {"text/plain"} else {"application/json"}});
        if path.starts_with("source/") || path == "export.sssom.tsv" {
            e["license"] = json!({"@id":license});
        }
        if path == "source-import.json" {
            e["isBasedOn"] = json!(source_parts);
        }
        entities.push(e);
    }
    for e in &o.external_sources {
        entities.push(json!({"@id":e.id, "@type":"CreativeWork", "name":e.name, "description":format!("{}; external reference, not embedded or fetched",e.description)}));
    }
    let mut ids = BTreeSet::new();
    if entities
        .iter()
        .any(|e| !ids.insert(e["@id"].as_str().expect("constructed ID")))
    {
        return refuse(
            "SCIENTIFIC_CRATE_OPTIONS",
            "Conflicting JSON-LD entity identifiers",
        );
    }
    let result = ScientificCrate {
        metadata: json!({"@context":CONTEXT, "@graph":entities}),
        files,
    };
    bounds(&result)?;
    // Serialized transport, including repeated capture/source representations,
    // must fit the same strict ingress profile as verification.
    parse_value(&canonical_bytes(&result)?)?;
    Ok(CheckedScientificCrate(result, external_raw_inputs))
}
fn bounds(c: &ScientificCrate) -> Result<()> {
    patamaps_core::check_value_bounds(&c.metadata, PROFILE, "SCIENTIFIC_CRATE_RESOURCE_LIMIT")?;
    if c.files.is_empty()
        || c.files.len() > 256
        || c.files
            .iter()
            .try_fold(0usize, |n, (p, v)| {
                if p.len() > 4096 || v.len() > MAX_INPUT_BYTES {
                    None
                } else {
                    n.checked_add(p.len())?.checked_add(v.len())
                }
            })
            .is_none_or(|n| n > MAX_INPUT_BYTES)
    {
        return refuse(
            "SCIENTIFIC_CRATE_RESOURCE_LIMIT",
            "Crate file count/aggregate bytes exceed profile bounds",
        );
    }
    Ok(())
}
/// Recompute from captured source/replay/options, then compare the complete set
/// and every byte. A self-consistent substituted inventory is insufficient.
pub fn verify_crate(c: &ScientificCrate) -> Result<CheckedScientificCrate> {
    bounds(c)?;
    #[derive(Deserialize)]
    #[serde(rename_all = "camelCase", deny_unknown_fields)]
    struct Profile {
        schema_version: ProtocolVersion,
        document_type: String,
        profile: String,
        engine: String,
        options: CrateOptions,
    }
    let p: Profile = parse(
        c.files
            .get("scientific-profile.json")
            .ok_or_else(|| Error::new("SCIENTIFIC_CRATE_INVENTORY", "Missing profile"))?
            .as_bytes(),
    )?;
    let _ = p.schema_version;
    if p.document_type != "scientific-crate-profile"
        || p.profile != PROFILE
        || p.engine != scientific_engine_id()
    {
        return refuse(
            "SCIENTIFIC_CRATE_ENGINE",
            "Wrong scientific profile/executor",
        );
    }
    let capture: CaptureRecord = parse(
        c.files
            .get("capture-0.json")
            .ok_or_else(|| Error::new("SCIENTIFIC_CRATE_INVENTORY", "Missing replay"))?
            .as_bytes(),
    )?;
    let expected = create_crate(&capture, &p.options)?;
    if canonical_bytes(&c.metadata)? != canonical_bytes(&expected.0.metadata)?
        || c.files != expected.0.files
    {
        return refuse(
            "SCIENTIFIC_CRATE_INVENTORY",
            "Metadata, complete inventory or payload bytes differ from regenerated export",
        );
    }
    Ok(expected)
}
