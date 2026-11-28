# Retained dynamic symbol profile: focused preflight passes

All112 existing controls passed on Intel, with0 failures/errors/skips and both
workflow YAML checks passing. Source hashes match the tested working overlay.
The actual512MiB native-exclusive reservation finished/released with guard and
supervisor0; the machine4GB ceiling,500MB reserve/100GB retention are unchanged.

Only the explicit retained-dynamic profile now requests Cargo dev/test
strip=symbols in both existing workspace gates and fresh compiler commands.
The receipt records those options. Legacy profiles, optimization/assertion/
overflow policy and every original runtime/refusal/resource gate remain.
[Cargo documents this option](https://doc.rust-lang.org/cargo/reference/profiles.html#strip);
no binary-size saving or behavioral equivalence has yet been observed.

The actual full source/native41-group/four-test pair still needs its selected
Linux CI run and independent artifact review. Do not infer a capacity pass from
unit controls. Earlier failed4GB runs remain failures.

A separate read-only context diagnostic used the wrong permission comparison:
private snapshot storage intentionally has different modes from source metadata.
Native load uses permissions=false and omits stored symlink entries. Its first
reported difference is not a demonstrated native fault. Raw result/source remain
private and the mistaken assumption is retained explicitly.
