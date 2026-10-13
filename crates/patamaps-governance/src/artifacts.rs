use crate::{model::*, util::*};
use patamaps_contracts::*;
use patamaps_core::{CheckedGraph, EvaluationOptions, admit};
use patamaps_projection::{CaptureRecord, emit_rust, emit_typescript, project, replay};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

pub(crate) fn candidate_bounds(candidate: &GovernedCandidate) -> Result<()> {
    if candidate.captures.is_empty()
        || candidate.captures.len() > 16
        || candidate.emissions.len() > 32
    {
        return fail(
            "GOVERNANCE_RESOURCE_LIMIT",
            "Candidate needs one through sixteen captures and at most thirty-two native emissions",
        );
    }
    for c in &candidate.captures {
        value_bounds(&c.result)?;
        patamaps_core::check_input_bounds(
            &c.inputs.graph,
            &c.inputs.packs,
            &c.inputs.policy,
            &c.inputs.context,
        )?;
        for spec in c.inputs.specs() {
            patamaps_core::check_metadata_bounds(
                spec.metadata.iter().map(|m| (m, 4)),
                &spec.id,
                "GOVERNANCE_RESOURCE_LIMIT",
            )?;
        }
        let g = &c.inputs.graph;
        patamaps_core::check_metadata_bounds(
            g.metadata
                .iter()
                .chain(g.extensions.iter())
                .map(|m| (m, 4))
                .chain(
                    g.entities
                        .iter()
                        .filter_map(|e| e.attributes.as_ref())
                        .map(|m| (m, 6)),
                )
                .chain(
                    g.mappings
                        .iter()
                        .filter_map(|m| m.attributes.as_ref())
                        .map(|m| (m, 6)),
                ),
            &g.id,
            "GOVERNANCE_RESOURCE_LIMIT",
        )?;
        // Existing admission/pack/spec checks bound their own recursive fields.
        // Replayed output metadata is separately bounded before serialization.
    }
    Ok(())
}
fn common(c: &CaptureRecord) -> Result<Vec<u8>> {
    Ok(canonical_bytes(
        &serde_json::json!({"graph":c.inputs.graph,"packs":c.inputs.packs,"policy":c.inputs.policy,"context":c.inputs.context,"evaluatedAt":c.inputs.evaluated_at,"sources":c.sources}),
    )?)
}
pub(crate) fn normalized_candidate(
    candidate: &GovernedCandidate,
    consumer: &str,
) -> Result<GovernedCandidate> {
    normalize(candidate, consumer, true)
}

pub(crate) fn normalized_reference_candidate(
    candidate: &GovernedCandidate,
    consumer: &str,
) -> Result<GovernedCandidate> {
    normalize(candidate, consumer, false)
}

fn normalize(
    candidate: &GovernedCandidate,
    consumer: &str,
    require_source_bytes: bool,
) -> Result<GovernedCandidate> {
    candidate_bounds(candidate)?;
    let mut ids = BTreeSet::new();
    for c in &candidate.captures {
        let checked = replay(c)?;
        if require_source_bytes && !checked.missing_sources().is_empty() {
            return fail(
                "GOVERNANCE_MISSING_SOURCE_BYTES",
                "Governed candidates require bytes for every declared source receipt",
            );
        }
        if c.result["status"] != "viable" {
            return fail(
                "GOVERNANCE_CANDIDATE_REJECTED",
                "Every selected capture must be freshly viable",
            );
        }
        if c.inputs.specs().next().is_none() {
            return fail(
                "GOVERNANCE_WRONG_CONSUMER",
                "Every capture needs an explicit consumer projection",
            );
        }
        for spec in c.inputs.specs() {
            let declared = spec
                .consumer
                .as_deref()
                .or(spec.semantics.as_ref().map(|s| s.consumer.as_str()));
            if declared != Some(consumer) || !ids.insert(&spec.id) {
                return fail(
                    "GOVERNANCE_WRONG_CONSUMER",
                    "Projection consumers must match and specification identities must be unique",
                );
            }
        }
    }
    let candidate: GovernedCandidate = normalized(candidate)?;
    let expected = common(&candidate.captures[0])?;
    for capture in candidate.captures.iter().skip(1) {
        if common(capture)? != expected {
            return fail(
                "GOVERNANCE_INCONSISTENT_CAPTURES",
                "Selected captures must share exact graph, packs, policy, context, time and source receipts",
            );
        }
    }
    let mut emissions = BTreeSet::new();
    for e in &candidate.emissions {
        if !ids.contains(&e.projection) || !emissions.insert(canonical_bytes(e)?) {
            return fail(
                "GOVERNANCE_INVALID_EMISSION",
                "Native emissions must name selected projections and be unique",
            );
        }
    }
    Ok(candidate)
}
pub(crate) struct Artifacts {
    pub manifest: ArtifactManifest,
    pub files: BTreeMap<String, String>,
}
struct Writer {
    files: BTreeMap<String, String>,
    bytes: usize,
}
impl Writer {
    fn add(&mut self, path: String, value: String) -> Result<()> {
        self.bytes = self.bytes.saturating_add(value.len());
        if self.bytes > MAX_INPUT_BYTES {
            return fail(
                "GOVERNANCE_RESOURCE_LIMIT",
                "Complete artifact bytes exceed profile bound",
            );
        }
        if self.files.insert(path, value).is_some() {
            return fail(
                "GOVERNANCE_INVALID_MANIFEST",
                "Duplicate generated artifact path",
            );
        }
        Ok(())
    }
    fn json<T: Serialize>(&mut self, path: &str, value: &T) -> Result<()> {
        let mut bytes = canonical_bytes(value)?;
        bytes.push(b'\n');
        self.add(
            path.into(),
            String::from_utf8(bytes).expect("canonical UTF-8"),
        )
    }
}
pub(crate) fn prepare_artifacts(
    candidate: &GovernedCandidate,
    consumer: &str,
    environment: &str,
) -> Result<Artifacts> {
    let first = &candidate.captures[0];
    let graph = CheckedGraph::check(first.inputs.graph.clone(), first.inputs.packs.clone())?;
    let generation = admit(
        &graph,
        &first.inputs.policy,
        EvaluationOptions {
            context: first.inputs.context.clone(),
            evaluated_at: first.inputs.evaluated_at.clone(),
        },
    )?;
    let mut writer = Writer {
        files: BTreeMap::new(),
        bytes: 0,
    };
    writer.json("graph.json", &first.inputs.graph)?;
    writer.json("policy.json", &first.inputs.policy)?;
    writer.json("relation-packs.json", &first.inputs.packs)?;
    writer.json("source-receipts.json", &first.sources)?;
    writer.json("generation.json", generation.record())?;
    let mut projections = BTreeMap::new();
    for (i, c) in candidate.captures.iter().enumerate() {
        writer.json(&format!("capture-{i}.json"), c)?;
        if !c.inputs.projection_specs.is_empty() {
            let outcomes = c.result["projections"]
                .as_array()
                .expect("fresh collection result");
            for (j, spec) in c.inputs.projection_specs.iter().enumerate() {
                let outcome = outcomes
                    .iter()
                    .find(|outcome| outcome["specId"] == spec.id)
                    .expect("fresh outcome for every specification");
                writer.json(&format!("projection-{i}-{j}.json"), &outcome["projection"])?;
                if !outcome["pathTree"].is_null() {
                    writer.json(&format!("path-tree-{i}-{j}.json"), &outcome["pathTree"])?;
                }
                projections.insert(&spec.id, project(&generation, spec)?);
            }
            continue;
        }
        writer.json(&format!("projection-{i}.json"), &c.result["projection"])?;
        if !c.result["pathTree"].is_null() {
            writer.json(&format!("path-tree-{i}.json"), &c.result["pathTree"])?;
        }
        let spec = c
            .inputs
            .projection_spec
            .as_ref()
            .expect("checked consumer specification");
        projections.insert(&spec.id, project(&generation, spec)?);
    }
    for (i, e) in candidate.emissions.iter().enumerate() {
        let p = &projections[&e.projection];
        let (extension, bytes) = match e.language {
            EmissionLanguage::Rust => ("rs", emit_rust(p, e.binding_slot.as_deref())?),
            EmissionLanguage::Typescript => (
                "ts",
                emit_typescript(p, "bindings", e.binding_slot.as_deref())?,
            ),
        };
        writer.add(format!("bindings-{i}.{extension}"), bytes)?;
    }
    let mut manifest = ArtifactManifest {
        schema_version: ProtocolVersion::Draft1,
        document_type: ArtifactType::Draft1,
        profile: GovernanceProfile::Draft1,
        id: String::new(),
        digest: String::new(),
        consumer: consumer.into(),
        environment: environment.into(),
        captures: candidate
            .captures
            .iter()
            .map(|c| ContentBinding {
                id: c.id.clone(),
                digest: c.digest.clone(),
            })
            .collect(),
        files: writer
            .files
            .iter()
            .map(|(path, bytes)| ArtifactFile {
                path: path.clone(),
                media_type: if path.ends_with(".rs") {
                    ArtifactMediaType::Rust
                } else if path.ends_with(".ts") {
                    ArtifactMediaType::Typescript
                } else {
                    ArtifactMediaType::Json
                },
                byte_digest: byte_digest(bytes.as_bytes()),
                byte_length: SafeInteger::new(bytes.len() as u64).expect("bounded output"),
            })
            .collect(),
    };
    manifest.digest = document_digest(&manifest)?;
    manifest.id = address("artifacts", &manifest.digest);
    Ok(Artifacts {
        manifest,
        files: writer.files,
    })
}
