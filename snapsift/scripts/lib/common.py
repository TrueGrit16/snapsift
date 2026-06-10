"""
Shared helpers for the photo-culling-curator skill.

Design notes (see references/sandbox_notes.md):
- Truth about what files exist comes from os.listdir, NOT os.path.exists
  (the synced mount returns stale True for deleted files).
- Heavy passes are resumable: results stream to a .jsonl in a persistent
  work dir keyed by the target folder, and already-processed files are skipped.
"""
import os, json, hashlib, datetime

IMG_EXTS = ('.jpg', '.jpeg', '.png')
VID_EXTS = ('.mp4', '.mov', '.m4v', '.avi')
# Camera formats the pipeline cannot decode (no RAW/HEIC codecs available).
# Inventory reports these so they are never skipped silently.
UNSUPPORTED_EXTS = ('.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2',
                    '.raf', '.heic', '.heif')
# Folders we never treat as source images (our own outputs).
SKIP_DIRS = {'Archive', '.curator_work'}
# Device subfolder mirrored inside Archive/ (one level of subfolders supported).
GOPRO_DIR = 'GoPro'
# Minutes of EXIF silence that separates two shooting sessions.
SESSION_GAP_MIN = 25

def is_shortlist_dir(name):
    n = name.lower()
    return n.startswith('whatsapp') or n.startswith('shortlist') or n.startswith('best')

def list_images(folder, max_depth=1):
    """Return image rels (relative to folder) using listdir as truth.
    Includes the top level and one level of subfolders (e.g. GoPro/),
    skipping Archive, our work dir, hidden files and shortlist output dirs."""
    out = []
    for f in sorted(os.listdir(folder)):
        p = os.path.join(folder, f)
        if f.startswith('.') or f.startswith('._'):
            continue
        if os.path.isdir(p):
            if f in SKIP_DIRS or is_shortlist_dir(f) or max_depth < 1:
                continue
            for g in sorted(os.listdir(p)):
                if g.lower().endswith(IMG_EXTS) and not g.startswith('.'):
                    out.append(f + '/' + g)
        elif f.lower().endswith(IMG_EXTS):
            out.append(f)
    return out

def list_videos(folder):
    out = []
    for root in [folder, os.path.join(folder, GOPRO_DIR)]:
        if not os.path.isdir(root):
            continue
        rel_prefix = '' if root == folder else GOPRO_DIR + '/'
        for f in sorted(os.listdir(root)):
            if f.lower().endswith(VID_EXTS) and not f.startswith('.'):
                out.append(rel_prefix + f)
    return out

def list_unsupported(folder):
    """Camera files we cannot decode (RAW/HEIC), same walk as list_images."""
    out = []
    for f in sorted(os.listdir(folder)):
        p = os.path.join(folder, f)
        if f.startswith('.'):
            continue
        if os.path.isdir(p):
            if f in SKIP_DIRS or is_shortlist_dir(f):
                continue
            out += [f + '/' + g for g in sorted(os.listdir(p))
                    if g.lower().endswith(UNSUPPORTED_EXTS) and not g.startswith('.')]
        elif f.lower().endswith(UNSUPPORTED_EXTS):
            out.append(f)
    return out

def archive_image_rels(folder):
    """All image rels under Archive/ (recursive — the plan mirrors the original
    layout, so any source subfolder can exist inside Archive)."""
    arch = os.path.join(folder, 'Archive')
    out = []
    if not os.path.isdir(arch):
        return out
    for root, _dirs, files in os.walk(arch):
        for f in files:
            if f.lower().endswith(IMG_EXTS) and not f.startswith('.'):
                rel = os.path.relpath(os.path.join(root, f), arch)
                out.append(rel.replace(os.sep, '/'))
    return out

def work_dir(folder):
    """Persistent per-folder scratch dir under /tmp (survives between calls,
    keeps the user's folder clean)."""
    h = hashlib.md5(os.path.abspath(folder).encode()).hexdigest()[:10]
    d = os.path.join('/tmp', 'curator_work', h)
    os.makedirs(d, exist_ok=True)
    return d

def load_done(jsonl_path):
    done = set()
    if os.path.exists(jsonl_path):
        for line in open(jsonl_path):
            try:
                done.add(json.loads(line)['rel'])
            except Exception:
                pass
    return done

# --- perceptual hash ---
def dhash_from_gray(arr):
    import numpy as np
    from PIL import Image
    im = Image.fromarray(arr.astype('uint8')).resize((9, 8))
    s = np.asarray(im, dtype='int16')
    diff = s[:, 1:] > s[:, :-1]
    bits = 0
    for b in diff.flatten():
        bits = (bits << 1) | int(b)
    return format(bits, '016x')

def hpop(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count('1')

# --- EXIF capture time ---
def dt_of(q):
    """Capture datetime from a quality.jsonl row, or None."""
    s = q.get('dt')
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s, '%Y:%m:%d %H:%M:%S')
    except Exception:
        return None

def sessionize(rels, Q, gap_min=SESSION_GAP_MIN):
    """Split a date-sorted rel list into shooting sessions on EXIF-time gaps."""
    sess = []; cur = []
    for r in rels:
        if cur and dt_of(Q[cur[-1]]) and dt_of(Q[r]) and \
           (dt_of(Q[r]) - dt_of(Q[cur[-1]])).total_seconds() > gap_min * 60:
            sess.append(cur); cur = [r]
        else:
            cur.append(r)
    if cur:
        sess.append(cur)
    return sess

def exif_datetime(path):
    from PIL import Image
    from PIL.ExifTags import TAGS
    try:
        im = Image.open(path)
        ex = im._getexif() or {}
        d = {TAGS.get(k, k): v for k, v in ex.items()}
        s = d.get('DateTimeOriginal') or d.get('DateTime')
        if not s:
            return None
        return datetime.datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None

def load_jsonl_map(path):
    out = {}
    if os.path.exists(path):
        for line in open(path):
            try:
                r = json.loads(line)
                if 'err' not in r:
                    out[r['rel']] = r
            except Exception:
                pass
    return out

def clip(x, a=0.0, b=1.0):
    return max(a, min(b, x))
