use patamaps_contracts::*;
use patamaps_workspace::WorkspaceConfig;
use serde_json::json;
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};
static SEQUENCE: AtomicU64 = AtomicU64::new(0);
pub struct Fixture {
    pub root: PathBuf,
    pub config: WorkspaceConfig,
}
impl Drop for Fixture {
    fn drop(&mut self) {
        eprintln!(
            "Retained source-evaluation fixture: {}",
            self.root.display()
        );
    }
}
pub fn fixture() -> Fixture {
    let root = std::env::temp_dir().join(format!(
        "patamaps-source-evaluation-{}-{}",
        std::process::id(),
        SEQUENCE.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir(&root).unwrap();
    let mut graph: GraphDocument = parse(include_bytes!(
        "../../package-inputs/fixtures/routing/graph.json"
    ))
    .unwrap();
    graph
        .entities
        .iter_mut()
        .find(|e| e.kind == "routing:handler")
        .unwrap()
        .locators
        .as_mut()
        .unwrap()
        .push(Locator {
            uri: "rust:crate::service::greet".into(),
            media_type: None,
            revision: None,
            digest: None,
        });
    let mut empty = graph.clone();
    empty.id = "urn:source:empty".into();
    empty.entities.clear();
    empty.mappings.clear();
    empty.authorities.clear();
    fs::write(root.join("one.json"), canonical_bytes(&graph).unwrap()).unwrap();
    fs::write(root.join("two.json"), canonical_bytes(&empty).unwrap()).unwrap();
    fs::write(
        root.join("pack.json"),
        include_bytes!("../../package-inputs/relation-packs/routing.json"),
    )
    .unwrap();
    fs::write(
        root.join("projection.json"),
        include_bytes!("../../package-inputs/fixtures/routing/projection-spec.json"),
    )
    .unwrap();
    let mut policy: PolicyDocument = parse(include_bytes!(
        "../../package-inputs/fixtures/routing/policy.json"
    ))
    .unwrap();
    policy.graph.id = "urn:source-evaluation:test".into();
    policy.graph.revision = Some("1".into());
    policy.graph.digest = None;
    fs::write(root.join("policy.json"), canonical_bytes(&policy).unwrap()).unwrap();
    let config:WorkspaceConfig=parse(&canonical_bytes(&json!({"schemaVersion":"0.1.0","documentType":"workspace-config","id":policy.graph.id,"namespace":"source-test","revision":"1","sources":[{"adapter":"portable-shard","id":"urn:source:one","path":"one.json"},{"adapter":"portable-shard","id":"urn:source:two","path":"two.json"}],"packs":["pack.json"],"policy":"policy.json","projections":[{"path":"projection.json","emissions":[{"path":"bindings.rs","language":"rust","bindingSlot":"handler"}]}],"context":{"environment":"production"},"evaluatedAt":"2026-10-10T12:00:00Z"})).unwrap()).unwrap();
    Fixture { root, config }
}
