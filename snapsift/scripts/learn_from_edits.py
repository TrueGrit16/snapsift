#!/usr/bin/env python3
"""
Phase 8: learn from the owner's manual edits. Diffs the CURRENT folder/Archive
against the last cull plan to find:
  - false_keep : you kept it, the owner deleted it (your misses)
  - restored   : you archived it, the owner moved it back (your over-culls)
Then summarizes what (if anything) in the metrics separates these from the rest,
so you can re-tune thresholds and update memory.

IMPORTANT: uses os.listdir as truth, NOT os.path.exists (the mount lies; deleted
files report stale exists=True). See references/sandbox_notes.md.

Usage: python scripts/learn_from_edits.py <FOLDER>
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from lib import common, scoring

def listset(folder):
    s = set(common.list_images(folder))
    return s

def archset(folder):
    return set(common.archive_image_rels(folder))

def main(folder):
    wd = common.work_dir(folder)
    plan = json.load(open(os.path.join(wd, 'cull_plan.json')))
    Q = common.load_jsonl_map(os.path.join(wd, 'quality.jsonl'))
    V = common.load_jsonl_map(os.path.join(wd, 'vision.jsonl'))
    prev_keep = set(plan['keep'])
    main_now = listset(folder); arch_now = archset(folder)
    false_keep = sorted([r for r in prev_keep if r not in main_now and r not in arch_now])
    restored = sorted([r for r in main_now if r not in prev_keep])
    json.dump({'false_keep': false_keep, 'restored': restored},
              open(os.path.join(wd, 'edits_diff.json'), 'w'))

    def summarize(name, rels):
        rels = [r for r in rels if r in Q]
        print(f'\n=== {name} (n={len(rels)}) ===')
        if not rels:
            return
        ppl = [r for r in rels if scoring.person(V.get(r, {}))]
        lap = np.array([Q[r]['lapv'] for r in rels])
        print(f'  person shots: {len(ppl)} ({100*len(ppl)//len(rels)}%)')
        print(f'  global sharpness median: {np.median(lap):.0f}  blurry(<150): {int((lap<150).sum())}')
        # subject signals on person shots
        if ppl:
            eyes_closed = sum(1 for r in ppl if not V.get(r, {}).get('eyes'))
            look_away = sum(1 for r in ppl if not V.get(r, {}).get('on_cam', 1))
            unready_grp = sum(1 for r in ppl if V.get(r, {}).get('group_any_unready'))
            facesoft = sum(1 for r in ppl if 0 < V.get(r, {}).get('facesharp', 9999) < 120)
            print(f'  of person shots: eyes-closed {eyes_closed}, looking-away {look_away}, '
                  f'group-has-unready {unready_grp}, soft-face {facesoft}')
        # duplicate-ness vs current survivors
        surv = [r for r in main_now if r in Q and r not in set(restored)]
        def mindup(r):
            h = Q[r]['dhash']
            return min((common.hpop(h, Q[x]['dhash']) for x in surv if x != r), default=99)
        d = np.array([mindup(r) for r in rels])
        print(f'  near-duplicate of a survivor (<=12 dHash): {int((d<=12).sum())}/{len(rels)}')

    summarize('FALSE-KEEP (you kept, owner deleted)', false_keep)
    summarize('RESTORED (you archived, owner brought back)', restored)
    print('\nInterpretation hints:')
    print(' - If false-keeps are NOT blurry/duplicate but ARE eyes-closed/looking-away,'
          ' the readiness thresholds should weigh heavier (this is the usual finding).')
    print(' - If restored shots are near-duplicates, your dedup is too aggressive on'
          ' valued moments; raise keep-per-cluster for people/scenery.')
    print(' - Record durable findings to memory so the next project starts smarter.')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: learn_from_edits.py <FOLDER>'); sys.exit(1)
    main(sys.argv[1])
