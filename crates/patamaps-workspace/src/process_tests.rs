use crate::*;
use patamaps_contracts::{
    GraphDocument, ProtocolVersion, canonical_bytes, canonical_digest, parse,
};
use std::{
    fs,
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
    time::{Duration, Instant},
};
static SEQUENCE: AtomicU64 = AtomicU64::new(0);
struct Temp(PathBuf);
impl Temp {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "patamaps-process-test-{}-{}",
            std::process::id(),
            SEQUENCE.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}
impl Drop for Temp {
    fn drop(&mut self) {
        eprintln!("Retained process-test fixture: {}", self.0.display());
    }
}
fn setup() -> (Temp, AdapterRequest, AdapterResponse, Invocation) {
    let root = Temp::new();
    let mut request = AdapterRequest {
        schema_version: ProtocolVersion::Draft1,
        document_type: RequestType::Record,
        profile: PROFILE.into(),
        source_id: "urn:source:process".into(),
        namespace: "test".into(),
        config: Default::default(),
        inputs: Vec::new(),
        invocation_digest: "sha256:configured-executable".into(),
        request_digest: String::new(),
    };
    request.request_digest = canonical_digest(&request).unwrap();
    let graph: GraphDocument =
        parse(include_bytes!("../../../fixtures/routing/graph.json")).unwrap();
    let response = AdapterResponse {
        schema_version: ProtocolVersion::Draft1,
        document_type: ResponseType::Record,
        profile: PROFILE.into(),
        source_id: request.source_id.clone(),
        adapter_version: "test-1".into(),
        request_digest: request.request_digest.clone(),
        inputs: Vec::new(),
        shard: graph,
        diagnostics: Vec::new(),
    };
    let path = root.0.join("response.json");
    fs::write(&path, canonical_bytes(&response).unwrap()).unwrap();
    let invocation = Invocation {
        executable: "/bin/sh".into(),
        // A valid fixture provider consumes the supplied request before
        // responding. cat(file) alone can close stdin before the writer runs.
        arguments: vec![
            "-c".into(),
            "/bin/cat >/dev/null; /bin/cat \"$1\"".into(),
            "adapter-fixture".into(),
            path.to_str().unwrap().into(),
        ],
        code_inputs: Vec::new(),
        bounds: ProcessBounds {
            maximum_elapsed_ms: SafeInteger::new(1000).unwrap(),
            maximum_stdout_bytes: SafeInteger::new(65536).unwrap(),
            maximum_stderr_bytes: SafeInteger::new(4096).unwrap(),
        },
    };
    (root, request, response, invocation)
}
#[test]
fn exact_response_rejects_forged_request_duplicate_json_and_error_diagnostic() {
    let (root, request, mut response, invocation) = setup();
    assert_eq!(
        process::invoke(&invocation, Path::new("/bin/sh"), &root.0, &request)
            .unwrap()
            .request_digest,
        request.request_digest
    );
    response.request_digest = "sha256:wrong".into();
    fs::write(
        root.0.join("response.json"),
        canonical_bytes(&response).unwrap(),
    )
    .unwrap();
    let refused =
        process::invoke(&invocation, Path::new("/bin/sh"), &root.0, &request).unwrap_err();
    assert!(
        refused.to_string().contains("ADAPTER_BINDING"),
        "{refused:?}"
    );
    response.request_digest = request.request_digest.clone();
    response.diagnostics.push(AdapterDiagnostic {
        severity: DiagnosticSeverity::Error,
        code: "BAD_SOURCE".into(),
        message: "fixture refusal".into(),
    });
    fs::write(
        root.0.join("response.json"),
        canonical_bytes(&response).unwrap(),
    )
    .unwrap();
    assert!(
        process::invoke(&invocation, Path::new("/bin/sh"), &root.0, &request)
            .unwrap_err()
            .to_string()
            .contains("ADAPTER_DIAGNOSTIC")
    );
    let raw = String::from_utf8(canonical_bytes(&response).unwrap()).unwrap();
    fs::write(
        root.0.join("response.json"),
        format!("{{\"schemaVersion\":\"0.1.0\",{}", &raw[1..]),
    )
    .unwrap();
    assert!(matches!(
        process::invoke(&invocation, Path::new("/bin/sh"), &root.0, &request),
        Err(Error::Contract(_))
    ));
}
#[test]
fn exit_timeout_pipe_overflow_and_inherited_pipe_holders_are_bounded() {
    let (root, request, _, mut invocation) = setup();
    invocation.arguments.clear();
    assert!(
        process::invoke(&invocation, Path::new("/usr/bin/false"), &root.0, &request)
            .unwrap_err()
            .to_string()
            .contains("ADAPTER_EXIT")
    );
    invocation.bounds.maximum_elapsed_ms = SafeInteger::new(30).unwrap();
    invocation.arguments = vec!["10".into()];
    let start = Instant::now();
    assert!(
        process::invoke(&invocation, Path::new("/bin/sleep"), &root.0, &request)
            .unwrap_err()
            .to_string()
            .contains("ADAPTER_TIMEOUT")
    );
    assert!(start.elapsed() < Duration::from_secs(2));
    invocation.arguments.clear();
    // Isolate pipe overflow from the preceding deliberately tight deadline.
    invocation.bounds.maximum_elapsed_ms = SafeInteger::new(1000).unwrap();
    invocation.bounds.maximum_stdout_bytes = SafeInteger::new(32).unwrap();
    let overflow =
        process::invoke(&invocation, Path::new("/usr/bin/yes"), &root.0, &request).unwrap_err();
    assert!(
        overflow.to_string().contains("ADAPTER_OUTPUT_LIMIT"),
        "{overflow:?}"
    );
    invocation.bounds.maximum_elapsed_ms = SafeInteger::new(30).unwrap();
    invocation.arguments = vec!["-c".into(), "/bin/sleep 10 & exit 0".into()];
    let start = Instant::now();
    assert!(
        process::invoke(&invocation, Path::new("/bin/sh"), &root.0, &request)
            .unwrap_err()
            .to_string()
            .contains("ADAPTER_TIMEOUT")
    );
    assert!(start.elapsed() < Duration::from_secs(2));
}
