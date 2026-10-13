use crate::*;
use patamaps_contracts::canonical_bytes;

fn quote(value: &str) -> String {
    if value.contains(['\t', '\n', '\r', '"']) {
        format!("\"{}\"", value.replace('"', "\"\""))
    } else {
        value.into()
    }
}
pub fn export_tsv(checked: &CheckedSssom, condense: bool) -> Result<ExportedSssom> {
    let mut document = checked.document.clone();
    let before = &checked.interpretation;
    let mut condensed = Vec::new();
    if condense && !before.records.is_empty() {
        for (name, slot) in &interpret::slots().mapping_set {
            if !slot.propagated {
                continue;
            }
            let Some(common) = before.records[0]
                .fields
                .get(name)
                .filter(|v| interpret::has(v))
            else {
                continue;
            };
            if before
                .records
                .iter()
                .any(|r| r.fields.get(name) != Some(common))
            {
                continue;
            }
            if let Some(value) = document.metadata.get(name).filter(|v| interpret::has(v)) {
                let normalized = if slot.multivalued && !value.is_array() {
                    serde_json::Value::Array(vec![value.clone()])
                } else {
                    value.clone()
                };
                if normalized != *common {
                    continue;
                }
            }
            let Some(index) = document.columns.iter().position(|c| c == name) else {
                continue;
            };
            if document.rows.iter().all(|row| row[index].is_empty()) {
                continue;
            }
            document.metadata.insert(name.clone(), common.clone());
            document.columns.remove(index);
            for row in &mut document.rows {
                row.remove(index);
            }
            condensed.push(name.clone());
        }
    }
    // JSON flow syntax is YAML 1.2; quoting every metadata string avoids scalar
    // reinterpretation. Original YAML bytes remain separately captured evidence.
    let mut text = format!(
        "#{}\n",
        String::from_utf8(canonical_bytes(&document.metadata)?).expect("canonical UTF-8")
    );
    for row in std::iter::once(&document.columns).chain(&document.rows) {
        text.push_str(&row.iter().map(|v| quote(v)).collect::<Vec<_>>().join("\t"));
        text.push('\n');
    }
    let after = interpret::parse_tsv_with_limits(text.as_bytes(), None, checked.limits)?;
    let fields = |value: &Interpretation| -> Result<Vec<u8>> {
        Ok(canonical_bytes(
            &value.records.iter().map(|r| &r.fields).collect::<Vec<_>>(),
        )?)
    };
    let metadata = |value: &Interpretation| -> Result<Vec<u8>> {
        Ok(canonical_bytes(
            &value
                .metadata
                .iter()
                .filter(|(k, _)| !condensed.contains(k))
                .collect::<std::collections::BTreeMap<_, _>>(),
        )?)
    };
    if fields(before)? != fields(&after.interpretation)?
        || metadata(before)? != metadata(&after.interpretation)?
        || canonical_bytes(&before.prefixes)? != canonical_bytes(&after.interpretation.prefixes)?
        || canonical_bytes(&before.extensions)?
            != canonical_bytes(&after.interpretation.extensions)?
    {
        return refuse(
            "SSSOM_EXPORT_PRESERVATION",
            "Export changed effective fields, prefixes, extensions or retained set context",
        );
    }
    Ok(ExportedSssom { text, loss: ExportLoss { profile: EntityProfile::Entity1, semantic_fields_preserved: true, byte_identity_preserved: false, dropped_fields: Vec::new(), condensed_slots: condensed, normalization: vec!["YAML flow serialization, TSV quoting and line endings may change".into(), "Condensation changes field origins explicitly; original bytes retain their own receipt".into()] } })
}
