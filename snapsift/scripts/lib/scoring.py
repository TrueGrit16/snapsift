"""
Composite scoring shared by the cull plan and the shortlist. See
references/methodology.md sections 7-8 for the formulas and thresholds.
q = quality.jsonl row, v = vision.jsonl row (may be {} if vision not run).
"""
from .common import clip
from .readiness import YAW_TURNED

def person(v):
    return max(int(bool(v.get('person'))), 1 if v.get('nf', 0) >= 1 else 0)

def face_fraction(v):
    return v.get('maxf', 0) or 0

def technical(q):
    sharp = 0.6 * clip(q.get('lapv', 0) / 800.0) + 0.4 * clip(q.get('ten', 0) / 15000.0)
    over = q.get('over', 0); under = q.get('under', 0)
    expo = clip(q.get('well', 0) / 0.85) * (1 - 0.6 * max(0, over - 0.2) - 0.5 * max(0, under - 0.2))
    contrast = clip(q.get('contrast', 0) / 75.0)
    return 0.50 * sharp + 0.30 * expo + 0.20 * contrast

def aesthetic(q):
    color = 0.6 * clip(q.get('colorf', 0) / 65.0) + 0.4 * clip(q.get('sat', 0) / 120.0)
    return 0.65 * color + 0.35 * clip(q.get('comp', 0) / 0.75)

def keeper_score(q, v):
    """Expression-aware score for choosing the best frame and ranking."""
    TQ = technical(q); AE = aesthetic(q)
    if person(v):
        portrait = clip(face_fraction(v) / 0.06)
        facefocus = clip(v.get('facesharp', 0) / 1200.0)
        return (0.45 * TQ + 0.20 * AE + 0.05
                + 0.10 * portrait + 0.08 * v.get('eyes', 0) + 0.07 * v.get('smile', 0)
                + 0.05 * v.get('on_cam', 0) + 0.03 * v.get('frontal', 0)
                + 0.05 * clip(v.get('bodyvis', 0)))
    return 0.60 * TQ + 0.40 * AE

def is_soft(q):
    return q.get('lapv', 9999) < 150 and q.get('ten', 99999) < 6500

def poor_reason(q, v):
    """Why a standalone is too poor to keep, or None. Night/fire scenes (dark but
    with light sources / not a person) are NOT auto-rejected for darkness alone;
    callers should protect intentional-dark sessions via the session guarantee.

    Blur is judged on the subject for person shots (out-of-focus face = reject) and
    with a looser global floor than v1: the eval showed an AND-of-two-sharpness
    floor let textured-but-soft frames survive."""
    lap = q.get('lapv', 9999); ten = q.get('ten', 99999)
    mean = q.get('mean', 128); well = q.get('well', 1)
    under = q.get('under', 0); over = q.get('over', 0)
    if person(v) and 0 < v.get('facesharp', 9999) < 90 and v.get('maxf', 0) > 0.012:
        return 'soft_face'
    if lap < 140 or (lap < 300 and ten < 4800):
        return 'blurry'
    if mean < 32 or under > 0.5:
        return 'underexposed'
    if mean > 226 or over > 0.42:
        return 'overexposed'
    if well < 0.40:
        return 'badly_exposed'
    return None

def unready_reason(q, v, level='balanced'):
    """Why a standalone PERSON shot is an 'unready moment', or None. Wires the
    readiness detector (blink/gaze/head-pose) into the reject logic. Only fires on
    shots dominated by one or two prominent faces (a group candid where one person
    blinks is left to dedup, not nuked). The session guarantee still protects the
    best frame of any moment."""
    if not person(v):
        return None
    faces = v.get('faces') or []
    if not faces or v.get('maxf', 0) < 0.02:
        return None
    prominent = [f for f in faces if f.get('frac', 0) >= 0.02]
    if len(prominent) == 0 or len(prominent) > 2:
        return None
    dom = prominent[0]
    if not dom.get('eyes_open', True):
        return 'eyes_closed'
    if abs(dom.get('yaw', 0)) > YAW_TURNED:
        return 'looking_away'
    if level == 'strong' and not dom.get('on_camera', True):
        return 'looking_away'
    return None

def good_person(q, v):
    """A person shot worth protecting from the poor-quality filter."""
    if not person(v):
        return False
    if q.get('lapv', 0) < 70:
        return False
    return bool(v.get('eyes', 0) or v.get('smile', 0)
                or v.get('maxf', 0) >= 0.008
                or (v.get('body', 0) and v.get('bodyvis', 0) > 0.55))
