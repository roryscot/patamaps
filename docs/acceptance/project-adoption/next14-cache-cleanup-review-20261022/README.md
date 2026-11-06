# Interrupted Next build cache review

The [exact inventory](inventory.json) contains six singly linked regular Webpack pack files from the failed Intel build: 1074593792 allocated bytes (summed allocation; actual free space may differ). SHA-256 and file identities were checked after the owned workload stopped.

These cache bytes have no verified backup, and exact restoration has not been exercised. Recompilation may produce replacement caches. Removing them loses those original cache instances.

All directories, source/snapshot bytes, non-cache build outputs/manifests, tools/archives, receipts/logs/recovery evidence, original application/dependencies and every unlisted path remain. At proposal time no deletion had been performed. The owner subsequently approved only this exact six-file list. The [deletion result](deletion-result.json) records all six removals after fresh activity, SHA-256 and file-identity checks, with every directory and unlisted file preserved.
