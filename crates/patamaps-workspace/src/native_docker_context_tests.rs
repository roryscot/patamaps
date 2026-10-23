use super::*;
use crate::{AdapterRequest, ContextSymlinks, ProjectContextDefinition};
use patamaps_contracts::{canonical_bytes, canonical_digest, parse};
use std::{
    fs,
    os::unix::fs::{PermissionsExt, symlink},
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};

static SEQUENCE: AtomicU64 = AtomicU64::new(0);
const DOCKER: &str = "# syntax=docker/dockerfile:1.10.0\nFROM scratch AS runtime\nWORKDIR /app\nCOPY assets/ /app/\nRUN touch forbidden.marker\nENTRYPOINT [\"/app/runtime\"]\n";

struct Fixture {
    root: PathBuf,
    owner: PathBuf,
    snapshot: PathBuf,
    config: Value,
    texts: BTreeMap<String, String>,
}
impl Fixture {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "patamaps-docker-context-{}-{}",
            std::process::id(),
            SEQUENCE.fetch_add(1, Ordering::Relaxed)
        ));
        let owner = root.join("owner");
        fs::create_dir_all(owner.join("assets")).unwrap();
        let texts = BTreeMap::from([
            ("Dockerfile".into(), DOCKER.into()),
            (".dockerignore".into(), "assets/ignored\n".into()),
        ]);
        for (path, content) in &texts {
            fs::write(owner.join(path), content).unwrap();
        }
        fs::write(owner.join("assets/runtime"), [0, 255, 128, 1, 0]).unwrap();
        fs::set_permissions(
            owner.join("assets/runtime"),
            fs::Permissions::from_mode(0o755),
        )
        .unwrap();
        fs::write(owner.join("assets/ignored"), [255, 0]).unwrap();
        fs::write(owner.join("assets/document.txt"), "public\n").unwrap();
        let paths = vec![
            "Dockerfile",
            ".dockerignore",
            "assets/runtime",
            "assets/ignored",
            "assets/document.txt",
        ]
        .into_iter()
        .map(str::to_owned)
        .collect::<Vec<_>>();
        let definition = ProjectContextDefinition {
            profile: crate::CONTEXT_PROFILE.into(),
            id: "urn:test:docker-opaque".into(),
            nonsecret_inputs: true,
            paths: paths.clone(),
            symlinks: ContextSymlinks::Refuse,
        };
        let snapshot = root.join("snapshot");
        let captured = crate::capture_project_context(&owner, &snapshot, &definition).unwrap();
        let config = json!({"provider":"dockerfile","nonsecretInputs":true,"dockerfile":"Dockerfile","context":".","contextFiles":paths,"completeContextSnapshot":true,"target":"runtime","platform":"linux/amd64","frontend":"docker/dockerfile:1.10.0","buildArgs":{},"contextSnapshot":{"snapshot":snapshot,"digest":captured["digest"]}});
        Self {
            root,
            owner,
            snapshot,
            config,
            texts,
        }
    }
    fn discover(
        &self,
        config: Value,
        texts: &BTreeMap<String, String>,
    ) -> Result<Value, crate::Error> {
        let mut request:AdapterRequest = serde_json::from_value(json!({
            "schemaVersion":"0.1.0","documentType":"adapter-request","profile":crate::PROFILE,
            "sourceId":"urn:test:binary-docker","namespace":"binary-docker-tests","config":config,
            "inputs":texts.iter().map(|(path,content)|json!({"receipt":{"path":path,"digest":byte_digest(content.as_bytes()),"byteLength":content.len()},"content":content})).collect::<Vec<_>>(),
            "invocationDigest":format!("sha256:{}","0".repeat(64)),"requestDigest":""
        })).unwrap();
        request.request_digest = canonical_digest(&request).unwrap();
        let wire: AdapterRequest = parse(&canonical_bytes(&request).unwrap()).unwrap();
        let response = crate::discover_native(&wire, Path::new("/unavailable-original-owner"))?;
        Ok(serde_json::from_slice(&canonical_bytes(&response)?).unwrap())
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        eprintln!("Retained Docker context fixture: {}", self.root.display());
    }
}
fn observation(value: &Value) -> &Value {
    &value["shard"]["metadata"]["observation"]
}

#[test]
fn canonical_binary_context_copy_and_ignore_replay_without_owner_or_execution() {
    let f = Fixture::new();
    fs::rename(&f.owner, f.root.join("owner.retained-offline")).unwrap();
    let response = f.discover(f.config.clone(), &f.texts).unwrap();
    let value = observation(&response);
    assert_eq!(
        value["contextSnapshot"]["snapshotBytesAndModesVerified"],
        true
    );
    assert_eq!(value["contextSnapshot"]["fileCount"], 5);
    assert_eq!(value["instructionsExecuted"], false);
    assert_eq!(value["imageContentsEstablished"], false);
    let members = response["shard"]["entities"]
        .as_array()
        .unwrap()
        .iter()
        .find(|e| e["attributes"]["instruction"] == "copy_instruction")
        .unwrap()["attributes"]["observation"]["contextMembers"]
        .as_array()
        .unwrap();
    assert_eq!(members.len(), 2);
    let runtime = members
        .iter()
        .find(|m| m["source"] == "assets/runtime")
        .unwrap();
    assert_eq!(runtime["digest"], byte_digest(&[0, 255, 128, 1, 0]));
    assert_eq!(runtime["byteLength"], 5);
    assert_eq!(runtime["contentSuppliedAsText"], false);
    assert_eq!(
        runtime["contextSnapshotDigest"],
        f.config["contextSnapshot"]["digest"]
    );
    assert_eq!(runtime["destination"], "/app/runtime");
    assert!(!f.root.join("forbidden.marker").exists());
    let staged = f.root.join("staged");
    crate::stage_project_context(&f.snapshot, &staged).unwrap();
    assert_eq!(
        fs::read(staged.join("assets/runtime")).unwrap(),
        [0, 255, 128, 1, 0]
    );
    assert_eq!(f.discover(f.config.clone(), &f.texts).unwrap(), response);
}

#[test]
fn changed_text_and_omitted_ignore_content_refuse_even_with_valid_request_digests() {
    let f = Fixture::new();
    let mut changed = f.texts.clone();
    changed
        .get_mut("Dockerfile")
        .unwrap()
        .push_str("# different\n");
    assert!(
        f.discover(f.config.clone(), &changed)
            .unwrap_err()
            .to_string()
            .contains("NATIVE_DOCKER_CONTEXT_TEXT")
    );
    changed = f.texts.clone();
    changed.remove(".dockerignore");
    assert!(
        f.discover(f.config.clone(), &changed)
            .unwrap_err()
            .to_string()
            .contains("NATIVE_DOCKER_CONTEXT_TEXT")
    );
}

#[test]
fn changed_binary_modes_and_extra_members_refuse() {
    for case in ["bytes", "mode", "extra", "symlink"] {
        let f = Fixture::new();
        let runtime = f.snapshot.join("data/assets/runtime");
        match case {
            "bytes" => {
                fs::rename(&runtime, f.root.join("runtime.retained")).unwrap();
                fs::write(&runtime, [7, 8, 9]).unwrap();
            }
            "mode" => fs::set_permissions(&runtime, fs::Permissions::from_mode(0o644)).unwrap(),
            "extra" => fs::write(f.snapshot.join("data/unselected"), "extra").unwrap(),
            _ => {
                fs::rename(&runtime, f.root.join("runtime.retained")).unwrap();
                symlink(f.owner.join("assets/runtime"), &runtime).unwrap();
            }
        }
        assert!(f.discover(f.config.clone(), &f.texts).is_err(), "{case}");
    }
}

#[test]
fn complete_file_inventory_and_snapshot_digest_are_required() {
    let f = Fixture::new();
    for case in ["missing", "extra", "duplicate", "digest"] {
        let mut config = f.config.clone();
        match case {
            "missing" => {
                config["contextFiles"].as_array_mut().unwrap().pop();
            }
            "extra" => config["contextFiles"]
                .as_array_mut()
                .unwrap()
                .push(json!("absent")),
            "duplicate" => config["contextFiles"]
                .as_array_mut()
                .unwrap()
                .push(json!("Dockerfile")),
            _ => config["contextSnapshot"]["digest"] = json!(format!("sha256:{}", "0".repeat(64))),
        }
        assert!(f.discover(config, &f.texts).is_err(), "{case}");
    }
}

#[test]
fn snapshot_reference_privacy_paths_unknown_keys_and_root_links_refuse() {
    let f = Fixture::new();
    for case in [
        "relative",
        "unknown",
        "root-link",
        "nonsecret",
        "selection-nonsecret",
    ] {
        let mut config = f.config.clone();
        match case {
            "relative" => config["contextSnapshot"]["snapshot"] = json!("snapshot"),
            "unknown" => config["contextSnapshot"]["unreviewed"] = json!(true),
            "root-link" => {
                let alias = f.root.join("alias");
                symlink(&f.snapshot, &alias).unwrap();
                config["contextSnapshot"]["snapshot"] = json!(alias);
            }
            "nonsecret" => {
                config["nonsecretInputs"] = json!(false);
                config["contextSnapshot"]["snapshot"] = json!("/not-to-be-opened");
            }
            _ => {
                let selection = f.snapshot.join("selection.json");
                let mut value: Value =
                    serde_json::from_slice(&fs::read(&selection).unwrap()).unwrap();
                value["nonsecretInputs"] = json!(false);
                fs::write(selection, canonical_bytes(&value).unwrap()).unwrap();
            }
        }
        assert!(f.discover(config, &f.texts).is_err(), "{case}");
    }
    for path in [".env", "nested/.env.private", "id_rsa", ".npmrc"] {
        let blocked = f.owner.join(path);
        fs::create_dir_all(blocked.parent().unwrap()).unwrap();
        fs::write(&blocked, "explicit blocked-path test label").unwrap();
        let destination = f.root.join(format!("blocked-{}", path.replace('/', "-")));
        let definition = ProjectContextDefinition {
            profile: crate::CONTEXT_PROFILE.into(),
            id: "blocked".into(),
            nonsecret_inputs: true,
            paths: vec![path.into()],
            symlinks: ContextSymlinks::Refuse,
        };
        assert!(
            crate::capture_project_context(&f.owner, &destination, &definition).is_err(),
            "{path}"
        );
    }
}

#[test]
fn legacy_text_request_still_has_no_snapshot_lineage() {
    let f = Fixture::new();
    let mut config = f.config.clone();
    config.as_object_mut().unwrap().remove("contextSnapshot");
    config["contextFiles"] = json!(f.texts.keys().collect::<Vec<_>>());
    let response = f.discover(config, &f.texts).unwrap();
    assert!(observation(&response).get("contextSnapshot").is_none());
    assert_eq!(
        observation(&response)["contextCompleteness"],
        "caller-declared complete captured snapshot; live filesystem not rediscovered"
    );
}
