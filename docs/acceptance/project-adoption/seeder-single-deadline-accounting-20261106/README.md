# Same-limit Docker volume sampler

The [full Seeder run](../seeder-full-viewport-accounting-stop-20261105/README.md)
stopped after Docker timed out on both requests from the serial retry
sampler. On idle Norway, eight samples from that sampler completed in
0.797 to 0.923 seconds and all returned the 23 owned volumes. The idle
checks did not reproduce the live failure.

The staged candidate makes one fresh volume-only request. It keeps the
5.1-second inner and 5.5-second outer deadlines and charges the same
volume sizes through the existing accounting adapter. The inner deadline
covers headers, body and result selection together. No stale sample
substitution or installed guard change is included. Docker documents
that its disk-usage command traverses the objects it measures.
[Docker disk-usage reference](https://github.com/docker/cli/blob/master/docs/reference/commandline/system_df.md)

On Norway, the Unix-socket control sent a complete response after 4.2
seconds. The old split sampler made two requests and refused after
5.101 seconds. The candidate made one request and returned in 4.205
seconds. A response body trickled beyond the deadline was refused at
5.103 seconds. Invalid JSON, missing inventory and HTTP 503 all refused.
The first body test fixture completed inside its deadline and failed
the expected-timeout assertion. Its corrected fixture sent enough
bytes to exercise the deadline. These controls establish a failure
mode of the old budget split and do not prove the earlier live request
would have finished inside a single window.

Six candidate calls bracketed by two old-sampler calls returned
identical names and byte counts for all 23 labelled volumes. Candidate
calls took 0.990 to 1.011 seconds. The [review](probe-review.json)
records their source digests and timings. The tested sources are
included. The test expects the prior query at
`../guarded-job-volume-retry-20261105/query.py` relative to the test
directory. Its bytes are in the [prior sampler record](../seeder-bounded-accounting-retry-20261105/query.py).
The pinned Python 3.13.16 command used `-I -S -B test-query.py` in
that staging layout. Full browser qualification remains open.
