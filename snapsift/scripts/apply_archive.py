#!/usr/bin/env python3
"""
Phase 5: apply the plan. Moves planned rejects into Archive/ (mirroring the
original layout), appends to Archive/_archive_manifest.csv, and prints an
integrity reconciliation. NEVER deletes. Reversible (move back to restore).

Usage: python scripts/apply_archive.py <FOLDER> [--dry-run]
"""
import os, sys, json, shutil, csv, argparse
from collections import Counter
sys.path.insert(0, os.path.dirname(__file__))
from lib import common

def main(folder, dry):
    wd = common.work_dir(folder)
    plan = json.load(open(os.path.join(wd, 'cull_plan.json')))
    arch_dir = os.path.join(folder, 'Archive')
    reasons = plan['reasons']
    before_keep = len(common.list_images(folder))
    before_arch = len(common.archive_image_rels(folder))
    moved = 0; rows = []
    for rel in plan['archive']:
        src = os.path.join(folder, rel)
        dst = os.path.join(arch_dir, rel)
        if dry:
            rows.append((rel, reasons[rel])); continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # truth check via listdir of the source dir
        srcdir = os.path.dirname(src) or folder
        present = os.path.basename(src) in os.listdir(srcdir) if os.path.isdir(srcdir) else False
        if present and not os.path.exists(dst):
            try:
                shutil.move(src, dst); moved += 1; rows.append((rel, reasons[rel]))
            except Exception as e:
                print('  could not move', rel, '->', e)
    if dry:
        print(f'DRY RUN: would move {len(rows)} files. reasons:',
              dict(Counter(r for _, r in rows)))
        return
    # manifest (append, dedup)
    os.makedirs(arch_dir, exist_ok=True)
    mpath = os.path.join(arch_dir, '_archive_manifest.csv')
    existing = []
    if os.path.exists(mpath):
        with open(mpath) as fh:
            rd = csv.reader(fh); next(rd, None)
            existing = [tuple(r) for r in rd if r]
    allrows = sorted(set(existing + rows))
    with open(mpath, 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['archived_file', 'reason'])
        for r in allrows:
            w.writerow(r)
    after_keep = len(common.list_images(folder))
    after_arch = len(common.archive_image_rels(folder))
    print(f'moved {moved} to Archive. reasons:', dict(Counter(r for _, r in rows)))
    print('=== INTEGRITY ===')
    print(f'before: {before_keep} in main + {before_arch} in Archive = {before_keep + before_arch}')
    print(f'after:  {after_keep} in main + {after_arch} in Archive = {after_keep + after_arch}')
    if before_keep + before_arch != after_keep + after_arch:
        print(f'WARNING: photo totals do not reconcile '
              f'({before_keep + before_arch} before vs {after_keep + after_arch} after) - '
              f'verify the moves above before doing anything else.')
    else:
        print('reconciled: no photos lost.')
    print('manifest:', mpath)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('folder'); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    main(a.folder, a.dry_run)
