#!/usr/bin/env python3
"""
Phase 4: verification contact sheets. Renders montages into an output dir so you
can LOOK before moving anything (and after, for the kept sample).

Sets:
  archive      - everything the plan would archive, person-shots first, reason labels
  people_dups  - people clusters: kept (green) vs archived (red), with E/S tags
  kept_sample  - random sample of survivors (sanity check after moving)
  shortlist    - a folder of exported shortlist images

Usage:
  python scripts/contact_sheet.py <FOLDER> --set archive --out /path/out [--budget 36]
Re-run with the same --set to resume multi-page sets (pages are skipped if present).
"""
import os, sys, json, math, time, random, argparse, datetime
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
from lib import common, scoring

def font(sz=12):
    try:
        return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', sz)
    except Exception:
        return ImageFont.load_default()

def thumb(path, th):
    try:
        im = Image.open(path); im.draft('RGB', (th * 2, th * 2))
        im = im.convert('RGB'); im.thumbnail((th, th)); return im
    except Exception:
        return Image.new('RGB', (th, th), (60, 60, 60))

def grid(folder, items, out_png, th=120, cols=10, title='', labeler=None, border=None):
    PAD = 3; CELL = th + 13
    rows = math.ceil(len(items) / cols)
    W = PAD + cols * (th + PAD); H = 20 + rows * CELL
    cv = Image.new('RGB', (W, H), (255, 255, 255)); dr = ImageDraw.Draw(cv)
    dr.text((6, 4), title, fill=(0, 0, 0), font=font(12))
    for i, it in enumerate(items):
        r = i // cols; c = i % cols; x = PAD + c * (th + PAD); y = 20 + r * CELL
        im = thumb(os.path.join(folder, it['rel']), th)
        ox = x + (th - im.width) // 2
        cv.paste(im, (ox, y))
        col = border(it) if border else None
        if col:
            dr.rectangle([ox, y, ox + im.width, y + im.height], outline=col, width=3)
        dr.text((x + 1, y + im.height + 1), labeler(it) if labeler else it['rel'][:8],
                fill=col or (0, 0, 0), font=font(11))
    cv.save(out_png)

def main(a):
    folder = a.folder; wd = common.work_dir(folder)
    os.makedirs(a.out, exist_ok=True)
    Q = common.load_jsonl_map(os.path.join(wd, 'quality.jsonl'))
    V = common.load_jsonl_map(os.path.join(wd, 'vision.jsonl'))
    plan = json.load(open(os.path.join(wd, 'cull_plan.json'))) if os.path.exists(os.path.join(wd, 'cull_plan.json')) else {}
    reasons = plan.get('reasons', {})

    if a.set == 'archive':
        items = [{'rel': r} for r in plan.get('archive', [])]
        items.sort(key=lambda it: (0 if scoring.person(V.get(it['rel'], {})) else 1, reasons.get(it['rel'], '')))
        per = 70
        for si in range(0, len(items), per):
            page = items[si:si + per]
            fn = os.path.join(a.out, f'archive_{si // per}.png')
            if os.path.exists(fn):
                continue
            grid(folder, page, fn, title=f'ARCHIVE candidates (person-shots first) p{si // per}',
                 labeler=lambda it: it['rel'].split('/')[-1][:8] + ' ' + reasons.get(it['rel'], '')[:4]
                         + (' P' if scoring.person(V.get(it['rel'], {})) else ''),
                 border=lambda it: (210, 120, 0) if scoring.person(V.get(it['rel'], {})) else (200, 0, 0))
            print('wrote', fn)

    elif a.set == 'people_dups':
        # reconstruct clusters cheaply by adjacency on dHash within current archive+keep
        keep = set(plan.get('keep', []))
        items = [{'rel': r} for r in (plan.get('keep', []) + plan.get('archive', []))]
        items = [it for it in items if scoring.person(V.get(it['rel'], {}))]
        items.sort(key=lambda it: it['rel'])
        fn = os.path.join(a.out, 'people_dups.png')
        grid(folder, items[:140], fn, th=130, cols=10,
             title='People shots: KEPT(green) vs ARCHIVED(red), E=eyes S=smile',
             labeler=lambda it: it['rel'].split('/')[-1][:8]
                     + (' K' if it['rel'] in keep else ' A')
                     + (' E' if V.get(it['rel'], {}).get('eyes') else '')
                     + (' S' if V.get(it['rel'], {}).get('smile') else ''),
             border=lambda it: (0, 160, 0) if it['rel'] in keep else (210, 30, 30))
        print('wrote', fn)

    elif a.set == 'kept_sample':
        keep = plan.get('keep') or common.list_images(folder)
        random.seed(7); samp = random.sample(keep, min(80, len(keep)))
        items = [{'rel': r} for r in sorted(samp)]
        fn = os.path.join(a.out, 'kept_sample.png')
        grid(folder, items, fn, title='Random sample of KEPT set (sanity check)')
        print('wrote', fn)

    elif a.set == 'shortlist':
        # render a folder of already-exported images
        sl = a.shortlist_dir
        if not sl or not os.path.isdir(sl):
            sys.exit('--shortlist-dir <exported folder> is required (and must exist) with --set shortlist')
        files = sorted(f for f in os.listdir(sl) if f.lower().endswith('.jpg'))
        items = [{'rel': f} for f in files]
        fn = os.path.join(a.out, 'shortlist_preview.png')
        grid(sl, items, fn, th=150, cols=9, title=f'Shortlist preview ({len(files)})',
             labeler=lambda it: it['rel'].replace('.jpg', '')[:12])
        print('wrote', fn)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--set', required=True,
                    choices=['archive', 'people_dups', 'kept_sample', 'shortlist'])
    ap.add_argument('--out', default='/tmp/curator_sheets')
    ap.add_argument('--shortlist-dir', dest='shortlist_dir', default=None)
    ap.add_argument('--budget', type=float, default=36)
    main(ap.parse_args())
