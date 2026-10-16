#![cfg(unix)]
use patamaps_contracts::SafeInteger;
use patamaps_workspace::*;
use serde_json::json;
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicU64, Ordering},
};
static SEQUENCE: AtomicU64 = AtomicU64::new(0);
struct Temp(PathBuf);
impl Temp {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "patamaps-command-test-{}-{}",
            std::process::id(),
            SEQUENCE.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}
impl Drop for Temp {
    fn drop(&mut self) {
        eprintln!("Retained project-command fixture: {}", self.0.display());
    }
}
fn fixture() -> (Temp, ProjectCapture, ProjectCommand) {
    let root = Temp::new();
    fs::write(root.0.join("input.txt"), "selected original\n").unwrap();
    let definition: ProjectProfile = serde_json::from_value(json!({
        "profile":"patamaps-project-inputs-1", "id":"urn:test:project-command",
        "nonsecretInputs":true, "inputs":["input.txt"],
        "components":[{"id":"inputs","kind":"configuration","root":".","entrypoints":["input.txt"]}],
        "nonsecretConfiguration":{"mode":"declared"}, "secretReferences":{"unused":"PATAMAPS_SECRET_NOT_RESOLVED"}
    })).unwrap();
    let capture = capture_project(&root.0, definition).unwrap();
    let command = ProjectCommand {
        profile: PROJECT_COMMAND_PROFILE.into(),
        invocation: Invocation {
            executable: "/usr/bin/env".into(),
            arguments: vec![],
            code_inputs: vec![],
            bounds: ProcessBounds {
                maximum_elapsed_ms: SafeInteger::new(2000).unwrap(),
                maximum_stdout_bytes: SafeInteger::new(65536).unwrap(),
                maximum_stderr_bytes: SafeInteger::new(4096).unwrap(),
            },
        },
        working_directory: ".".into(),
        environment_references: std::collections::BTreeMap::from([("MODE".into(), "mode".into())]),
    };
    (root, capture, command)
}
#[test]
fn command_uses_only_captured_nonsecret_environment_and_keeps_sources() {
    let (root, capture, mut command) = fixture();
    // A longer command budget is explicit and does not require waiting for it.
    command.invocation.bounds.maximum_elapsed_ms = SafeInteger::new(60_001).unwrap();
    let result = execute_project_command(&root.0, &capture, &command).unwrap();
    assert_eq!(result["status"], "completed-project-command");
    assert_eq!(result["stdout"]["text"], "MODE=declared\n");
    assert_eq!(result["selectedInputsUnchanged"], true);
    assert_eq!(result["ambientEnvironment"], "not-inherited");
    assert_eq!(result["selectionPublication"], "not-performed");
    assert_eq!(
        fs::read_to_string(root.0.join("input.txt")).unwrap(),
        "selected original\n"
    );
}
#[test]
fn unsuccessful_command_retains_actual_exit_and_diagnostics() {
    let (root, capture, mut command) = fixture();
    command.invocation.executable = "/bin/sh".into();
    command.invocation.arguments = vec![
        "-c".into(),
        "printf out; printf diagnostic >&2; exit 9".into(),
    ];
    let result = execute_project_command(&root.0, &capture, &command).unwrap();
    assert_eq!(result["status"], "refused-project-command");
    assert_eq!(result["exitCode"], 9);
    assert_eq!(result["stdout"]["text"], "out");
    assert_eq!(result["stderr"]["text"], "diagnostic");
    assert_eq!(result["selectedInputsUnchanged"], true);
}
#[test]
fn command_input_changes_are_reported_without_rollback_or_selection() {
    let (root, capture, mut command) = fixture();
    command.invocation.executable = "/bin/sh".into();
    command.invocation.arguments = vec!["-c".into(), "printf changed > input.txt".into()];
    let result = execute_project_command(&root.0, &capture, &command).unwrap();
    assert_eq!(result["programSucceeded"], true);
    assert_eq!(result["status"], "refused-project-command");
    assert_eq!(result["selectedInputsUnchanged"], false);
    assert_eq!(
        fs::read_to_string(root.0.join("input.txt")).unwrap(),
        "changed"
    );
    assert_eq!(result["selectionPublication"], "not-performed");
}
#[test]
fn command_deadline_and_pipe_bounds_refuse() {
    let (root, capture, mut command) = fixture();
    command.invocation.executable = "/bin/sleep".into();
    command.invocation.arguments = vec!["5".into()];
    command.invocation.bounds.maximum_elapsed_ms = SafeInteger::new(100).unwrap();
    assert!(matches!(
        execute_project_command(&root.0, &capture, &command),
        Err(Error::Refused {
            code: "ADAPTER_TIMEOUT",
            ..
        })
    ));
    command.invocation.executable = "/bin/sh".into();
    command.invocation.arguments = vec!["-c".into(), "printf too-long".into()];
    command.invocation.bounds.maximum_elapsed_ms = SafeInteger::new(2000).unwrap();
    command.invocation.bounds.maximum_stdout_bytes = SafeInteger::new(3).unwrap();
    assert!(matches!(
        execute_project_command(&root.0, &capture, &command),
        Err(Error::Refused {
            code: "ADAPTER_OUTPUT_LIMIT",
            ..
        })
    ));
}
#[test]
fn command_refuses_unknown_environment_uncaptured_helpers_and_escaping_directory() {
    let (root, capture, mut command) = fixture();
    command
        .environment_references
        .insert("MODE".into(), "missing".into());
    assert!(matches!(
        execute_project_command(&root.0, &capture, &command),
        Err(Error::Refused {
            code: "PROJECT_COMMAND_ENVIRONMENT",
            ..
        })
    ));
    command.environment_references.clear();
    command.invocation.code_inputs = vec!["missing-helper".into()];
    assert!(matches!(
        execute_project_command(&root.0, &capture, &command),
        Err(Error::Refused {
            code: "PROJECT_COMMAND_CODE_INPUTS",
            ..
        })
    ));
    command.invocation.code_inputs.clear();
    command.working_directory = "../".into();
    assert!(matches!(
        execute_project_command(&root.0, &capture, &command),
        Err(Error::Refused {
            code: "PROJECT_COMMAND_DIRECTORY",
            ..
        })
    ));
    command.working_directory = ".".into();
    command.invocation.bounds.maximum_elapsed_ms = SafeInteger::new(86_400_001).unwrap();
    assert!(matches!(
        execute_project_command(&root.0, &capture, &command),
        Err(Error::Refused {
            code: "ADAPTER_LIMITS",
            ..
        })
    ));
}
