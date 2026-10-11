use crate::CheckError;
use patamaps_contracts::{ContractError, GraphDocument, canonical_digest};
use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RecordDelta {
    pub kind: &'static str,
    pub id: String,
    pub change: &'static str,
    pub before_digest: Option<String>,
    pub after_digest: Option<String>,
}

fn records<T: Serialize>(
    kind: &'static str,
    before: &[T],
    after: &[T],
    id: impl Fn(&T) -> &str,
    changes: &mut Vec<RecordDelta>,
) -> Result<(), CheckError> {
    let mut maps = [BTreeMap::new(), BTreeMap::new()];
    for (map, values) in maps.iter_mut().zip([before, after]) {
        for v in values {
            let digest = canonical_digest(v)?;
            if map.insert(id(v).to_owned(), digest).is_some() {
                return Err(CheckError(vec![crate::Issue::error(
                    "DUPLICATE_DIFF_ID",
                    "Diff input has duplicate identities",
                    id(v),
                )]));
            }
        }
    }
    let keys: std::collections::BTreeSet<_> = maps.iter().flat_map(|m| m.keys()).collect();
    for key in keys {
        let a = maps[0].get(key);
        let b = maps[1].get(key);
        if a != b {
            changes.push(RecordDelta {
                kind,
                id: key.clone(),
                change: if a.is_none() {
                    "added"
                } else if b.is_none() {
                    "removed"
                } else {
                    "modified"
                },
                before_digest: a.cloned(),
                after_digest: b.cloned(),
            });
        }
    }
    Ok(())
}

/// Exact authored record changes by stable ID, independent of declaration order.
/// This reports differences, not a claim that any input uniquely caused a failure.
pub fn diff(before: &GraphDocument, after: &GraphDocument) -> Result<Vec<RecordDelta>, CheckError> {
    let mut changes = Vec::new();
    records(
        "entity",
        &before.entities,
        &after.entities,
        |e| &e.id,
        &mut changes,
    )?;
    records(
        "mapping",
        &before.mappings,
        &after.mappings,
        |m| &m.id,
        &mut changes,
    )?;
    records(
        "authority",
        &before.authorities,
        &after.authorities,
        |a| &a.id,
        &mut changes,
    )?;
    let mut a = serde_json::to_value(before).map_err(ContractError::from)?;
    let mut b = serde_json::to_value(after).map_err(ContractError::from)?;
    for v in [&mut a, &mut b] {
        for key in ["entities", "mappings", "authorities"] {
            v.as_object_mut().expect("graph object").remove(key);
        }
    }
    let (a, b) = (canonical_digest(&a)?, canonical_digest(&b)?);
    if a != b {
        changes.push(RecordDelta {
            kind: "document",
            id: after.id.clone(),
            change: "modified",
            before_digest: Some(a),
            after_digest: Some(b),
        });
    }
    changes.sort_by(|a, b| (&a.kind, &a.id).cmp(&(&b.kind, &b.id)));
    Ok(changes)
}
