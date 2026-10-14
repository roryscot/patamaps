use patamaps_contracts::*;
use patamaps_core::{CheckError, CheckedGraph, ImpactReport, Issue, impact};
use patamaps_projection::{CaptureRecord, compare, replay};
use patamaps_workspace::{VerifiedSourceEvaluation, compare_source_evaluations};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SelectionKind {
    Entity,
    Mapping,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct InspectionSelection {
    pub kind: SelectionKind,
    pub id: String,
}

/// The renderer consumes the same immutable verified report returned to the CLI.
/// ```compile_fail
/// let forged:patamaps_inspect::CheckedExplanation=serde_json::from_str("{}").unwrap();
/// ```
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CheckedExplanation {
    id: String,
    digest: String,
    record: Value,
}
impl CheckedExplanation {
    pub fn record(&self) -> &Value {
        &self.record
    }
    pub fn digest(&self) -> &str {
        &self.digest
    }
}
fn state(n: usize) -> &'static str {
    match n {
        0 => "missing",
        1 => "known",
        _ => "ambiguous",
    }
}
fn serialized<T: Serialize>(value: T) -> Result<Value, CheckError> {
    Ok(serde_json::to_value(value).map_err(ContractError::from)?)
}
fn focused<'a>(
    records: &'a BTreeMap<String, Vec<Value>>,
    selected: Option<&str>,
    dependencies: &BTreeSet<String>,
    limit: usize,
) -> Vec<(&'a String, &'a Vec<Value>)> {
    let mut rows: Vec<_> = records.iter().collect();
    let priority = |id: &String| {
        if selected == Some(id.as_str()) {
            0
        } else if dependencies.contains(id) {
            1
        } else {
            2
        }
    };
    rows.sort_by(|(a, _), (b, _)| (priority(a), a).cmp(&(priority(b), b)));
    rows.truncate(limit);
    rows
}
pub fn explain(
    capture: &CaptureRecord,
    before: Option<&CaptureRecord>,
    selection: InspectionSelection,
    maximum_subjects: usize,
    maximum_mappings: usize,
) -> Result<CheckedExplanation, CheckError> {
    let verified = replay(capture)?;
    if maximum_subjects == 0
        || maximum_subjects > 256
        || maximum_mappings == 0
        || maximum_mappings > 512
    {
        return Err(CheckError(vec![Issue::error(
            "EXPLANATION_RESOURCE_LIMIT",
            "Inspection permits 1..256 subjects and 1..512 mappings",
            "inspection",
        )]));
    }
    let graph = &capture.inputs.graph;
    let (mut entities, mut mappings) = (
        BTreeMap::<String, Vec<Value>>::new(),
        BTreeMap::<String, Vec<Value>>::new(),
    );
    for e in &graph.entities {
        entities
            .entry(e.id.clone())
            .or_default()
            .push(serialized(e)?);
    }
    for m in &graph.mappings {
        mappings
            .entry(m.id.clone())
            .or_default()
            .push(serialized(m)?);
    }
    let occurrences = match selection.kind {
        SelectionKind::Entity => entities.get(&selection.id),
        SelectionKind::Mapping => mappings.get(&selection.id),
    }
    .map_or(0, Vec::len);
    let mut dependency_ids = BTreeSet::from([selection.id.clone()]);
    for m in &graph.mappings {
        if m.id == selection.id
            || m.sources.contains(&selection.id)
            || m.targets.contains(&selection.id)
        {
            dependency_ids.extend(m.sources.iter().chain(&m.targets).cloned());
            dependency_ids.insert(m.id.clone());
        }
    }
    let (selected_entity, selected_mapping) = match selection.kind {
        SelectionKind::Entity => (Some(selection.id.as_str()), None),
        SelectionKind::Mapping => (None, Some(selection.id.as_str())),
    };
    let subjects:Vec<_>=focused(&entities,selected_entity,&dependency_ids,maximum_subjects).into_iter().map(|(id,records)|json!({"id":id,"state":state(records.len()),"records":records,"relevance":if dependency_ids.contains(id){"selection-or-dependency"}else{"other"}})).collect();
    let mapped:Vec<_>=focused(&mappings,selected_mapping,&dependency_ids,maximum_mappings).into_iter().map(|(id,records)|{
        let active=capture.result["generation"]["activeMappings"].as_array().map(|ids|ids.iter().any(|v|v==id));
        json!({"id":id,"state":state(records.len()),"records":records,"activity":match active{Some(true)=>"active",Some(false)=>"inactive",None=>"unavailable"},"relevance":if dependency_ids.contains(id){"selection-or-dependency"}else{"other"}})
    }).collect();
    let actual_impact: Option<ImpactReport> =
        CheckedGraph::check(graph.clone(), capture.inputs.packs.clone())
            .ok()
            .map(|g| impact(&g, std::slice::from_ref(&selection.id), 32))
            .transpose()?;
    let comparison = match before {
        Some(old) => match compare(&replay(old)?, &verified) {
            Ok(report) => json!({"status":"compared","report":report}),
            Err(e) => json!({"status":"unavailable","issues":e.0}),
        },
        None => json!({"status":"unavailable","reason":"No before capture supplied"}),
    };
    let issues = capture.result["issues"]
        .as_array()
        .map(|items| {
            items
                .iter()
                .map(|issue| {
                    let subject = issue["subjectId"].as_str().unwrap_or("");
                    let relevant = if subject == selection.id {
                        "selection"
                    } else if dependency_ids.contains(subject) {
                        "dependency"
                    } else if subject.is_empty() || subject == graph.id {
                        "global"
                    } else {
                        "other"
                    };
                    json!({"issue":issue,"relevance":relevant})
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let record = json!({"schemaVersion":"0.1.0","documentType":"explanation","capture":{"id":capture.id,"digest":capture.digest},"consumer":capture.inputs.projection_spec.as_ref().and_then(|s|s.consumer.clone().or_else(||s.semantics.as_ref().map(|s|s.consumer.clone()))),
        "selection":{"kind":selection.kind,"id":selection.id,"state":state(occurrences),"occurrences":occurrences},"admission":capture.result["status"],"subjects":subjects,"mappings":mapped,
        "ownership":{"interpretation":"declared-fact-ownership","authentication":"not-evaluated","declarations":graph.authorities},
        "sources":{"receipts":capture.sources,"missingBytes":verified.missing_sources(),"membership":"not-captured; no attribution inferred from labels or locators"},
        "policy":capture.inputs.policy,"relationPacks":capture.inputs.packs,"context":capture.inputs.context,"evaluatedAt":capture.inputs.evaluated_at,
        "generation":capture.result["generation"],"projection":capture.result["projection"],"pathTree":capture.result["pathTree"],"projections":capture.result.get("projections"),"projectionSpecifications":capture.inputs.specs().collect::<Vec<_>>(),"issues":issues,"comparison":comparison,"impact":actual_impact,
        "navigation":{"subjectIds":subjects.iter().map(|s|&s["id"]).collect::<Vec<_>>(),"mappingIds":mapped.iter().map(|s|&s["id"]).collect::<Vec<_>>(),"omittedSubjects":entities.len().saturating_sub(subjects.len()),"omittedMappings":mappings.len().saturating_sub(mapped.len()),"status":if entities.len()>subjects.len()||mappings.len()>mapped.len(){"truncated"}else{"complete"}},
        "approval":{"status":"not-evaluated","currentAuthority":"not-evaluated","active":"not-evaluated","reason":"Captured ownership and viability do not establish current external approval or active host state"},
        "causality":{"interpretation":"Observed input differences and declared dependency paths; unique causal responsibility is not established"}});
    parse_value(&canonical_bytes(&record)?)?;
    let digest = canonical_digest(&record)?;
    Ok(CheckedExplanation {
        id: format!("urn:patamaps:explanation:{}", &digest[7..]),
        digest,
        record,
    })
}
/// Explain the same candidate with its separately verified source composition.
/// Every source claim is recomputed from checked workspace records; this does
/// not read a locator, authenticate a provider or authorize an activation.
pub fn explain_source(
    evaluation: &VerifiedSourceEvaluation<'_>,
    before: Option<&VerifiedSourceEvaluation<'_>>,
    selection: InspectionSelection,
    maximum_subjects: usize,
    maximum_mappings: usize,
) -> Result<CheckedExplanation, CheckError> {
    let source_error = |error: patamaps_workspace::Error| {
        CheckError(vec![Issue::error(
            "EXPLANATION_SOURCE_BINDING",
            error.to_string(),
            "source-inspection",
        )])
    };
    if before.is_some_and(|old| old.source_graph().id != evaluation.source_graph().id) {
        return Err(CheckError(vec![Issue::error(
            "EXPLANATION_SOURCE_BASELINE",
            "Source comparison requires the same workspace graph ID",
            "source-inspection",
        )]));
    }
    let source = evaluation.inspect().map_err(source_error)?;
    let mut report = explain(
        evaluation.candidate().record(),
        before.map(|v| v.candidate().record()),
        selection,
        maximum_subjects,
        maximum_mappings,
    )?;
    report.record["sources"]["membership"] = json!("verified-recorded-shards-to-candidate-inputs");
    report.record["sources"]["inspection"] = source.record().clone();
    if let Some(old) = before {
        let compared = compare_source_evaluations(old, evaluation).map_err(source_error)?;
        report.record["sources"]["comparison"] =
            json!({"status":"compared","report":compared.record()});
    }
    parse_value(&canonical_bytes(&report.record)?)?;
    report.digest = canonical_digest(&report.record)?;
    report.id = format!("urn:patamaps:explanation:{}", &report.digest[7..]);
    Ok(report)
}

fn escape(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for c in value.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(c),
        }
    }
    out
}
fn detail(title: &str, value: &Value) -> String {
    format!(
        "<details><summary>{}</summary><pre tabindex=\"0\">{}</pre></details>",
        escape(title),
        escape(&serde_json::to_string_pretty(value).expect("checked JSON report"))
    )
}
pub fn render_debugger(report: &CheckedExplanation) -> Result<String, CheckError> {
    let r = report.record();
    let mut html = String::from(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none';style-src 'sha256-83ElXRu8oOR4amJ7F7IhlAyK/5wERtC+CrN06+JnFJ4=';base-uri 'none';form-action 'none'\"><title>Patamaps inspection</title><style>:root{color-scheme:light dark;font:16px/1.55 system-ui}body{margin:0 auto;max-width:1100px;padding:24px}section{border:1px solid #8887;border-radius:8px;padding:20px;margin:20px 0}a{color:LinkText}nav{display:flex;flex-wrap:wrap;gap:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:28rem;overflow:auto;background:#8881;padding:16px}a:focus-visible,summary:focus-visible,pre:focus-visible{outline:3px solid #bd7000;outline-offset:4px}.skip{position:absolute;top:-80px}.skip:focus{top:8px}summary{cursor:pointer}h1,h2,p,li{overflow-wrap:anywhere}.notice{border-left:4px solid #bd7000;padding:12px}article{border-top:1px solid #8885;padding-top:12px;margin-top:16px}</style></head><body><a class=\"skip\" href=\"#main\">Skip to inspection</a><header><p>Patamaps · offline inspection</p><h1>",
    );
    html.push_str(&escape(
        r["selection"]["id"].as_str().unwrap_or("Unknown selection"),
    ));
    html.push_str("</h1><p class=\"notice\">Read-only captured evidence. No change is applied. Current approval and activation are not evaluated; missing or rejected data remains visible.</p><nav aria-label=\"Inspection sections\">");
    for (id, title) in [
        ("decision", "Decision"),
        ("subjects", "Subjects"),
        ("mappings", "Mappings"),
        ("semantics", "Proofs and risk"),
        ("sources", "Sources"),
        ("changes", "Changes"),
        ("raw", "Shared JSON report"),
    ] {
        html.push_str(&format!("<a href=\"#{id}\">{title}</a>"));
    }
    html.push_str("</nav></header><main id=\"main\" tabindex=\"-1\">");
    let mut section = |id: &str, title: &str, body: String| {
        html.push_str(&format!("<section id=\"{id}\" aria-labelledby=\"{id}-title\"><h2 id=\"{id}-title\">{title}</h2>{body}</section>"));
    };
    section(
        "decision",
        "Decision",
        format!(
            "<p>Admission: <strong>{}</strong>. Selection: <strong>{}</strong>. Navigation: <strong>{}</strong>.</p>{}",
            escape(r["admission"].as_str().unwrap_or("unavailable")),
            escape(r["selection"]["state"].as_str().unwrap_or("unknown")),
            escape(r["navigation"]["status"].as_str().unwrap_or("unknown")),
            detail("Issues and their recorded subjects", &r["issues"])
        ),
    );
    for (name, title) in [("subjects", "Subjects"), ("mappings", "Mappings")] {
        let mut body = String::new();
        for item in r[name].as_array().expect("checked arrays") {
            let id = item["id"].as_str().expect("checked ID");
            let anchor = byte_digest(id.as_bytes());
            body.push_str(&format!(
                "<article id=\"{name}-{}\"><h3>{}</h3><p>Record state: {}</p>{}</article>",
                &anchor[7..],
                escape(id),
                escape(item["state"].as_str().unwrap_or("unknown")),
                detail("Captured records", item)
            ));
        }
        if body.is_empty() {
            body.push_str("<p>No records are available in this bounded view.</p>");
        }
        section(name, title, body);
    }
    section(
        "semantics",
        "Proofs, uncertainty, budget and declared ownership",
        detail(
            "Checked generation; null means unavailable",
            &r["generation"],
        ) + &detail("Projection and its complete risk closure", &r["projection"])
            + &detail("Path tree", &r["pathTree"])
            + &detail(
                "Ownership declarations; authentication not evaluated",
                &r["ownership"],
            )
            + &detail(
                "Exact policy, evidence and law declarations",
                &json!({"policy":r["policy"],"packs":r["relationPacks"]}),
            ),
    );
    section(
        "sources",
        "Sources",
        detail("Captured receipts and missing bytes", &r["sources"]),
    );
    section(
        "changes",
        "Observed changes and declared dependency paths",
        detail("Comparison", &r["comparison"])
            + &detail("Impact; no assertion of unique causality", &r["impact"]),
    );
    section(
        "raw",
        "Shared JSON report",
        detail(
            "The same report used by CLI inspection",
            &serde_json::to_value(report).map_err(ContractError::from)?,
        ),
    );
    html.push_str("</main><footer><p>Capture-bound inspection; no external resources or executable candidate content.</p></footer></body></html>");
    if html.len() > MAX_INPUT_BYTES {
        return Err(CheckError(vec![Issue::error(
            "DEBUGGER_RESOURCE_LIMIT",
            "Rendered document exceeds bounded output",
            "debugger",
        )]));
    }
    Ok(html)
}
