# Retained project input staging

Status: implemented with frozen filesystem controls; compilation/runtime pending. G4 workflow completion remains open.

Add native project-stage CAPTURE --destination NEW_DIRECTORY using the existing
ProjectCapture/verification contract. It reads only the verified record, never
original project paths, environment values or tools. The destination parent must
already exist. Refuse an existing destination (including symlinks), invalid or
tampered capture, and file/directory prefix collisions before creating anything.

Use the existing Unix descriptor-relative path discipline and rustix dependency:
create a fresh private directory, traverse intermediate directories with NOFOLLOW,
create regular files exclusively with non-executable user-only permissions, and
compare staged bytes to captured inputs. Recheck held and visible directory
identities before reporting success. The final parent component must not be a
symlink; ordinary operating-system ancestor aliases follow the same selected-root
policy as capture. This is not a malicious-host sandbox or filesystem transaction.
Refused partial attempts remain for review; never delete or overwrite them.

The receipt binds the capture digest, selected file receipts and recheck scope.
It explicitly establishes no complete build context, executable/metadata restore,
dependency installation, build, admission, selection publication or activation.
Secret references stay unresolved. Binary files, symlinks, dependencies and input
modes are outside the existing UTF-8 capture profile and are not reconstructed.
Windows remains unavailable consistently with native capture's current platform
boundary. Do not weaken earlier capture/verify behavior.

Acceptance: stage exact nested input bytes after original selected source paths
are unavailable; recapture the result and match the original capture digest;
refuse existing directory/file/symlink destinations and symlink parents without
changing their bytes; reject tampered capture and a validly hashed prefix collision
before creating a destination; exercise shared intermediate directories and
non-executable modes. Native CLI checks must repeat source-free staging with
empty PATH, and an attempted existing-target overwrite must fail. Real Wargame
preparation should stage its selected input capture before the explicitly recorded
candidate-only witness include. These are staging checks, not real app build or
Next qualification. Remaining G4 requirements (orchestration, readiness, race/
cancellation/watch/no-op/performance and installed consumers) are unchanged.
