# Explicit native project commands

The project-exec CAPTURE COMMAND --root RETAINED_ROOT CLI runs one owner-declared command and prints its report to stdout. The typed command profile is patamaps-project-command-1: invocation, workingDirectory and environmentReferences. The invocation selects an absolute executable, literal argv, captured codeInputs and explicit process bounds. Environment names refer only to string values already captured in the project's nonsecretConfiguration. Secret references and ambient environment are never resolved.

Selected input capture must verify and match the supplied root before execution. The root and selected working directory must be ordinary directories; relative escapes and directory symlinks refuse. The executable target is resolved and hashed, execution preserves the configured path/argv[0] (including rustup-style aliases), then the target is resolved/hashed again; selected project inputs are recaptured afterward. A normal nonzero exit, changed executable or changed selected input yields a refusal report. Normal completion retains bounded stdout/stderr, exact exit code or signal, digests and elapsed milliseconds. Binary diagnostics use hex when UTF-8 is unavailable. Changes are preserved without rollback.

The existing private self-exec supervisor and direct process executor are reused. Adapter invocations keep their60-second ceiling. Explicit project commands allow up to24hours, at most1MiB stdout and64KiB stderr; the private framed result has a separate bounded envelope. A distinct private wire version makes old helpers refuse project commands before execution. CLI calls configure parent-death cleanup; unconfigured library embedders report that guarantee as unestablished.

Programs are trusted, with no filesystem/network sandbox or complete dynamic dependency closure. Required application/storage guards still apply; process supervision is not a replacement for them. This primitive does not stage a complete build context, establish readiness, select outputs, publish a candidate, implement no-op/watch behavior or activate anything. Timeout/output-bound aborts retain the caller's failure diagnostic, but complete partial program pipe retention is not established. Those G4 obligations remain open.

Acceptance requires full workspace regressions, unchanged adapter deadline refusals, and supervised CLI controls for nonsecret environment isolation, nonzero/binary diagnostics, executable-alias dispatch, input/tool mutation, cwd/helper/environment refusals, timeout/output limits and ordinary descendant cleanup after SIGKILL of the CLI. Native Intel verification passed the full workspace suite,13 supervised CLI controls and focused all-target Clippy. Shared executor regression also passed49 discovery and93 HTTP transport controls before the isolated alias refinement. The [scoped receipt](../acceptance/project-adoption/g4-native-project-command-20261016/receipt.json) records exact file hashes and phases. Linux CI is pending after push.

For a capture whose definition includes nonsecretConfiguration.mode = "declared", this command prints only MODE=declared. Save it as a command JSON file and pass that file with the capture to project-exec. The root must contain the unchanged captured selected inputs.

```json
{
  "profile": "patamaps-project-command-1",
  "workingDirectory": ".",
  "environmentReferences": {
    "MODE": "mode"
  },
  "invocation": {
    "executable": "/usr/bin/env",
    "arguments": [],
    "codeInputs": [],
    "bounds": {
      "maximumElapsedMs": 60000,
      "maximumStdoutBytes": 65536,
      "maximumStderrBytes": 4096
    }
  }
}
```
