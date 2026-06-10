# QA and verification checklist

Quality is not optional here; the cost of a wrong move is the owner losing trust (and, if deletion ever gets involved, a real memory). Run these checks every time.

## Before moving anything (Phase 4)

- [ ] Render a contact sheet of the full archive candidate list, person-shots first. Open it and actually look.
- [ ] Confirm the "poor" set is genuinely poor: soft subject, blown/black, not an intentional night/fire scene, not a distinct moment with no better frame.
- [ ] Render keeper-vs-archived for people clusters. Confirm the green keeper is the best frame (eyes open, looking ready), not just the sharpest.
- [ ] Render the readiness demo on a sample of portrait shots. Confirm blink/look-away flags match what you see. If they are wrong, adjust EAR/gaze/yaw thresholds and re-plan.
- [ ] Spot-check that full-body-only detections (person, no face) are treated as people, not scenery.
- [ ] Check no whole session/day is being wiped. The plan's session-guarantee should keep at least the best 1-2 of each; verify the guarantee fired where needed.

## After moving (Phase 5)

- [ ] Integrity reconciliation: count originals before, kept after, archived after. `kept + archived (+ system junk) == original`. Print it. Investigate any mismatch before doing anything else.
- [ ] Confirm nothing the owner cares about is unreadable/lost. Only files that moved to Archive should leave the main folder. Originals are never deleted by this skill.
- [ ] Confirm `Archive/_archive_manifest.csv` exists and lists every archived file with a reason.
- [ ] Sanity-render a random sample (~80) of the kept main folder. Scan for any blurry/junk that slipped through; if found, the thresholds are too loose.

## Shortlist QA (Phase 6)

- [ ] Coverage: every day and key moment represented; print a per-day count.
- [ ] People quota met (roughly half the set) and personas/groupings varied.
- [ ] No near-duplicates within the shortlist (dHash diversity enforced).
- [ ] File sizes reasonable for the target channel (WhatsApp ~ a few hundred KB to ~1MB at long-edge 2048, quality ~88). Print avg/total.
- [ ] Names are date-ordered so they send/scroll in sequence; `_filelist.txt` maps each back to its original.
- [ ] Render the final shortlist as one preview montage and look at it end to end.

## Counts and reconciliation snippet

Use `os.listdir` (not `os.path.exists`) as truth. A correct reconciliation looks like:

```
originals (pre-cull, excluding shortlist copy folders) == kept_in_main + in_archive
```

If the owner has been editing in parallel, expect their manual deletions to reduce the original total; account for that explicitly rather than assuming your moves caused a delta.

## Final deliverable

- [ ] Write or update `_Cleanup_Summary.txt` in the folder: what was kept, what was archived and why, where the shortlist is, and a reminder that Archive is reversible and nothing was deleted.
- [ ] Present the summary, the manifest, and the kept-sample / shortlist preview to the owner. Keep the explanation short; let them look.
- [ ] Offer the learning loop: if they edit the result, run `learn_from_edits.py` and fold the findings back in.
