# Interrupted Next build cache review

The [exact inventory](inventory.json) contains six singly linked regular Webpack pack files from the failed Intel build: 1074593792 allocated bytes (summed allocation; actual free space may differ). SHA-256 and file identities were checked after the owned workload stopped.

These cache bytes have no verified backup, and exact restoration has not been exercised. Recompilation may produce replacement caches. Removing them loses those original cache instances.

All directories, source/snapshot bytes, non-cache build outputs/manifests, tools/archives, receipts/logs/recovery evidence, original application/dependencies and every unlisted path remain. No deletion has been performed. User approval for this exact list and fresh activity/identity checks are required before removal.
