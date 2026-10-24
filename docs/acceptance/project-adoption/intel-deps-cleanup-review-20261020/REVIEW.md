# Intel compiler-output deletion proposal

Only the ordinary, singly linked files listed in inventory.jsonl are proposed. No deletion is authorized yet. Parent directories and excluded entries remain.

Source, Git history, acceptance receipts, source/native distribution archives, installed CLI copies, and all paths outside target/debug/deps remain. No byte-for-byte backup or restoration of these compiled outputs has been verified. Their loss requires recompilation when needed; that rebuild has not been exercised after deletion. Previous test records remain historical evidence, not proof that a future rebuild passes. APFS sharing means physical space gained may differ from summed allocation.

Before deletion, recheck no active reservations and every inventoried file identity/size/mtime/mode/link count. A changed inventory needs fresh approval.
