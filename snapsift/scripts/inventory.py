#!/usr/bin/env python3
"""
Phase 0: inventory a photo/video folder.
Counts, extensions, EXIF capture timeline (per day), and video duration/resolution
via ffprobe. Writes work/inventory.json. Fast; not resumable (no need).

Usage: python scripts/inventory.py <FOLDER>
"""
import os, sys, json, subprocess
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from lib import common

def vid_meta(p):
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', p],
            capture_output=True, text=True, timeout=60).stdout
        j = json.loads(out)
        dur = float(j.get('format', {}).get('duration', 0) or 0)
        w = h = None
        for s in j.get('streams', []):
            if s.get('codec_type') == 'video':
                w, h = s.get('width'), s.get('height'); break
        return dur, w, h
    except Exception:
        return 0, None, None

def main(folder):
    imgs = common.list_images(folder)
    vids = common.list_videos(folder)
    unsup = common.list_unsupported(folder)
    ext = Counter(os.path.splitext(r)[1].lower() for r in imgs + vids)
    days = Counter()
    for r in imgs:
        dt = common.exif_datetime(os.path.join(folder, r))
        days[dt.strftime('%Y-%m-%d') if dt else 'no-date'] += 1
    vdays = Counter(); vdur = defaultdict(float); res = Counter()
    for r in vids:
        dur, w, h = vid_meta(os.path.join(folder, r))
        res[f'{w}x{h}'] += 1; vdur['total'] += dur
    inv = {
        'folder': folder,
        'image_count': len(imgs), 'video_count': len(vids),
        'extensions': dict(ext),
        'photo_days': dict(sorted(days.items())),
        'video_total_minutes': round(vdur['total'] / 60, 1),
        'video_resolutions': dict(res),
        'unsupported_camera_files': len(unsup),
        'unsupported_extensions': dict(Counter(os.path.splitext(r)[1].lower() for r in unsup)),
    }
    wd = common.work_dir(folder)
    json.dump(inv, open(os.path.join(wd, 'inventory.json'), 'w'), indent=2)
    print(json.dumps(inv, indent=2))
    if unsup:
        print(f'\nWARNING: {len(unsup)} RAW/HEIC camera files cannot be decoded by this '
              f'pipeline and will NOT be scored or culled. Convert them to JPEG first '
              f'or handle them manually.')
    if vids:
        print(f'NOTE: {len(vids)} videos are inventoried only; the automated cull scores '
              f'photos and leaves videos untouched for manual review.')
    print('\nwork dir:', wd)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: inventory.py <FOLDER>'); sys.exit(1)
    main(sys.argv[1])
