//! Legacy read-only diff/report behavior. These observations confer no graph
//! validation, admission, authority, approval or activation capability.
use icu_collator::{Collator, CollatorBorrowed, CollatorPreferences};
use patamaps_contracts::{
    COMPATIBILITY_JSON_LIMITS, LegacyOrderedJson as J, LegacyReadOnlyJson as Data,
};
use serde::{Deserialize, Serialize, Serializer};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LegacyReportingRequest {
    pub action: LegacyReportingAction,
    #[serde(default = "default_locale")]
    pub locale: String,
}
fn default_locale() -> String {
    "en-US".into()
}
#[derive(Debug, Deserialize)]
#[serde(tag = "operation", rename_all = "kebab-case", deny_unknown_fields)]
pub enum LegacyReportingAction {
    StableJson {
        value: String,
        #[serde(default)]
        pretty: bool,
    },
    ValueDigest {
        value: String,
    },
    Diff {
        before: String,
        after: String,
    },
    EmptyDiff,
    DriftReport {
        input: String,
    },
    GraphDocumentation {
        graph: String,
        correspondences: String,
    },
}
#[derive(Debug, thiserror::Error, Serialize)]
#[error("{message}")]
pub struct LegacyReportingError {
    pub code: String,
    pub name: String,
    pub message: String,
}
fn error(message: impl Into<String>) -> LegacyReportingError {
    LegacyReportingError {
        code: "LEGACY_REPORTING_INPUT".into(),
        name: "Error".into(),
        message: message.into(),
    }
}
fn parse(text: &str) -> Result<Data, LegacyReportingError> {
    Data::parse(text, COMPATIBILITY_JSON_LIMITS).map_err(|e| error(e.to_string()))
}
fn list<'a>(value: &'a J, field: &str) -> Result<&'a [J], LegacyReportingError> {
    value
        .get(field)
        .and_then(J::array)
        .ok_or_else(|| error(format!("Read-only legacy {field} requires an array")))
}
fn string<'a>(value: &'a J, field: &str) -> Result<&'a str, LegacyReportingError> {
    value
        .get(field)
        .and_then(J::string)
        .ok_or_else(|| error(format!("Read-only legacy {field} requires a string")))
}
fn collator(locale: &str) -> Result<CollatorBorrowed<'static>, LegacyReportingError> {
    let prefs = CollatorPreferences::from_locale_strict(
        &locale
            .parse()
            .map_err(|_| error("Invalid reporting locale"))?,
    )
    .map_err(|_| error("Unsupported reporting locale preferences"))?;
    Collator::try_new(prefs, Default::default()).map_err(|e| error(e.to_string()))
}
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct LegacyReportText(pub(crate) Vec<u16>);
impl Serialize for LegacyReportText {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        Data::string_json(&self.0).serialize(serializer)
    }
}
impl From<&str> for LegacyReportText {
    fn from(s: &str) -> Self {
        Self(s.encode_utf16().collect())
    }
}
impl From<String> for LegacyReportText {
    fn from(s: String) -> Self {
        Self::from(s.as_str())
    }
}
impl From<usize> for LegacyReportText {
    fn from(n: usize) -> Self {
        Self::from(n.to_string())
    }
}
impl From<&LegacyReportText> for LegacyReportText {
    fn from(s: &LegacyReportText) -> Self {
        s.clone()
    }
}
impl LegacyReportText {
    pub(crate) fn source(s: &str) -> Self {
        Self(Data::string_units(s))
    }
    pub(crate) fn join(items: &[Self], separator: &str) -> Self {
        let mut out = Vec::new();
        for (index, item) in items.iter().enumerate() {
            if index > 0 {
                out.extend(separator.encode_utf16());
            }
            out.extend(&item.0);
        }
        Self(out)
    }
    fn escaped(&self) -> Self {
        let mut out = Vec::new();
        for &unit in &self.0 {
            match unit {
                124 => out.extend([92, 124]),
                10 => out.push(32),
                _ => out.push(unit),
            }
        }
        Self(out)
    }
    fn equals(&self, s: &str) -> bool {
        self.0.iter().copied().eq(s.encode_utf16())
    }
}
macro_rules! line {
    ($($part:expr),* $(,)?) => { LegacyReportText::join(&[$(LegacyReportText::from($part)),*], "") };
}
pub(crate) fn js_text(value: Option<&J>) -> LegacyReportText {
    match value {
        None => "undefined".into(),
        Some(J::String(s)) => LegacyReportText::source(s),
        Some(J::Array(items)) => LegacyReportText::join(
            &items
                .iter()
                .map(|v| {
                    if matches!(v, J::Null) {
                        "".into()
                    } else {
                        js_text(Some(v))
                    }
                })
                .collect::<Vec<_>>(),
            ",",
        ),
        Some(other) => other.js_text().into(),
    }
}
fn nullish(value: Option<&J>, fallback: &str) -> LegacyReportText {
    if value.is_none_or(|v| matches!(v, J::Null)) {
        fallback.into()
    } else {
        js_text(value)
    }
}
fn optional_join(value: Option<&J>) -> Result<LegacyReportText, LegacyReportingError> {
    match value {
        None | Some(J::Null) => Ok("".into()),
        Some(J::Array(items)) => Ok(LegacyReportText::join(
            &items
                .iter()
                .map(|v| {
                    if matches!(v, J::Null) {
                        "".into()
                    } else {
                        js_text(Some(v))
                    }
                })
                .collect::<Vec<_>>(),
            ", ",
        )),
        _ => Err(error("Read-only legacy joined field requires an array")),
    }
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyGraphChange {
    change: &'static str,
    kind: &'static str,
    id: LegacyReportText,
    #[serde(skip_serializing_if = "Option::is_none")]
    changed_properties: Option<Vec<LegacyReportText>>,
}
#[derive(Debug, Default, Serialize)]
pub struct LegacyDiffCounts {
    added: usize,
    removed: usize,
    changed: usize,
}
#[derive(Debug, Default, Serialize)]
pub struct LegacyGraphDiff {
    changes: Vec<LegacyGraphChange>,
    counts: LegacyDiffCounts,
}
#[derive(Debug, Serialize)]
#[serde(untagged)]
pub enum LegacyReportingResponse {
    Diff(LegacyGraphDiff),
    Text(LegacyReportText),
}
fn stable(value: &J, col: &CollatorBorrowed<'_>) -> Result<Vec<u8>, LegacyReportingError> {
    Data::stable_bytes(value, col).map_err(|e| error(e.to_string()))
}
fn equivalent(
    left: Option<&J>,
    right: Option<&J>,
    col: &CollatorBorrowed<'_>,
) -> Result<bool, LegacyReportingError> {
    match (left, right) {
        (None, None) => Ok(true),
        (Some(a), Some(b)) => Ok(stable(a, col)? == stable(b, col)?),
        _ => Ok(false),
    }
}
fn indexed(items: &[J]) -> Result<Vec<(&str, &J)>, LegacyReportingError> {
    let mut slots = HashMap::new();
    let mut records = Vec::new();
    for record in items {
        let id = string(record, "id")?;
        if let Some(&slot) = slots.get(id) {
            records[slot] = (id, record);
        } else {
            slots.insert(id, records.len());
            records.push((id, record));
        }
    }
    Ok(records)
}
fn changed_properties(
    left: &J,
    right: &J,
    col: &CollatorBorrowed<'_>,
) -> Result<Vec<LegacyReportText>, LegacyReportingError> {
    let mut keys = HashSet::new();
    for value in [left, right] {
        if let J::Object(items) = value {
            keys.extend(items.iter().map(|(key, _)| key.as_str()));
        }
    }
    let mut changed = Vec::new();
    for key in keys {
        if !equivalent(left.get(key), right.get(key), col)? {
            changed.push(LegacyReportText::source(key));
        }
    }
    // The reference uses Array.sort() here: UTF-16 ordinal, not locale order.
    changed.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(changed)
}
fn diff(
    before: &J,
    after: &J,
    col: &CollatorBorrowed<'_>,
) -> Result<LegacyGraphDiff, LegacyReportingError> {
    let mut result = LegacyGraphDiff::default();
    for (field, kind) in [
        ("entities", "entity"),
        ("mappings", "mapping"),
        ("authorities", "authority"),
    ] {
        let a = indexed(list(before, field)?)?;
        let b = indexed(list(after, field)?)?;
        let by_id: HashMap<_, _> = b.iter().copied().collect();
        let before_ids: HashSet<_> = a.iter().map(|(id, _)| *id).collect();
        for (id, left) in a {
            if let Some(right) = by_id.get(id) {
                if !equivalent(Some(left), Some(right), col)? {
                    result.counts.changed += 1;
                    result.changes.push(LegacyGraphChange {
                        change: "changed",
                        kind,
                        id: LegacyReportText::source(id),
                        changed_properties: Some(changed_properties(left, right, col)?),
                    });
                }
            } else {
                result.counts.removed += 1;
                result.changes.push(LegacyGraphChange {
                    change: "removed",
                    kind,
                    id: LegacyReportText::source(id),
                    changed_properties: None,
                });
            }
        }
        for (id, _) in b {
            if !before_ids.contains(id) {
                result.counts.added += 1;
                result.changes.push(LegacyGraphChange {
                    change: "added",
                    kind,
                    id: LegacyReportText::source(id),
                    changed_properties: None,
                });
            }
        }
    }
    result.changes.sort_by(|a, b| {
        a.kind
            .cmp(b.kind)
            .then_with(|| col.compare_legacy_utf16(&a.id.0, &b.id.0))
    });
    Ok(result)
}
struct Issue {
    severity: LegacyReportText,
    code: LegacyReportText,
    message: LegacyReportText,
    subject: Option<LegacyReportText>,
}
fn issues(items: &[J], correspondence: bool) -> Vec<Issue> {
    items
        .iter()
        .map(|v| {
            let subject = if correspondence {
                v.get("correspondenceId")
            } else {
                v.get("subjectId")
                    .filter(|v| !matches!(v, J::Null))
                    .or_else(|| v.get("path"))
            };
            Issue {
                severity: js_text(v.get("severity")),
                code: js_text(v.get("code")),
                message: js_text(v.get("message")),
                subject: subject
                    .filter(|v| !matches!(v, J::Null))
                    .map(|v| js_text(Some(v))),
            }
        })
        .collect()
}
fn issue_table(entries: &[Issue]) -> Vec<LegacyReportText> {
    if entries.is_empty() {
        return vec!["No issues.".into()];
    }
    if entries.len() <= 30 {
        let mut lines = vec![
            "| Severity | Code | Subject | Message |".into(),
            "| --- | --- | --- | --- |".into(),
        ];
        lines.extend(entries.iter().map(|v| {
            line!(
                "| ",
                &v.severity,
                " | ",
                v.code.escaped(),
                " | ",
                v.subject
                    .as_ref()
                    .map(LegacyReportText::escaped)
                    .unwrap_or_else(|| "".into()),
                " | ",
                v.message.escaped(),
                " |"
            )
        }));
        return lines;
    }
    struct Group<'a> {
        severity: &'a LegacyReportText,
        code: &'a LegacyReportText,
        count: usize,
        examples: Vec<LegacyReportText>,
    }
    let mut positions = HashMap::new();
    let mut groups: Vec<Group<'_>> = Vec::new();
    for entry in entries {
        // Preserve the original NUL-concatenated Map key, including collisions.
        let key = line!(&entry.severity, "\0", &entry.code);
        let slot = *positions.entry(key).or_insert_with(|| {
            let slot = groups.len();
            groups.push(Group {
                severity: &entry.severity,
                code: &entry.code,
                count: 0,
                examples: Vec::new(),
            });
            slot
        });
        let group = &mut groups[slot];
        group.count += 1;
        if group.examples.len() < 3 {
            group
                .examples
                .push(entry.subject.as_ref().unwrap_or(&entry.message).clone());
        }
    }
    let mut lines = vec![
        "| Severity | Code | Count | Examples |".into(),
        "| --- | --- | ---: | --- |".into(),
    ];
    lines.extend(groups.iter().map(|g| {
        line!(
            "| ",
            g.severity,
            " | ",
            g.code.escaped(),
            " | ",
            g.count,
            " | ",
            LegacyReportText::join(&g.examples, ", ").escaped(),
            " |"
        )
    }));
    lines
}
fn drift_report(input: &J) -> Result<LegacyReportText, LegacyReportingError> {
    let graph = input
        .get("graph")
        .ok_or_else(|| error("Missing report graph"))?;
    let adapters = list(input, "adapters")?;
    let drift = issues(list(input, "driftIssues")?, true);
    let mut adapter_issues = Vec::new();
    for adapter in adapters {
        adapter_issues.extend(issues(list(adapter, "diagnostics")?, false));
    }
    let validation = input
        .get("validation")
        .ok_or_else(|| error("Missing report validation"))?;
    let validation_issues = issues(list(validation, "issues")?, false);
    let all = drift
        .iter()
        .chain(&adapter_issues)
        .chain(&validation_issues);
    let (mut errors, mut warnings) = (0usize, 0usize);
    for issue in all {
        if issue.severity.equals("error") {
            errors += 1;
        }
        if issue.severity.equals("warning") {
            warnings += 1;
        }
    }
    let diff = input
        .get("diff")
        .ok_or_else(|| error("Missing report diff"))?;
    let counts = diff
        .get("counts")
        .ok_or_else(|| error("Missing report diff counts"))?;
    let changes = list(diff, "changes")?;
    let cache_hits = match input.get("cacheHits") {
        None | Some(J::Null) => 0,
        Some(J::Array(items)) => items.len(),
        _ => return Err(error("Read-only legacy cacheHits requires an array")),
    };
    let mut lines = vec![
        "# Metamap drift report".into(),
        "".into(),
        line!(
            "Status: **",
            if errors == 0 { "PASS" } else { "FAIL" },
            "** — ",
            errors,
            " error(s), ",
            warnings,
            " warning(s)."
        ),
        "".into(),
        "## Graph summary".into(),
        "".into(),
        line!("- Entities: ", list(graph, "entities")?.len()),
        line!("- Mappings: ", list(graph, "mappings")?.len()),
        line!(
            "- Authority declarations: ",
            list(graph, "authorities")?.len()
        ),
        line!("- Adapter shards: ", adapters.len()),
        line!("- Cache hits: ", cache_hits),
        "".into(),
        "## Baseline diff".into(),
        "".into(),
        line!("- Added: ", js_text(counts.get("added"))),
        line!("- Removed: ", js_text(counts.get("removed"))),
        line!("- Changed: ", js_text(counts.get("changed"))),
        "".into(),
    ];
    if !changes.is_empty() {
        lines.push("| Change | Kind | ID | Properties |".into());
        lines.push("| --- | --- | --- | --- |".into());
        for change in changes {
            lines.push(line!(
                "| ",
                js_text(change.get("change")),
                " | ",
                js_text(change.get("kind")),
                " | ",
                LegacyReportText::source(string(change, "id")?).escaped(),
                " | ",
                optional_join(change.get("changedProperties"))?.escaped(),
                " |"
            ));
        }
        lines.push("".into());
    }
    for (heading, entries) in [
        ("Correspondence drift", drift),
        ("Adapter diagnostics", adapter_issues),
        ("Graph validation", validation_issues),
    ] {
        lines.push(line!("## ", heading));
        lines.push("".into());
        lines.extend(issue_table(&entries));
        lines.push("".into());
    }
    Ok(LegacyReportText::join(&lines, "\n"))
}
fn documentation(
    graph: &J,
    correspondences: &[J],
    col: &CollatorBorrowed<'_>,
) -> Result<LegacyReportText, LegacyReportingError> {
    fn counts(
        items: &[J],
        field: &str,
        col: &CollatorBorrowed<'_>,
    ) -> Result<Vec<(LegacyReportText, usize)>, LegacyReportingError> {
        let mut slots = HashMap::new();
        let mut counts: Vec<(LegacyReportText, usize)> = Vec::new();
        for item in items {
            let key = LegacyReportText::source(string(item, field)?);
            let slot = *slots.entry(key.clone()).or_insert_with(|| {
                let slot = counts.len();
                counts.push((key, 0));
                slot
            });
            counts[slot].1 += 1;
        }
        counts.sort_by(|a, b| col.compare_legacy_utf16(&a.0.0, &b.0.0));
        Ok(counts)
    }
    let entities = list(graph, "entities")?;
    let mappings = list(graph, "mappings")?;
    let authorities = list(graph, "authorities")?;
    let mut lines = vec![
        line!("# ", nullish(graph.get("label"), "Structural map")),
        "".into(),
        "> Generated by Metamap. Edit source structures or `metamap.config.json`, then regenerate."
            .into(),
        "".into(),
        "## Summary".into(),
        "".into(),
        line!("- Graph: `", js_text(graph.get("id")), "`"),
        line!(
            "- Revision: `",
            nullish(graph.get("revision"), "unversioned"),
            "`"
        ),
        line!("- Entities: ", entities.len()),
        line!("- Mappings: ", mappings.len()),
        line!("- Authorities: ", authorities.len()),
        "".into(),
        "## Entity kinds".into(),
        "".into(),
        "| Kind | Count |".into(),
        "| --- | ---: |".into(),
    ];
    lines.extend(
        counts(entities, "kind", col)?
            .iter()
            .map(|(key, count)| line!("| ", key, " | ", *count, " |")),
    );
    lines.extend(
        [
            "",
            "## Relations",
            "",
            "| Relation | Count |",
            "| --- | ---: |",
        ]
        .map(Into::into),
    );
    lines.extend(
        counts(mappings, "relation", col)?
            .iter()
            .map(|(key, count)| line!("| ", key, " | ", *count, " |")),
    );
    lines.extend(["", "## Declared correspondences", ""].map(Into::into));
    if correspondences.is_empty() {
        lines.push("No declared correspondences.".into());
    } else {
        lines.extend(
            correspondences
                .iter()
                .map(|v| line!("- `", js_text(v.get("id")), "`")),
        );
    }
    lines.extend(["", "## Authority", ""].map(Into::into));
    if authorities.is_empty() {
        lines.push("No authority declarations.".into());
    } else {
        lines.extend(
            [
                "| Concept | Facts | Canonical source |",
                "| --- | --- | --- |",
            ]
            .map(Into::into),
        );
        for authority in authorities {
            lines.push(line!(
                "| ",
                js_text(authority.get("concept")),
                " | ",
                optional_join(authority.get("facts"))?,
                " | ",
                js_text(authority.get("source")),
                " |"
            ));
        }
    }
    lines.push("".into());
    Ok(LegacyReportText::join(&lines, "\n"))
}

fn stable_json_text(
    input: &str,
    pretty: bool,
    locale: &str,
) -> Result<LegacyReportText, LegacyReportingError> {
    let parsed = parse(input)?;
    // Bound indentation and enclosing JSON-string expansion before formatting.
    // Compact input bytes already bound keys, escapes and scalar values.
    let mut bound = input.len().checked_add(16).ok_or_else(output_limit)?;
    let mut stack = vec![(parsed.value(), 0usize)];
    while let Some((value, depth)) = stack.pop() {
        if pretty {
            bound = bound.checked_add(depth * 4 + 16).ok_or_else(output_limit)?;
        }
        if bound > (COMPATIBILITY_JSON_LIMITS.max_bytes - 2) / 2 {
            return Err(output_limit());
        }
        match value {
            J::Object(pairs) => stack.extend(pairs.iter().map(|(_, v)| (v, depth + 1))),
            J::Array(values) => stack.extend(values.iter().map(|v| (v, depth + 1))),
            _ => {}
        }
    }
    let col = collator(locale)?;
    let bytes = if pretty {
        Data::stable_pretty_bytes(parsed.value(), &col)
    } else {
        Data::stable_bytes(parsed.value(), &col)
    }
    .map_err(|e| error(e.to_string()))?;
    Ok(String::from_utf8(bytes)
        .expect("Original JSON is UTF-8")
        .into())
}
fn output_limit() -> LegacyReportingError {
    LegacyReportingError {
        code: "LEGACY_REPORTING_RESOURCE_LIMIT".into(),
        name: "Error".into(),
        message: "Original stable JSON exceeds native compatibility resource bounds".into(),
    }
}

pub fn legacy_reporting_request(
    request: LegacyReportingRequest,
) -> Result<LegacyReportingResponse, LegacyReportingError> {
    Ok(match request.action {
        LegacyReportingAction::StableJson { value, pretty } => {
            LegacyReportingResponse::Text(stable_json_text(&value, pretty, &request.locale)?)
        }
        LegacyReportingAction::ValueDigest { value } => {
            let parsed = parse(&value)?;
            let bytes = Data::stable_bytes(parsed.value(), &collator(&request.locale)?)
                .map_err(|e| error(e.to_string()))?;
            LegacyReportingResponse::Text(patamaps_contracts::byte_digest(&bytes).into())
        }

        LegacyReportingAction::EmptyDiff => {
            LegacyReportingResponse::Diff(LegacyGraphDiff::default())
        }
        LegacyReportingAction::Diff { before, after } => LegacyReportingResponse::Diff(diff(
            parse(&before)?.value(),
            parse(&after)?.value(),
            &collator(&request.locale)?,
        )?),
        LegacyReportingAction::DriftReport { input } => {
            LegacyReportingResponse::Text(drift_report(parse(&input)?.value())?)
        }
        LegacyReportingAction::GraphDocumentation {
            graph,
            correspondences,
        } => {
            let graph = parse(&graph)?;
            let correspondences = parse(&correspondences)?;
            let items = correspondences
                .value()
                .array()
                .ok_or_else(|| error("Read-only legacy correspondences requires an array"))?;
            LegacyReportingResponse::Text(documentation(
                graph.value(),
                items,
                &collator(&request.locale)?,
            )?)
        }
    })
}
