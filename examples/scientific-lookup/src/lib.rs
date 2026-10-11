//! Port of the pinned scientific lookup consumer over checked static artifacts.
//! Generation supplies bindings.rs, graph.json and projection.json at build time.
mod bindings;
pub use bindings::SemanticId;
use serde_json::{Map, Value, json};
use std::collections::BTreeMap;

pub struct Lookup {
    entries: BTreeMap<String, Value>,
    assertions: BTreeMap<String, Value>,
    targets: Value,
}
impl Lookup {
    pub fn from_static() -> Result<Self, String> {
        let projection: Value =
            serde_json::from_str(include_str!("projection.json")).map_err(|e| e.to_string())?;
        let graph: Value =
            serde_json::from_str(include_str!("graph.json")).map_err(|e| e.to_string())?;
        let generated: Value =
            serde_json::from_str(bindings::PROJECTION_JSON).map_err(|e| e.to_string())?;
        if generated != projection {
            return Err("Generated binding projection differs from installed projection".into());
        }
        let mut targets = Map::new();
        for e in generated["entries"]
            .as_array()
            .ok_or("Missing generated binding entries")?
        {
            let id = e["subject"]["id"]
                .as_str()
                .ok_or("Missing generated binding ID")?;
            let slots = e["slots"]
                .as_array()
                .ok_or("Missing generated binding slots")?
                .iter()
                .map(|s| {
                    Ok((
                        s["name"]
                            .as_str()
                            .ok_or("Missing binding slot name")?
                            .to_owned(),
                        s["targets"].clone(),
                    ))
                })
                .collect::<Result<Map<String, Value>, String>>()?;
            targets.insert(id.into(), Value::Object(slots));
        }
        let targets = Value::Object(targets);
        let entries = projection["entries"]
            .as_array()
            .ok_or("Missing projection entries")?
            .iter()
            .map(|e| {
                Ok((
                    e["subject"]["id"]
                        .as_str()
                        .ok_or("Missing subject ID")?
                        .into(),
                    e.clone(),
                ))
            })
            .collect::<Result<_, String>>()?;
        let assertions = graph["mappings"]
            .as_array()
            .ok_or("Missing captured assertions")?
            .iter()
            .map(|m| {
                Ok((
                    m["id"].as_str().ok_or("Missing assertion ID")?.into(),
                    m.clone(),
                ))
            })
            .collect::<Result<_, String>>()?;
        Ok(Self {
            entries,
            assertions,
            targets,
        })
    }
    pub fn subjects(&self) -> impl Iterator<Item = SemanticId> + '_ {
        self.entries
            .keys()
            .map(|id| SemanticId::parse(id).expect("Generated static subject identity"))
    }
    pub fn lookup(&self, id: SemanticId) -> Result<Value, String> {
        let id = id.as_str();
        let e = self
            .entries
            .get(id)
            .ok_or_else(|| format!("Missing checked projection entry: {id}"))?;
        let mut slots = Map::new();
        for slot in e["slots"].as_array().ok_or("Missing checked slots")? {
            let name = slot["name"].as_str().ok_or("Missing slot name")?;
            let assertions = slot["mappings"]
                .as_array()
                .ok_or("Missing assertion IDs")?
                .iter()
                .map(|m| {
                    let mapping = m.as_str().ok_or("Invalid assertion identity")?;
                    self.assertions
                        .get(mapping)
                        .cloned()
                        .ok_or_else(|| format!("Missing captured assertion: {mapping}"))
                })
                .collect::<Result<Vec<_>, String>>()?;
            slots.insert(name.into(),json!({"relation":slot["relation"],"direction":slot["direction"],"targets":self.targets[id][name],"assertions":assertions}));
        }
        Ok(json!({"subject":e["subject"],"slots":slots}))
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn native_static_lookup_preserves_all_assertions_and_duplicate_pair() {
        let lookup = Lookup::from_static().unwrap();
        let mut ids = std::collections::BTreeSet::new();
        let mut duplicate = false;
        for id in lookup.subjects() {
            let value = lookup.lookup(id).unwrap();
            assert_eq!(value["slots"].as_object().unwrap().len(), 5);
            for s in value["slots"].as_object().unwrap().values() {
                let assertions = s["assertions"].as_array().unwrap();
                for a in assertions {
                    ids.insert(a["id"].as_str().unwrap().to_owned());
                }
                if assertions.len() == 2 {
                    assert_eq!(assertions[0]["sources"], assertions[1]["sources"]);
                    assert_eq!(assertions[0]["targets"], assertions[1]["targets"]);
                    assert_ne!(assertions[0]["id"], assertions[1]["id"]);
                    assert_ne!(assertions[0]["attributes"], assertions[1]["attributes"]);
                    duplicate = true;
                }
            }
        }
        assert_eq!(ids.len(), 7);
        assert!(duplicate);
        assert!(SemanticId::parse("urn:unknown:operation").is_none());
    }
}
