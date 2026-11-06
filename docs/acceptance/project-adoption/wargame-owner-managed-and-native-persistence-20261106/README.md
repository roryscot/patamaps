# Wargame managed browser and native persistence on Norway

The original `scripts/check-persistence.mjs --web` command ran all three
declared managed integrations through Wargame's candidate guard. They
passed with the retained production Next build, Rust API, PostgreSQL
18.6 and a synthetic loopback OIDC provider. The integrations covered
production proxy identity and retry behavior, authoring and review
permissions, and detached runtime replay with an isolated restored
database. Each integration recorded two browser cases.

The detached runtime executed from the retained archive. The original
fixture database was archived and both its owner and runtime connection
attempts were denied. The owner catalog and an independent streaming
check matched all 2,185 regular archive members, the manifest and the
archive digest. The streaming check was separate from the owner's
unchanged archive verifier.

The independent review rehashed 159 frozen inputs and all 2,820
retained Next tree entries. The prior route-cache directory was
restored, and 24 new runtime cache files were retained separately.
The native binary, Next build ID and generated-bundle pointer matched.
The guard exited 0 and released. The owned PostgreSQL cluster stopped,
its tool image detached and the unrelated database retained its start
identity.

A separate native command completed 116 of 117 declared persistence
cases. The first plan of the remaining boundary-reference test reached
tick 200 of 864 at 487.98 seconds. The agent stopped the attempt because
the chosen 1,000-second deadline was inadequate for the three plans.
The partial native results, reference progress and failed run remain
retained. The native reservation released and the owned cluster
stopped. Full native persistence remains open, as do broader owner
acceptance and production activation.
