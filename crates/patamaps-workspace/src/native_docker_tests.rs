use super::*;

fn config(paths: Vec<String>) -> DockerConfig {
    DockerConfig {
        nonsecret_inputs: true,
        dockerfile: "deploy/Dockerfile".into(),
        context: ".".into(),
        context_files: paths,
        context_snapshot: None,
        complete_context_snapshot: true,
        target: "runtime".into(),
        platform: "linux/amd64".into(),
        frontend: "docker/dockerfile:1.10.0".into(),
        build_args: BTreeMap::new(),
    }
}
const DOCKER: &str = "# syntax=docker/dockerfile:1.10.0\nFROM scratch AS builder\nWORKDIR /build\nRUN do-not-execute-project-code\nFROM scratch AS runtime\nWORKDIR /app\nCOPY --from=0 /build/catalog-service /usr/local/bin/catalog-service\nCOPY [\"config/service.toml\", \"/app/service.toml\"]\nUSER 65532:65532\nEXPOSE 8080\nENTRYPOINT [\"/usr/local/bin/catalog-service\"]\nCMD [\"/app/service.toml\"]\n";

#[test]
fn pinned_ast_observes_launch_and_preserves_opaque_effects() {
    let inputs = BTreeMap::from([
        ("deploy/Dockerfile", DOCKER),
        ("config/service.toml", "[http]\nlisten='0.0.0.0:8080'\n"),
    ]);
    let cfg = config(inputs.keys().map(|p| p.to_string()).collect());
    let (entities, metadata) = observe("docker-tests", &inputs, &cfg).unwrap();
    assert_eq!(
        metadata["selectedStage"]["entrypoint"],
        json!(["/usr/local/bin/catalog-service"])
    );
    assert_eq!(
        metadata["selectedStage"]["cmd"],
        json!(["/app/service.toml"])
    );
    assert_eq!(metadata["imageContentsEstablished"], false);
    assert_eq!(metadata["instructionsExecuted"], false);
    let copy = entities
        .iter()
        .find(|v| v["attributes"]["observation"]["from"] == "0")
        .unwrap();
    assert_eq!(copy["attributes"]["observation"]["fromStageIndex"], 0);
    for entity in entities
        .iter()
        .filter(|v| v["kind"] == "docker-instruction")
    {
        let a = &entity["attributes"];
        let start = a["span"][0].as_u64().unwrap() as usize;
        let end = a["span"][1].as_u64().unwrap() as usize;
        assert_eq!(&DOCKER[start..end], a["lexeme"].as_str().unwrap());
    }
    assert!(metadata["unsupported"].as_array().unwrap().iter().any(|v| {
        v["reasons"]
            .as_array()
            .unwrap()
            .iter()
            .any(|r| r.as_str().unwrap().contains("RUN effects"))
    }));
}

#[test]
fn ignore_subset_is_ordered_and_unknown_patterns_refuse() {
    let rules = ignore_rules("**/target\n!service/target/keep\nacceptance/runs/\n").unwrap();
    assert!(ignored("service/target/stale", &rules));
    assert!(!ignored("service/target/keep", &rules));
    assert!(ignored("acceptance/runs/log", &rules));
    assert!(!ignored("other/acceptance/runs/log", &rules));
    for pattern in ["*.rs", "[ab]", "a/**/b", "../outside", "!"] {
        assert!(ignore_rules(pattern).is_err(), "{pattern}");
    }
}

#[test]
fn unresolved_expansions_and_nonliteral_paths_remain_unavailable() {
    let values = BTreeMap::from([("ROOT".into(), "/app".into())]);
    assert_eq!(expand("${ROOT}/service", &values).unwrap(), "/app/service");
    assert!(expand("${UNKNOWN}", &values).is_err());
    assert!(expand("${ROOT:-/fallback}", &values).is_err());
    assert!(absolute("../outside", Some("/app")).is_err());
    assert!(absolute("service", None).is_err());
}

#[test]
fn complete_context_and_selected_stage_are_required() {
    let inputs = BTreeMap::from([
        ("deploy/Dockerfile", DOCKER),
        ("config/service.toml", "listen='test'"),
    ]);
    let mut cfg = config(inputs.keys().map(|p| p.to_string()).collect());
    cfg.complete_context_snapshot = false;
    assert!(
        observe("test", &inputs, &cfg)
            .unwrap_err()
            .to_string()
            .contains("NATIVE_DOCKER_CONTEXT")
    );
    cfg.complete_context_snapshot = true;
    cfg.context_files.pop();
    assert!(observe("test", &inputs, &cfg).is_err());
    cfg.context_files = inputs.keys().map(|p| p.to_string()).collect();
    cfg.target = "missing".into();
    assert!(
        observe("test", &inputs, &cfg)
            .unwrap_err()
            .to_string()
            .contains("NATIVE_DOCKER_TARGET")
    );
}

#[test]
fn an_ordinary_late_comment_cannot_select_the_frontend() {
    let raw = DOCKER.replacen("# syntax=docker/dockerfile:1.10.0\n", "", 1)
        + "# syntax=docker/dockerfile:1.10.0\n";
    let inputs = BTreeMap::from([
        ("deploy/Dockerfile", raw.as_str()),
        ("config/service.toml", "listen='test'"),
    ]);
    let cfg = config(inputs.keys().map(|p| p.to_string()).collect());
    assert!(
        observe("test", &inputs, &cfg)
            .unwrap_err()
            .to_string()
            .contains("NATIVE_DOCKER_FRONTEND")
    );
}

#[test]
fn node_budget_refuses_without_returning_a_partial_inventory() {
    let raw = "# syntax=docker/dockerfile:1.10.0\nFROM scratch AS runtime\n".to_owned()
        + &"RUN opaque\n".repeat(5000);
    let inputs = BTreeMap::from([("deploy/Dockerfile", raw.as_str())]);
    let cfg = config(inputs.keys().map(|p| p.to_string()).collect());
    assert!(
        observe("test", &inputs, &cfg)
            .unwrap_err()
            .to_string()
            .contains("NATIVE_DOCKER_LIMIT")
    );
}
