#!/usr/bin/env python3
"""
Phase 3: cluster, score, and build a keep/archive plan. Moves NOTHING.
Writes work/cull_plan.json = {keep, archive, reasons}.

- Clusters near-duplicates by dHash + capture-time proximity.
- Keeps the best 1-3 per cluster by the expression-aware keeper_score
  (gentle on people moments; aggressive on scenery).
- Flags genuinely poor standalones, but protects good person shots.
- Guarantees every shooting session keeps its best frame so no moment is wiped.

Levels: light | balanced | strong  (see SKILL.md).
Usage: python scripts/build_cull_plan.py <FOLDER> [--level balanced]
"""
import os, sys, json, datetime, argparse
from collections import Counter
sys.path.insert(0, os.path.dirname(__file__))
from lib import common, scoring

dt_of = common.dt_of

LEVELS = {
    # ham: dedup similarity, gap: seconds, keep_people: max keepers per people cluster
    'light':    dict(ham=8,  gap=15, keep_people=3, keep_scenery=2, do_poor=False),
    'balanced': dict(ham=12, gap=25, keep_people=2, keep_scenery=1, do_poor=True),
    'strong':   dict(ham=14, gap=30, keep_people=1, keep_scenery=1, do_poor=True),
}

def main(folder, level):
    cfg = LEVELS[level]
    wd = common.work_dir(folder)
    Q = common.load_jsonl_map(os.path.join(wd, 'quality.jsonl'))
    V = common.load_jsonl_map(os.path.join(wd, 'vision.jsonl'))
    if not Q:
        print('Run quality_metrics.py first.'); sys.exit(1)
    imgs = [r for r in common.list_images(folder) if r in Q]
    canon = [r for r in imgs if '/' not in r]
    sub = [r for r in imgs if '/' in r]  # e.g. GoPro/
    canon.sort(key=lambda r: (dt_of(Q[r]) or datetime.datetime.min, r))
    sub.sort()

    def cluster(seq, use_time):
        out = []; cur = []
        for r in seq:
            if not cur:
                cur = [r]; continue
            prev, first = cur[-1], cur[0]
            sim = (common.hpop(Q[prev]['dhash'], Q[r]['dhash']) <= cfg['ham']
                   and common.hpop(Q[first]['dhash'], Q[r]['dhash']) <= cfg['ham'] + 5)
            close = True
            if use_time and dt_of(Q[prev]) and dt_of(Q[r]):
                close = (dt_of(Q[r]) - dt_of(Q[prev])).total_seconds() <= cfg['gap']
            if sim and close:
                cur.append(r)
            else:
                out.append(cur); cur = [r]
        if cur:
            out.append(cur)
        return out

    clusters = cluster(canon, True) + cluster(sub, False)
    def ks(r):
        return scoring.keeper_score(Q[r], V.get(r, {}))
    def is_person(r):
        return scoring.person(V.get(r, {}))

    keep = set(); archive = {}
    for c in clusters:
        ranked = sorted(c, key=ks, reverse=True)
        kmax = cfg['keep_people'] if any(is_person(r) for r in c) else cfg['keep_scenery']
        # keep top kmax that are meaningfully distinct (dHash apart) else just top1
        kept_here = [ranked[0]]
        for r in ranked[1:]:
            if len(kept_here) >= kmax:
                break
            if all(common.hpop(Q[r]['dhash'], Q[k]['dhash']) >= 6 for k in kept_here):
                kept_here.append(r)
        for r in c:
            if r in kept_here:
                keep.add(r)
            else:
                archive[r] = 'duplicate'

    # poor-quality filter on survivors, protecting good people shots
    if cfg['do_poor']:
        for r in list(keep):
            pr = scoring.poor_reason(Q[r], V.get(r, {}))
            if pr and not scoring.good_person(Q[r], V.get(r, {})):
                keep.discard(r); archive[r] = pr

    # unready-moment filter on surviving person shots (blink / look-away).
    # This is the fix the eval surfaced: the readiness detector now rejects
    # standalone unready shots, not just chooses burst keepers. Session guarantee
    # below still protects the best frame of any moment.
    if cfg['do_poor']:
        for r in list(keep):
            ur = scoring.unready_reason(Q[r], V.get(r, {}), level)
            if ur:
                keep.discard(r); archive[r] = ur

    # session guarantee: every session keeps its best 1 (>=2 if large)
    sess = common.sessionize(canon, Q)
    guard = 0
    for s in sess:
        need = 2 if len(s) >= 8 else (1 if len(s) >= 3 else 0)
        have = [r for r in s if r in keep]
        if len(have) < need:
            for r in sorted([x for x in s if x in archive], key=ks, reverse=True)[:need - len(have)]:
                archive.pop(r, None); keep.add(r); guard += 1

    keep_l = [r for r in imgs if r in keep]
    arch_l = [r for r in imgs if r in archive]
    plan = {'level': level, 'keep': keep_l, 'archive': arch_l,
            'reasons': {r: archive[r] for r in arch_l}}
    json.dump(plan, open(os.path.join(wd, 'cull_plan.json'), 'w'))
    ppl_arch = sum(1 for r in arch_l if is_person(r))
    print(f'level={level}  images={len(imgs)}  clusters={len(clusters)}')
    print(f'KEEP={len(keep_l)}  ARCHIVE={len(arch_l)}  (session-guard protected {guard})')
    print('archive reasons:', dict(Counter(plan['reasons'].values())))
    print(f'person-shots in archive: {ppl_arch} '
          f'({sum(1 for r in arch_l if is_person(r) and archive[r]=="duplicate")} are non-best duplicates)')
    print('plan written to', os.path.join(wd, 'cull_plan.json'))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--level', default='balanced', choices=list(LEVELS))
    a = ap.parse_args()
    main(a.folder, a.level)
