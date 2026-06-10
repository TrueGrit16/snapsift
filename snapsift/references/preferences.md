# What owners actually want (learned from real corrections)

This is distilled from a real project where the owner reviewed the machine's output and corrected it by hand twice. Their deletions and restorations are the highest-quality signal you will get. Read this before your first cull on any new collection, and re-read it after the owner edits your output.

## The corrections that taught the most

Round 1: after a "strong" automated cull, the owner restored specific photos from Archive and was alarmed that beautiful frames had been archived. The archived frames were near-duplicates of a kept frame, removed on a tiny sharpness difference. Lesson: never pick the survivor of a near-identical pair on sharpness alone, and never aggressively dedup people moments.

Round 2: the owner manually deleted 163 of 624 kept photos and restored 28 from Archive. When the metrics were run on the 163 deletions, they were not blurrier (median sharpness was higher than the keepers), not more duplicate-like, and their eyes/smile rates matched the keepers. Conclusion: the existing features could not explain the owner's choices at all. The deciding factor was an unready subject (mid-blink, looking away, head turned, awkward pose). The 28 restorations were atmospheric and moment shots (mangrove river, sunsets, bonfire, a second good group frame) that had been over-culled.

## Concrete preferences

- **Subject readiness is the top criterion for people shots.** Eyes open, looking toward the camera (or naturally engaged), relaxed/ready pose, decent expression. A technically perfect frame of someone blinking or turned away is a reject.
- **"Blurry" means the subject, not the pixels.** Measure focus on the face/body. Owners call a soft-faced shot "blurry" even if the background is crisp and the global sharpness is high.
- **Keep multiple good frames of valued moments.** They will restore a second sunset, a second bonfire shot, another frame of the kids. Be gentle: keep 2-3 strong frames, drop only clearly worse repeats.
- **Protect atmosphere and night.** Sunsets, dusk, bonfire, fireworks, string lights, candlelit dinners read as dark to exposure metrics but are intentional and loved. Do not cull for darkness.
- **Protect distinct activities and locations.** A whole session (a trick-art museum, a boat trip, a beach walk) should be represented. Do not let a high-volume day starve a smaller, distinct one.
- **People variety matters.** Different people and groupings should appear, not ten frames of the same pose. (True identity grouping needs a face-recognition model; until then, spread across sessions and use dHash diversity.)
- **Shareable shortlists should be balanced and complete.** Cover every day and key moment, lead with people and hero scenery, resize for the target channel, and name files in date order so they send in sequence.

## Process the owner trusts

- Research-grounded methods over ad-hoc heuristics. They explicitly asked whether the algorithm was based on real photo-quality science. Cite the basis (see methodology.md).
- Modern vision over classic cascades for anything involving people.
- Visual verification (contact sheets) before any move, and a clear, reversible Archive with a manifest.
- Honesty about limits. When a metric cannot capture something (e.g. "unready pose" before the readiness detector existed), say so plainly and fix it, rather than over-claiming.
- Never delete originals. Archive only. The owner curates from there.

## How to keep learning

After each round of owner edits, run `scripts/learn_from_edits.py`. It diffs the current folder/Archive against your last plan to produce two sets: false-keeps (you kept, they deleted) and false-archives (you archived, they restored). Analyze both with the full metric set, look for what separates them, and adjust thresholds or add a signal. Save durable findings to memory so the next project starts smarter, not from zero.
