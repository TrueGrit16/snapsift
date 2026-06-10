#!/usr/bin/env python3
"""
Phase 6: build a shareable shortlist of the top N keepers. Exports RESIZED COPIES
(originals untouched) into a new folder, date-ordered, with a _filelist.txt.

Selection: allocate slots per shooting session by sqrt(session size) with a per-
session cap (so one big burst can't dominate), keep a people quota (~half), enforce
dHash diversity, and guarantee at least one from every day. RESUMABLE export.

Usage: python scripts/shortlist_export.py <FOLDER> --count 90 --out Best90 [--budget 35]
Re-run until ALL DONE (export resumes; selection is recomputed and cached).
"""
import os, sys, json, math, time, datetime, argparse
from collections import Counter
from PIL import Image, ImageOps
sys.path.insert(0, os.path.dirname(__file__))
from lib import common, scoring

dt_of = common.dt_of

# Selection policy. The dHash floors are intentionally looser than the per-level
# clustering thresholds in build_cull_plan.LEVELS: dedup decides what survives,
# these only enforce visual variety within the shortlist.
DIVERSITY_HAM = 12      # min dHash distance between any two shortlist picks
SUB_DIVERSITY_HAM = 8   # looser floor for the subfolder (e.g. GoPro) quota
PEOPLE_RATIO = 0.6      # share of each session's slots reserved for people shots

def select(folder, count):
    wd = common.work_dir(folder)
    Q = common.load_jsonl_map(os.path.join(wd, 'quality.jsonl'))
    V = common.load_jsonl_map(os.path.join(wd, 'vision.jsonl'))
    plan_path = os.path.join(wd, 'cull_plan.json')
    pool = json.load(open(plan_path))['keep'] if os.path.exists(plan_path) else [r for r in common.list_images(folder) if r in Q]
    pool = [r for r in pool if r in Q]
    canon = [r for r in pool if '/' not in r]
    sub = [r for r in pool if '/' in r]
    canon.sort(key=lambda r: (dt_of(Q[r]) or datetime.datetime.min, r))
    sess = common.sessionize(canon, Q)
    sub_quota = min(len(sub), max(0, count // 11))
    canon_budget = count - sub_quota
    CAP = max(6, canon_budget // 8)
    w = {i: math.sqrt(len(s)) for i, s in enumerate(sess)}; sw = sum(w.values()) or 1
    alloc = {i: max(1, min(CAP, round(w[i] / sw * canon_budget))) for i in w}
    # trim/grow to budget; every session keeps its guaranteed 1, so the total
    # can exceed --count only when there are more sessions than budget slots
    while sum(alloc.values()) > canon_budget:
        shrinkable = [j for j in alloc if alloc[j] > 1]
        if not shrinkable:
            break
        i = min(shrinkable, key=lambda j: w[j]); alloc[i] -= 1
    while sum(alloc.values()) < canon_budget:
        i = max(alloc, key=lambda j: w[j]); alloc[i] += 1
    def ks(r):
        return scoring.keeper_score(Q[r], V.get(r, {}))
    def person(r):
        return scoring.person(V.get(r, {}))
    sel = []; hs = []
    def add(r):
        sel.append(r); hs.append(Q[r]['dhash'])
    for i, s in enumerate(sess):
        k = alloc[i]
        ppl = sorted([r for r in s if person(r)], key=ks, reverse=True)
        scn = sorted([r for r in s if not person(r)], key=ks, reverse=True)
        nppl = min(len(ppl), max(1, int(round(k * PEOPLE_RATIO))) if ppl else 0)
        picks = []
        for r in ppl[:nppl]:
            if all(common.hpop(Q[r]['dhash'], h) >= DIVERSITY_HAM for h in hs):
                picks.append(r); hs.append(Q[r]['dhash'])
            if len(picks) >= k:
                break
        for r in scn + ppl:
            if len(picks) >= k:
                break
            if r in picks:
                continue
            if all(common.hpop(Q[r]['dhash'], h) >= DIVERSITY_HAM for h in hs):
                picks.append(r); hs.append(Q[r]['dhash'])
        if not picks and s:
            picks = [max(s, key=ks)]; hs.append(Q[picks[0]]['dhash'])
        sel.extend(picks)
    for r in sorted(sub, key=ks, reverse=True):
        if sub_quota <= 0:
            break
        if all(common.hpop(Q[r]['dhash'], h) >= SUB_DIVERSITY_HAM for h in hs):
            add(r); sub_quota -= 1
    # order by date
    def tk(r):
        d = dt_of(Q[r]); return (9, r) if (not d) else (0, d.timestamp())
    sel = list(dict.fromkeys(sel)); sel.sort(key=tk)
    return sel, Q, V

def main(a):
    folder = a.folder; wd = common.work_dir(folder)
    cache = os.path.join(wd, 'shortlist.json')
    if os.path.exists(cache):
        sel = json.load(open(cache))
        Q = common.load_jsonl_map(os.path.join(wd, 'quality.jsonl'))
        V = common.load_jsonl_map(os.path.join(wd, 'vision.jsonl'))
    else:
        sel, Q, V = select(folder, a.count)
        json.dump(sel, open(cache, 'w'))
    outdir = os.path.join(folder, a.out); os.makedirs(outdir, exist_ok=True)
    donef = os.path.join(wd, 'shortlist_done.txt')
    done = set(int(x) for x in open(donef).read().split()) if os.path.exists(donef) else set()
    t0 = time.time(); n = 0
    for i, rel in enumerate(sel, 1):
        if i in done:
            continue
        dst = os.path.join(outdir, f'{a.prefix}_{i:02d}.jpg')
        im = Image.open(os.path.join(folder, rel)); im = ImageOps.exif_transpose(im).convert('RGB')
        w, h = im.size; sc = 2048.0 / max(w, h)
        if sc < 1:
            im = im.resize((round(w * sc), round(h * sc)), Image.LANCZOS)
        im.save(dst, 'JPEG', quality=88, optimize=True)
        open(donef, 'a').write(f'{i}\n'); n += 1
        if time.time() - t0 > a.budget:
            print(f'exported {n}; total {len(done) + n}/{len(sel)}'); return
    # filelist + report
    def day(r):
        d = dt_of(Q.get(r, {}))
        return d.strftime('%b %d') if d else 'undated'
    with open(os.path.join(outdir, '_filelist.txt'), 'w') as fh:
        fh.write(f'{a.out} shortlist - {len(sel)} photos, date order\n\n')
        for i, rel in enumerate(sel, 1):
            tags = ('people ' if scoring.person(V.get(rel, {})) else '')
            fh.write(f'{a.prefix}_{i:02d}.jpg  {day(rel)}  <- {rel}  {tags}\n')
    print(f'exported {n}; ALL DONE {len(done) + n}/{len(sel)}')
    print('per day:', dict(sorted(Counter(day(r) for r in sel).items())))
    print('people shots:', sum(1 for r in sel if scoring.person(V.get(r, {}))))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--count', type=int, default=90)
    ap.add_argument('--out', default='Shortlist')
    ap.add_argument('--prefix', default='Pick')
    ap.add_argument('--budget', type=float, default=35)
    main(ap.parse_args())
