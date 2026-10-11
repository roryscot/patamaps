# Bounded native compiler measurements

The [raw receipt](phase-benchmark.json) records seven trials, the release binary
and driver hashes, compiler identity, Rust toolchain, host, commands, source
lock files, artifact sizes and registry dependency footprint. The
[input archive](phase-inputs.tar.gz) retains every measured graph, policy,
complete SDK case and optional provider request with a closed hash/size
inventory. Seed: `20261010`. The driver calls the public Rust SDK; it contains
no competing evaluator. The compiler identity remains `07f74356f72d…`.

All predeclared controls passed. Viable routing graphs contain 1,000 or 10,000
mappings; corresponding missing-endpoint graphs reject. Both 100,000-mapping
graphs exceed the 16 MiB ingress limit and refuse before semantic evaluation.
Their timings measure bounded refusal, not successful graph capacity. A
64-level delegation chain resolves to its declared leaf. Eight checked chain
proofs branch over nine base mappings; the overlapping consumer closure costs
17 unique mappings, with no repeated-premise charge. Original topology controls
and the original route-page removal retain their different decisions. The
bounded repair search completes without applying a proposal.

Fresh CLI processes separately measure `--version`, `engine` and complete
compile calls. Filesystem caches are uncontrolled. The SDK driver reads and
decodes each case before seven sequential in-process trials, initializes the
executor identity separately, and records strict decode, canonical hashing,
graph checking, admission, authority queries, one projection, 32 distinct
projection specifications, JSON/Rust/TypeScript emission, capture, replay and
bounded repair where those operations apply. The batch varies projection IDs
while retaining each case's selection and slots. Graph/packs cloning precedes
the graph-check timer; aggregate capture includes input cloning, admission and
serialization. These times overlap and cannot be summed into an end-to-end
estimate. Rejected stages have no invented projection time or artifact size.

An explicit TypeScript-Zod provider is timed separately, including Node startup,
temporary captured-source staging and discovery. It does not include Bindloom
admission, establish a complete provider dependency closure, or use process
caching. Compiler and SDK measurements run with Node absent from `PATH`.

Per-process memory comes from `os.wait4` for the exact child, avoiding a
cumulative child-process maximum. Python documents that this call returns the
waited child's resource usage. [Python process API](https://docs.python.org/3.14/library/os.html#os.wait4).
On this Darwin host, peak RSS is interpreted as bytes: Apple's kernel assigns
`resident_size_max` to `ru_maxrss`, and its Mach header defines that field in
bytes. The local SDK header agrees. An independently executed 64 MiB allocation
and page-touch control verifies the unit scale; its raw results remain in the
receipt. [Apple kernel accounting](https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/kern/kern_resource.c),
[Apple task-info definition](https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/osfmk/mach/task_info.h).
Whole-driver peak RSS includes fixture setup and all seven trials, including
allocator retention; it is not per-phase live memory or a deployment limit.

| Observed workload                                   | Median wall time | Peak RSS scope                                     |
| --------------------------------------------------- | ---------------- | -------------------------------------------------- |
| Fresh CLI, 1,000 valid mappings                     | 18.99 ms         | Median process peak: 12.42 MiB                     |
| Fresh CLI, 10,000 valid mappings                    | 137.42 ms        | Median process peak: 75.58 MiB                     |
| Warm SDK, 10,000 graph check                        | 92.19 ms         | Entire seven-trial SDK process: 459.97 MiB         |
| Warm SDK, 10,000 admission                          | 7.33 ms          | Same entire process; no phase-specific attribution |
| Warm SDK, 32 projections of 10,000 selected entries | 4,851.29 ms      | Same entire process                                |
| Warm SDK, branching proof admission                 | 4.97 ms          | Entire SDK process: 9.56 MiB                       |
| Warm SDK, bounded repair                            | 5.57 ms          | Entire SDK process: 7.89 MiB                       |
| Optional Zod discovery process                      | 248.94 ms        | Median process peak: 136.56 MiB                    |

The release CLI is 14,790,416 bytes and depends on the recorded system
libraries. Cargo metadata inventories 136 registry packages across this
workspace's resolved build/test/target graph: 92,307,045 unpacked source bytes
and 15,882,547 cached archive bytes. These are logical build-cache sizes, not
the runtime installation footprint; the registry inventory includes
dependencies that a particular platform or consumer may not compile. The
receipt retains all individual package licenses and sizes. Rust, Node, OS
libraries and build-object caches are described separately rather than charged
to the standalone compiler binary.

No performance optimization was introduced with this measurement work, and no
TypeScript timing baseline was measured. Seven observations do not establish
tail latency, a Rust speed or memory advantage, Linux performance or broader
capacity. The large SDK-process peak is retained as a useful baseline for future
allocation work; it cannot be compared with a single cold CLI process as though
the workloads were equivalent. Earlier development/release routing measurements
remain historical evidence, not matched performance comparisons.
