# Benchmark: photo-culling-curator

Harness: with-skill vs no-skill baseline on a labeled fixture of 26 real DSLR
photos (11 good keepers, 15 known-bad: 8 blurry, 3 over/under-exposed, 4
unready-person shots = blinks and look-aways). Task: plan-only keep/archive, no
files moved. Grading is objective against the labels.

| Config | Archived | Bad recall | Unready caught | Good wrongly archived | Precision |
|---|---|---|---|---|---|
| With skill v1 (balanced) | 4 | 4/15 (26%) | 0/4 | 0/11 | 100% |
| With skill v2 (improved) | 13 | 13/15 (86%) | 3/4 | 0/11 | 100% |
| Baseline (no skill) | 10 | 9/15 (60%) | 1/4 | 1/11 | 90% |

## What the harness found and fixed

v1 was too conservative: the blink/gaze/head-pose detector only chose burst
keepers, so isolated unready shots survived (0/4 caught) and overall recall was
26%. Two changes fixed it:

1. `unready_reason` now rejects a standalone person shot whose dominant prominent
   face is blinking or strongly turned away.
2. The "keep best of every session" guarantee now protects only real moments
   (3+ frames), so lone bad singletons are judged on quality.

v2 result: 86% of bad shots caught including 3 of 4 unready moments, at 100%
precision (it never archived a good photo). It beats the no-skill baseline on
recall, on unready detection, and on precision (the baseline mis-flagged a good
file as corrupt). The one missed unready shot was the better frame of a
look-away pair that dedup had already chosen as the pair's keeper.
