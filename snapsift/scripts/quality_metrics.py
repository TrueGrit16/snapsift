#!/usr/bin/env python3
"""
Phase 1: technical + aesthetic metrics for every image. RESUMABLE and TIME-BUDGETED.
Writes work/quality.jsonl (one row per image). Re-run until it prints ALL DONE.

Per image: Laplacian + Tenengrad sharpness, exposure (well-exposedness, clipping,
mean), contrast, colourfulness, saturation, spectral-residual saliency composition,
capture datetime, and a dHash for dedup. See references/methodology.md.

Usage: python scripts/quality_metrics.py <FOLDER> [BUDGET_SECONDS=38]
"""
import os, sys, json, time
import numpy as np, cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from lib import common

def saliency_thirds(gray):
    sm = cv2.resize(gray, (128, 128)).astype(np.float32)
    f = np.fft.fft2(sm); mag = np.abs(f); phase = np.angle(f)
    L = np.log(mag + 1e-8); R = L - cv2.blur(L, (3, 3))
    sal = np.abs(np.fft.ifft2(np.exp(R + 1j * phase))) ** 2
    sal = cv2.GaussianBlur(sal, (0, 0), 3); sal = sal / (sal.max() + 1e-8)
    ys, xs = np.mgrid[0:128, 0:128]; tot = sal.sum() + 1e-8
    cx = float((sal * xs).sum() / tot) / 128.0
    cy = float((sal * ys).sum() / tot) / 128.0
    pts = [(1/3, 1/3), (2/3, 1/3), (1/3, 2/3), (2/3, 2/3)]
    thirds = min(((cx - px) ** 2 + (cy - py) ** 2) ** 0.5 for px, py in pts)
    return float(max(0.0, 1.0 - thirds / 0.4))

def analyze(folder, rel):
    p = os.path.join(folder, rel)
    try:
        im = Image.open(p)
        dt = common.exif_datetime(p)
        im.draft('RGB', (1024, 1024))
        rgb_full = im.convert('RGB')
        gfull = np.asarray(rgb_full.convert('L'), dtype=np.float32)
        # standardize long edge ~1024
        H, W = gfull.shape; sc = 1024.0 / max(H, W)
        if sc < 1:
            gfull = cv2.resize(gfull, (max(1, int(W * sc)), max(1, int(H * sc))))
        lapv = float(cv2.Laplacian(gfull, cv2.CV_32F).var())
        gx = cv2.Sobel(gfull, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gfull, cv2.CV_32F, 0, 1, ksize=3)
        ten = float((gx * gx + gy * gy).mean())
        mean = float(gfull.mean())
        under = float((gfull < 25).mean()); over = float((gfull > 235).mean())
        well = float(((gfull >= 40) & (gfull <= 215)).mean())
        contrast = float(gfull.std())
        comp = saliency_thirds(gfull)
        # color on a small RGB
        small = rgb_full.copy(); small.thumbnail((256, 256))
        a = np.asarray(small, dtype=np.float32)
        Rc, Gc, Bc = a[:, :, 0], a[:, :, 1], a[:, :, 2]
        rg = Rc - Gc; yb = 0.5 * (Rc + Gc) - Bc
        colorf = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2)
                       + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
        hsv = cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGB2HSV)
        sat = float(hsv[:, :, 1].mean())
        dh = common.dhash_from_gray(gfull)
        return {'rel': rel, 'dt': dt.strftime('%Y:%m:%d %H:%M:%S') if dt else None,
                'lapv': round(lapv, 1), 'ten': round(ten, 1), 'mean': round(mean, 1),
                'under': round(under, 4), 'over': round(over, 4), 'well': round(well, 4),
                'contrast': round(contrast, 1), 'colorf': round(colorf, 1),
                'sat': round(sat, 1), 'comp': round(comp, 3), 'dhash': dh}
    except Exception as e:
        return {'rel': rel, 'err': str(e)[:80]}

def main(folder, budget):
    wd = common.work_dir(folder); out = os.path.join(wd, 'quality.jsonl')
    done = common.load_done(out)
    todo = [r for r in common.list_images(folder) if r not in done]
    if not todo:
        print('ALL DONE', len(done)); return
    t0 = time.time(); n = 0
    with open(out, 'a') as fh:
        for rel in todo:
            fh.write(json.dumps(analyze(folder, rel)) + '\n')
            n += 1
            if n % 25 == 0:
                fh.flush()
            if time.time() - t0 > budget:
                break
    print(f'processed {n}; remaining ~{len(todo) - n}; total {len(done) + n}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: quality_metrics.py <FOLDER> [BUDGET]'); sys.exit(1)
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 38.0)
