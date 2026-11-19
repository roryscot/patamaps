# Miniserve refuses a stale deployment generation

The pinned Miniserve 0.35.0 source compiled for Linux x86-64 and passed
325 upstream tests. Patamaps selected the actual runtime and a deployment
declaration for loopback port 9100. The qualification then changed the
owner graph and nonsecret service declaration to port 9101 and ran
`project-build-input-key` without building that generation. The
observation executed no declared commands.

With the producer paths unavailable, `project-exec-selected` received
the 9101 input key and refused with exit 2 and
`PROJECT_BUILD_EXPECTED_INPUT_KEY_MISMATCH` before the runtime probe
created its output directory. The same selected Miniserve bundle passed
all eight HTTP and startup checks with its matching 9100 input key,
including exact GET content, HEAD length and wrong-listener refusal.
The selection pointer and post-execution artifact bindings matched.

The independent review on Norway matched the 20,216,193-byte GitHub
archive to its published SHA-256, inspected the actual native commands
and both outcomes, and rehashed the nested selected-state archive,
pointer, application and creating compiler. It reconstructed the
intended port declarations from the archived inputs and matched both
recorded digests. The archive was inspected in memory.
[Linux CI job](https://github.com/roryscot/patamaps/actions/runs/42173903644/job/127747838102)

This qualifies the key check for this real Rust service and explicit
deployment profile in Linux CI. The intended 9101 generation was
observed only. Managed Intel replay of this current engine, private
owner deployment qualification and production activation remain separate.
