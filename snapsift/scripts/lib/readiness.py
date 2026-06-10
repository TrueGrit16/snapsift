"""
Unready-moment detection from MediaPipe face-mesh landmarks (refine_landmarks=True,
which adds the 10 iris points). This is the signal classic pipelines lack: blink,
gaze-on-camera, head pose. See references/methodology.md section 5.

Usage: detect a face (BlazeFace), crop it with margin, upscale to ~256, run
face_mesh on the crop, pass the landmark list here. Works per face, so a caller
can evaluate every face in a group shot.
"""
import math

L_EYE = [33, 160, 158, 133, 153, 144]   # outer, top1, top2, inner, bot2, bot1
R_EYE = [362, 385, 387, 263, 373, 380]

# |yaw_norm| beyond this = head turned away (methodology.md section 5/6).
# Single source of truth for assess_face, scoring.unready_reason and the
# 'frontal' summary field in modern_vision.
YAW_TURNED = 0.12

def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def ear(lm, idx, w, h):
    """Eye Aspect Ratio. Lower = more closed. Closed ~ < 0.15-0.16."""
    p = [(lm[i].x * w, lm[i].y * h) for i in idx]
    return (_d(p[1], p[5]) + _d(p[2], p[4])) / (2 * _d(p[0], p[3]) + 1e-6)

def gaze(lm, w, h):
    """Iris offset within each eye, normalized to half eye-width.
    Returns (gx, gy): ~0 is looking at the lens; |gx|>~0.55 is looking away."""
    def gx(iris, outer, inner):
        c = (lm[outer].x + lm[inner].x) / 2
        half = abs(lm[outer].x - lm[inner].x) / 2 + 1e-6
        return (lm[iris].x - c) / half
    def gy(iris, top, bot):
        c = (lm[top].y + lm[bot].y) / 2
        half = abs(lm[top].y - lm[bot].y) / 2 + 1e-6
        return (lm[iris].y - c) / half
    lx = gx(468, 33, 133); rx = gx(473, 263, 362)
    ly = gy(468, 159, 145); ry = gy(473, 386, 374)
    return (lx + rx) / 2, (ly + ry) / 2

def head_yaw(lm):
    """Cheap yaw proxy: nose tip vs midpoint of outer eye corners, normalized by
    inter-eye width. ~0 frontal; |yaw|>~0.12 means the head is turned."""
    nose = lm[1].x
    mid = (lm[33].x + lm[263].x) / 2
    eyew = abs(lm[33].x - lm[263].x) + 1e-6
    return (nose - mid) / eyew

def mouth_open(lm, w, h):
    """Lip gap over inter-ocular distance; large mid-burst usually = talking."""
    top = (lm[13].x * w, lm[13].y * h); bot = (lm[14].x * w, lm[14].y * h)
    le = (lm[33].x * w, lm[33].y * h); re = (lm[263].x * w, lm[263].y * h)
    iod = _d(le, re) + 1e-6
    return _d(top, bot) / iod

def smile(lm, w, h):
    """Geometric smile proxy (noisy; soft bonus only). Returns (width_ratio,
    corner_lift). Smiling widens the mouth and lifts the corners above lip center."""
    lc = (lm[61].x * w, lm[61].y * h); rc = (lm[291].x * w, lm[291].y * h)
    top = (lm[13].x * w, lm[13].y * h); bot = (lm[14].x * w, lm[14].y * h)
    le = (lm[33].x * w, lm[33].y * h); re = (lm[263].x * w, lm[263].y * h)
    iod = _d(le, re) + 1e-6
    width_ratio = _d(lc, rc) / iod
    corner_lift = ((top[1] + bot[1]) / 2 - (lc[1] + rc[1]) / 2) / iod
    return width_ratio, corner_lift

def assess_face(lm, w, h,
                ear_thr=0.155, gaze_thr=0.55, gaze_thr_y=0.85, yaw_thr=YAW_TURNED):
    """Return a per-face readiness dict. eyes_open, on_camera, plus raw values
    so callers can re-threshold. 'ready' = eyes open AND on camera AND frontal."""
    e = (ear(lm, L_EYE, w, h) + ear(lm, R_EYE, w, h)) / 2
    gx, gy = gaze(lm, w, h)
    yaw = head_yaw(lm)
    mo = mouth_open(lm, w, h)
    wr, cl = smile(lm, w, h)
    eyes_open = e > ear_thr
    on_camera = abs(gx) < gaze_thr and abs(gy) < gaze_thr_y and abs(yaw) < yaw_thr
    is_smile = (wr > 0.62 and cl > 0.02) or mo > 0.12
    return {
        'ear': round(e, 3), 'gx': round(gx, 3), 'gy': round(gy, 3),
        'yaw': round(yaw, 3), 'mouth_open': round(mo, 3),
        'eyes_open': bool(eyes_open), 'on_camera': bool(on_camera),
        'smile': bool(is_smile),
        'ready': bool(eyes_open and on_camera),
    }
