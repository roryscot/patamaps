# Seeder build with volume-only Docker accounting

The pinned volume-only API request and the prior Docker query returned the same 11 owned volumes and the same 501,651,966 bytes in live comparisons. The candidate changed only the request path. It used the existing guard, deadlines, accounting rules, and storage ceiling.

The first 1.8 GB reservation passed admission. Its launch driver still used the previous attempt's retained-state path, so it refused before compilation and released the reservation. The second attempt checked a fresh path before launch. It completed both generators and began the original Next.js command. Docker's volume usage query then timed out. A second timeout in the final capacity read aborted the guard's finalization before it wrote its terminal receipt or released the reservation.

Three stopped-state observations and rehashes of 7,446 prior artifacts, 943 source inputs and 146 frozen inputs supported releasing only this reservation. The archived owner record matches the original. The incomplete attempt and both generators' receipts remain on Norway. Neither run selected a frontend, and the browser tests did not run.

Before another build, address the accounting failure under load and provide retention headroom. The terminal capacity read must preserve failure evidence and proceed to the existing ownership decision if accounting is unavailable. This record does not qualify any change to the installed guard.
