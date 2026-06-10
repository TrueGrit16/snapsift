---
name: snapsift
description: Intelligently cull, clean, organize and curate large photo and video collections using research-grounded quality scoring and modern computer vision. Use this whenever the user wants to clean up a photo folder, remove duplicates or blurry or poorly-timed shots, find the best photos, build a shareable shortlist (for WhatsApp, Instagram, a gallery, or printing), organize a shoot or trip dump, pick the keeper from a burst, or judge people shots for eyes-open, smiles, gaze and natural pose. Trigger even when the user only says things like "my Photos folder is a mess", "pick the best ones from this trip", "get rid of the bad ones", "too many similar shots", "make me a highlights set", or points at a folder of camera files (DSLR, GoPro, phone). Always move rejects to an Archive folder and never delete originals.
---

# Photo Culling and Curation

A complete, careful pipeline for turning a large, messy photo/video dump into a clean, high-quality keeper set plus a curated shareable shortlist. It combines research-grounded image-quality scoring (NIMA-style aesthetics, no-reference technical quality) with modern computer vision (MediaPipe full-body pose, face detection, and per-face blink/gaze/head-pose "readiness") so the keeper of each moment is chosen the way a human would: sharp subject, eyes open, looking ready, good expression.

This skill exists because the obvious approach (global sharpness + perceptual-hash dedup) is wrong in ways that quietly destroy good photos. The lessons baked in here were learned the hard way. Read `references/preferences.md` and `references/methodology.md` before tuning anything.

## The five principles that matter most

1. **Judge the subject, not the whole frame.** A pin-sharp background hides a soft face. Global Laplacian variance rated photos the owner deleted as "sharper" than the ones they kept. Always measure focus on the face/person crop, and treat an out-of-focus face as a reject even when the scene is crisp.

2. **Detect the unready moment.** The single biggest miss is "bad or unready position of person": mid-blink, looking away, head turned, talking mid-sentence, awkward mid-stride. None of this shows up in exposure or color. You must look at eyes (Eye Aspect Ratio), gaze (iris position relative to eye corners), and head pose (yaw). In a group, check every prominent face, not just the largest.

3. **Dedup gently on moments people care about.** "Keep exactly one per group" is too aggressive. Owners often want two or three good frames of a valued moment (a sunset, a bonfire, a group laughing, kids playing). Cluster near-duplicates, keep the best 1-3 by an expression-aware score, and only drop clearly inferior repeats. Be more aggressive only on redundant scenery.

4. **Never delete. Always Archive, reversibly, with a manifest.** Move rejects into an `Archive/` folder that mirrors the original layout, and write `Archive/_archive_manifest.csv` listing every file and why. The owner reviews Archive and pulls things back. Treat their restorations and deletions as ground truth and learn from them.

5. **Verify visually before you move anything, and reconcile counts after.** Render contact sheets of what would be archived (especially anything with a person) and look at them. After moving, prove that kept + archived equals the original count so nothing was lost.

## Workflow

Run the phases in order. Every heavy script is **resumable and time-budgeted** because the sandbox kills long calls and background processes (see `references/sandbox_notes.md`). Re-run a phase's command until it prints `ALL DONE`; it skips finished files.

**Phase 0 - Clarify and inventory.** Confirm scope with the owner (how aggressive, what the shortlist is for, keep folders or flat). Then:
`python scripts/inventory.py <FOLDER>` — counts, file types, EXIF capture timeline, video durations/resolutions via ffprobe, and a per-day/session map. Writes `work/inventory.json`.

**Phase 1 - Technical + aesthetic metrics.** `python scripts/quality_metrics.py <FOLDER> <SECONDS>` — for every image: Laplacian + Tenengrad sharpness, exposure (well-exposedness, highlight/shadow clipping, mean), contrast, colourfulness, saturation, spectral-residual saliency composition (rule-of-thirds), and a dHash for dedup. Writes `work/quality.jsonl`.

**Phase 2 - Modern vision (the differentiator).** `python scripts/modern_vision.py <FOLDER> <SECONDS>` — MediaPipe full-body pose (finds people the face detectors miss), BlazeFace faces, and per-largest-face mesh metrics: face-region sharpness, eyes-open, smile, frontality, plus the readiness signals (blink/gaze/head-pose) from `scripts/lib/readiness.py`. Writes `work/vision.jsonl`. Requires `mediapipe==0.10.14` (see sandbox notes for why that exact version).

**Phase 3 - Cluster, score, plan.** `python scripts/build_cull_plan.py <FOLDER> --level <strong|balanced|light>` — clusters near-duplicates (dHash + capture-time), picks the best 1-3 keepers per cluster with the expression-aware score, flags genuinely poor standalones, protects person shots, and guarantees every session keeps its best frame. Writes `work/cull_plan.json` (keep / archive / reasons) but **moves nothing**.

**Phase 4 - Verify (mandatory).** `python scripts/contact_sheet.py <FOLDER> --set archive` and `--set people_dups` and `--set readiness` — renders montages of what is about to be archived (person shots first), the keeper-vs-archived people clusters, and a readiness demo. Read them. If a real keeper is flagged, adjust thresholds and re-plan. Do not skip this.

**Phase 5 - Apply.** `python scripts/apply_archive.py <FOLDER>` — moves planned rejects into `Archive/` mirroring structure, appends to the manifest, and prints an integrity reconciliation (kept + archived == original). Reversible.

**Phase 6 - Shortlist.** `python scripts/shortlist_export.py <FOLDER> --count <N> --out <NAME>` — curates the top N keepers, balanced across days and sessions with a people quota, deduped, exports resized copies (long edge 2048, ~quality 88) into a new folder with date-ordered names and a `_filelist.txt`. Originals are untouched (copies only).

**Phase 7 - Final QA.** Follow `references/qa_checklist.md`: reconcile counts, confirm no readable original was lost, sanity-render a random sample of the kept set, and write/update `_Cleanup_Summary.txt` in the folder.

**Phase 8 - Learn.** If the owner later deletes from the kept set or restores from Archive, run `python scripts/learn_from_edits.py <FOLDER>` to diff their actions against the last plan and surface what the metrics missed. Fold the findings back into thresholds and into memory.

## Calibration and levels

Thresholds are defaults, not laws. `references/methodology.md` lists every formula and starting value (EAR ~0.15 for closed eyes, head-yaw ~0.12 normalized for "turned away", iris-gaze ~0.55 for "looking away", blur floors, exposure bands). Cull levels: `light` removes only obvious junk and exact repeats; `balanced` removes clear duplicates and genuinely poor frames; `strong` keeps only the best of each group but still protects people via the readiness checks. Ask the owner which they want; default to `balanced` unless they say "very clean".

## Reference files (read when relevant)

- `references/methodology.md` — the science, every metric and formula, thresholds, the composite score, and citations (NIMA, BRISQUE/NIQE, EAR, MediaPipe iris/head-pose). Read before changing scoring.
- `references/preferences.md` — what owners actually want, distilled from real corrections. Read before your first cull on a new collection.
- `references/sandbox_notes.md` — Cowork/Linux-sandbox gotchas: resumable batching, the filesystem tombstone trap (trust listdir, not os.path.exists), overwrite-vs-create, the delete-permission tool, install pitfalls, no GPU. Read before running anything.
- `references/qa_checklist.md` — the verification and final-QA steps. Read before Phase 4 and Phase 7.

## Hard-won don'ts

- Don't choose a keeper between near-identical people frames on a sharpness tiebreak. Use eyes/gaze/smile. The difference a human cares about (who blinked) is invisible to pixel sharpness.
- Don't archive a dark frame just for being dark. Night, sunset, bonfire and fireworks are intentional. Protect them.
- Don't treat full-body-only detections as scenery. Pose without a face is still a person shot.
- Don't trust `os.path.exists` on the mounted folder; deleted files report stale True. Use `os.listdir`.
- Don't reuse a filename the owner deleted; it is tombstoned and creation fails. Use a fresh name or folder.
- Don't move first and look later. Render, look, then move.

## Eval-validated behavior (don't regress these)

This skill was benchmarked with a with-skill vs no-skill harness on a labeled
fixture (11 good, 15 bad incl. 4 unready-person shots). Two findings shaped the
current logic:

- The readiness detector must REJECT standalone unready person shots, not only
  pick burst keepers. `scoring.unready_reason` archives a shot whose dominant
  prominent face is blinking (eyes closed) or strongly turned away. Before this,
  isolated blink/look-away shots survived and recall was poor (26%). After, recall
  rose to ~86% with 100% precision (no good photo wrongly archived).
- The session guarantee only protects MOMENTS (sessions of 3+ frames). A lone
  blurry or unready singleton is not force-kept; it stands on its quality. Without
  this, scattered singletons re-protected everything and neutered the cull.

Result on the fixture: with-skill caught 13/15 bad incl. 3/4 unready at 100%
precision, beating a careful no-skill baseline (9/15 bad, 1/4 unready, and it even
mis-flagged a good file). Keep these two behaviors when refactoring.
