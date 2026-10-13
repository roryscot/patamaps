//! Legacy graph queries over retained host handles. This is an observation
//! view, not a checked graph, authority grant, or admitted generation.
use crate::{LegacyValidationRegistry, validate_legacy_document};
use patamaps_contracts::{Relation, SafeInteger};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet, VecDeque};

#[derive(Debug, Default, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LegacyGraphRegistry {
    #[serde(default)]
    packs: Vec<PackVersion>,
    #[serde(default)]
    definitions: Vec<Definition>,
}
#[derive(Debug, Deserialize)]
struct PackVersion {
    key: String,
    version: Option<String>,
}
#[derive(Debug, Deserialize)]
struct Definition {
    key: String,
    value: Relation,
}
impl LegacyValidationRegistry for LegacyGraphRegistry {
    fn legacy_has_pack(&self, id: &str, version: Option<&str>) -> bool {
        self.packs.iter().find(|p| p.key == id).is_some_and(|p| {
            version
                .filter(|v| !v.is_empty())
                .is_none_or(|v| p.version.as_deref() == Some(v))
        })
    }
    fn legacy_definition(&self, id: &str) -> Option<&Relation> {
        self.definitions
            .iter()
            .find(|d| d.key == id)
            .map(|d| &d.value)
    }
    fn legacy_definitions(&self) -> Vec<&Relation> {
        self.definitions.iter().map(|d| &d.value).collect()
    }
}

#[derive(Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LegacyGraphIndex {
    #[serde(default)]
    entities: Vec<(String, SafeInteger)>,
    #[serde(default)]
    mappings: Vec<(String, SafeInteger)>,
    #[serde(default)]
    incident: Vec<Bucket>,
    #[serde(default)]
    concepts: Vec<Bucket>,
    #[serde(default)]
    delegations: Vec<Bucket>,
}
#[derive(Debug, Deserialize, Serialize)]
struct Bucket {
    key: String,
    handles: Vec<SafeInteger>,
}
#[derive(Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LegacyGraphObjects {
    #[serde(default)]
    entities: Vec<Value>,
    #[serde(default)]
    mappings: Vec<Value>,
    #[serde(default)]
    authorities: Vec<Value>,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LegacyGraphOperation {
    Build,
    GetEntity,
    GetMapping,
    MappingsFor,
    Neighbors,
    Trace,
    ResolveAuthority,
}
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct LegacyGraphRequest {
    operation: LegacyGraphOperation,
    registry: LegacyGraphRegistry,
    #[serde(default)]
    document: Value,
    #[serde(default)]
    index: LegacyGraphIndex,
    #[serde(default)]
    objects: LegacyGraphObjects,
    #[serde(default)]
    id: String,
    #[serde(default)]
    fact: String,
    #[serde(default)]
    options: Value,
    /// Transport fact for a JavaScript numeric value that JSON cannot encode.
    #[serde(default)]
    non_finite_max_depth: bool,
    #[serde(default)]
    allow_invalid: bool,
}
#[derive(Debug, thiserror::Error, Serialize)]
#[error("{message}")]
pub struct LegacyGraphError {
    pub code: String,
    pub name: String,
    pub message: String,
}
fn failure(name: &str, message: impl Into<String>) -> LegacyGraphError {
    LegacyGraphError {
        code: "LEGACY_GRAPH_INPUT".into(),
        name: name.into(),
        message: message.into(),
    }
}
fn scalar<'a>(value: &'a Value, key: &str) -> Result<&'a str, LegacyGraphError> {
    value.get(key).and_then(Value::as_str).ok_or_else(|| {
        failure(
            "TypeError",
            format!("Legacy graph snapshot requires a string {key}"),
        )
    })
}
fn list<'a>(value: &'a Value, key: &str) -> Result<&'a [Value], LegacyGraphError> {
    value
        .get(key)
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .ok_or_else(|| failure("TypeError", format!("document.{key} is not iterable")))
}
fn handle(index: usize) -> SafeInteger {
    SafeInteger::new(index as u64).expect("bounded input index")
}
fn position(index: SafeInteger) -> Result<usize, LegacyGraphError> {
    usize::try_from(index.get())
        .map_err(|_| failure("Error", "Legacy graph handle exceeds this platform"))
}
fn object(objects: &[Value], index: SafeInteger) -> Result<&Value, LegacyGraphError> {
    objects.get(position(index)?).ok_or_else(|| {
        failure(
            "Error",
            "Legacy graph handle is outside its retained snapshot",
        )
    })
}
fn lookup(keys: &[(String, SafeInteger)], key: &str) -> Option<SafeInteger> {
    keys.iter().find(|(id, _)| id == key).map(|(_, i)| *i)
}
fn insert(keys: &mut Vec<(String, SafeInteger)>, key: &str, index: SafeInteger) {
    if let Some((_, existing)) = keys.iter_mut().find(|(id, _)| id == key) {
        *existing = index;
    } else {
        keys.push((key.into(), index));
    }
}
fn bucket<'a>(buckets: &'a [Bucket], key: &str) -> &'a [SafeInteger] {
    buckets
        .iter()
        .find(|b| b.key == key)
        .map(|b| b.handles.as_slice())
        .unwrap_or(&[])
}
fn append(buckets: &mut Vec<Bucket>, key: &str, index: SafeInteger) {
    if let Some(b) = buckets.iter_mut().find(|b| b.key == key) {
        b.handles.push(index);
    } else {
        buckets.push(Bucket {
            key: key.into(),
            handles: vec![index],
        });
    }
}
fn build_index(document: &Value) -> Result<LegacyGraphIndex, LegacyGraphError> {
    let mut index = LegacyGraphIndex::default();
    for (i, entity) in list(document, "entities")?.iter().enumerate() {
        insert(&mut index.entities, scalar(entity, "id")?, handle(i));
    }
    for (i, mapping) in list(document, "mappings")?.iter().enumerate() {
        let h = handle(i);
        insert(&mut index.mappings, scalar(mapping, "id")?, h);
        let mut seen = HashSet::new();
        for endpoint in list(mapping, "sources")?
            .iter()
            .chain(list(mapping, "targets")?)
        {
            let endpoint = endpoint
                .as_str()
                .ok_or_else(|| failure("TypeError", "Legacy mapping endpoint must be a string"))?;
            if seen.insert(endpoint) {
                append(&mut index.incident, endpoint, h);
            }
        }
    }
    for (i, authority) in list(document, "authorities")?.iter().enumerate() {
        let h = handle(i);
        append(&mut index.concepts, scalar(authority, "concept")?, h);
        if authority["mode"] == "delegated" {
            append(
                &mut index.delegations,
                scalar(authority, "delegatedFrom")?,
                h,
            );
        }
    }
    Ok(index)
}

struct Query<'a> {
    index: &'a LegacyGraphIndex,
    objects: &'a LegacyGraphObjects,
    registry: &'a LegacyGraphRegistry,
}
impl Query<'_> {
    fn symmetric(&self, mapping: &Value) -> bool {
        mapping["relation"]
            .as_str()
            .and_then(|id| self.registry.legacy_definition(id))
            .is_some_and(|d| d.symmetric == Some(true))
    }
    fn mappings_for(
        &self,
        id: &str,
        options: &Value,
    ) -> Result<Vec<SafeInteger>, LegacyGraphError> {
        let direction = options["direction"].as_str().unwrap_or("both");
        let filter = options.get("relations").filter(|v| !v.is_null());
        let mut results = Vec::new();
        for &h in bucket(&self.index.incident, id) {
            let mapping = object(&self.objects.mappings, h)?;
            if filter.is_some_and(|filter| {
                !filter
                    .as_array()
                    .is_some_and(|ids| ids.contains(&mapping["relation"]))
            }) {
                continue;
            }
            if direction == "both"
                || self.symmetric(mapping)
                || list(
                    mapping,
                    if direction == "outgoing" {
                        "sources"
                    } else {
                        "targets"
                    },
                )?
                .iter()
                .any(|v| v == id)
            {
                results.push(h);
            }
        }
        Ok(results)
    }
    fn neighbors(
        &self,
        id: &str,
        options: &Value,
    ) -> Result<Vec<(SafeInteger, SafeInteger)>, LegacyGraphError> {
        let direction = options["direction"].as_str().unwrap_or("both");
        let mut results = Vec::new();
        let mut slots = HashMap::new();
        for h in self.mappings_for(id, options)? {
            let mapping = object(&self.objects.mappings, h)?;
            let sources = list(mapping, "sources")?;
            let targets = list(mapping, "targets")?;
            let symmetric = self.symmetric(mapping);
            let mut linked = Vec::new();
            let mut seen = HashSet::new();
            for (from, to, enabled) in [
                (sources, targets, direction != "incoming" || symmetric),
                (targets, sources, direction != "outgoing" || symmetric),
            ] {
                if enabled && from.iter().any(|v| v == id) {
                    for target in to {
                        let target = target.as_str().ok_or_else(|| {
                            failure("TypeError", "Legacy mapping endpoint must be a string")
                        })?;
                        if target != id && seen.insert(target) {
                            linked.push(target);
                        }
                    }
                }
            }
            for linked in linked {
                if let Some(entity) = lookup(&self.index.entities, linked) {
                    // Replacing a Map entry keeps its original insertion slot.
                    let key = format!("{}\0{linked}", scalar(mapping, "id")?);
                    if let Some(&slot) = slots.get(&key) {
                        results[slot] = (entity, h);
                    } else {
                        slots.insert(key, results.len());
                        results.push((entity, h));
                    }
                }
            }
        }
        Ok(results)
    }
    fn trace(
        &self,
        id: &str,
        options: &Value,
        non_finite_depth: bool,
    ) -> Result<Value, LegacyGraphError> {
        let Some(start) = lookup(&self.index.entities, id) else {
            return Ok(json!([]));
        };
        let depth = (!non_finite_depth)
            .then(|| {
                options
                    .get("maxDepth")
                    .filter(|v| !v.is_null())
                    .map(|v| v.as_f64())
                    .unwrap_or(Some(1.0))
            })
            .flatten();
        let Some(max_depth) = depth.filter(|v| v.is_finite() && *v >= 0.0 && v.fract() == 0.0)
        else {
            return Err(failure("Error", "maxDepth must be a non-negative integer"));
        };
        let mut visits = vec![json!({"entity":start,"depth":0})];
        let mut visited = HashSet::from([id.to_owned()]);
        let mut queue = VecDeque::from([(id.to_owned(), 0usize)]);
        while let Some((current, depth)) = queue.pop_front() {
            if depth as f64 >= max_depth {
                continue;
            }
            for (entity, mapping) in self.neighbors(&current, options)? {
                let entity_id = scalar(object(&self.objects.entities, entity)?, "id")?;
                if visited.insert(entity_id.to_owned()) {
                    visits.push(json!({"entity":entity,"depth":depth+1,"viaMapping":mapping,"predecessor":current}));
                    queue.push_back((entity_id.to_owned(), depth + 1));
                }
            }
        }
        Ok(json!(visits))
    }
    fn authority(&self, concept: &str, fact: &str) -> Result<Value, LegacyGraphError> {
        let applies = |h: SafeInteger| -> Result<bool, LegacyGraphError> {
            Ok(list(object(&self.objects.authorities, h)?, "facts")?
                .iter()
                .any(|v| v == "*" || v == fact))
        };
        let mut canonical = Vec::new();
        let mut delegated = Vec::new();
        let mut candidates = Vec::new();
        for &h in bucket(&self.index.concepts, concept) {
            if applies(h)? {
                match object(&self.objects.authorities, h)?["mode"].as_str() {
                    Some("canonical") => canonical.push(h),
                    Some("delegated") => delegated.push(h),
                    Some("candidate") => candidates.push(h),
                    _ => {}
                }
            }
        }
        if let [root] = canonical.as_slice() {
            let mut chain = vec![*root];
            let mut current = *root;
            let mut visited = HashSet::new();
            visited.insert(scalar(object(&self.objects.authorities, current)?, "id")?.to_owned());
            loop {
                let id = scalar(object(&self.objects.authorities, current)?, "id")?;
                let children = bucket(&self.index.delegations, id)
                    .iter()
                    .copied()
                    .map(|h| applies(h).map(|yes| (h, yes)))
                    .collect::<Result<Vec<_>, _>>()?
                    .into_iter()
                    .filter_map(|(h, yes)| yes.then_some(h))
                    .collect::<Vec<_>>();
                if children.is_empty() {
                    return Ok(
                        json!({"status":"resolved","canonical":root,"effective":current,"delegationChain":chain,"candidates":candidates}),
                    );
                }
                let next_id = scalar(object(&self.objects.authorities, children[0])?, "id")?;
                if children.len() > 1 || !visited.insert(next_id.to_owned()) {
                    break;
                }
                current = children[0];
                chain.push(current);
            }
        }
        if !canonical.is_empty() || !delegated.is_empty() || !candidates.is_empty() {
            canonical.extend(delegated);
            canonical.extend(candidates);
            Ok(json!({"status":"ambiguous","candidates":canonical}))
        } else {
            Ok(json!({"status":"unresolved","candidates":[]}))
        }
    }
}

pub fn legacy_graph_request(request: LegacyGraphRequest) -> Result<Value, LegacyGraphError> {
    if matches!(request.operation, LegacyGraphOperation::Build) {
        let validation = validate_legacy_document(&request.document, &request.registry);
        if !validation.valid && !request.allow_invalid {
            return Ok(json!({"validation":validation,"index":null}));
        }
        return Ok(json!({"validation":validation,"index":build_index(&request.document)?}));
    }
    let query = Query {
        index: &request.index,
        objects: &request.objects,
        registry: &request.registry,
    };
    match request.operation {
        LegacyGraphOperation::GetEntity => Ok(json!(lookup(&request.index.entities, &request.id))),
        LegacyGraphOperation::GetMapping => Ok(json!(lookup(&request.index.mappings, &request.id))),
        LegacyGraphOperation::MappingsFor => {
            Ok(json!(query.mappings_for(&request.id, &request.options)?))
        }
        LegacyGraphOperation::Neighbors => Ok(json!(
            query
                .neighbors(&request.id, &request.options)?
                .into_iter()
                .map(|(entity, mapping)| json!({"entity":entity,"mapping":mapping}))
                .collect::<Vec<_>>()
        )),
        LegacyGraphOperation::Trace => {
            query.trace(&request.id, &request.options, request.non_finite_max_depth)
        }
        LegacyGraphOperation::ResolveAuthority => query.authority(&request.id, &request.fact),
        LegacyGraphOperation::Build => unreachable!(),
    }
}
