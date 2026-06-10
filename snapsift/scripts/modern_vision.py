#!/usr/bin/env python3
"""
Phase 2: modern vision. RESUMABLE and TIME-BUDGETED. Writes work/vision.jsonl.

MediaPipe full-body pose (person presence at distance/angle), BlazeFace faces,
and per-face readiness (face-region sharpness, eyes/EAR, gaze-on-camera, head yaw,
smile, frontality) via face_mesh on upscaled face crops. EVERY prominent face is
assessed so group shots can be judged on the worst face.

Requires: pip install --break-system-packages "mediapipe==0.10.14"
(see references/sandbox_notes.md for why that exact version).

Usage: python scripts/modern_vision.py <FOLDER> [BUDGET_SECONDS=36]
"""
import os, sys, json, time
os.environ['GLOG_minloglevel'] = '3'
import numpy as np, cv2
from PIL import Image
import mediapipe as mp
sys.path.insert(0, os.path.dirname(__file__))
from lib import common
from lib import readiness

mpfd = mp.solutions.face_detection
mpfm = mp.solutions.face_mesh
mpp = mp.solutions.pose

_fd = _fm = _pose = None
def init():
    global _fd, _fm, _pose
    _fd = mpfd.FaceDetection(model_selection=1, min_detection_confidence=0.35)
    _fm = mpfm.FaceMesh(static_image_mode=True, max_num_faces=1,
                        refine_landmarks=True, min_detection_confidence=0.3)
    _pose = mpp.Pose(static_image_mode=True, model_complexity=0,
                     min_detection_confidence=0.4)

def mesh_on_crop(a, box, W, H):
    x, y, fw, fh = box
    m = int(0.45 * max(fw, fh))
    x0, y0 = max(0, x - m), max(0, y - m)
    x1, y1 = min(W, x + fw + m), min(H, y + fh + m)
    crop = a[y0:y1, x0:x1]
    if crop.size == 0:
        return None, 0.0
    facesharp = float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY),
                                    cv2.CV_32F).var())
    s = 256 / max(crop.shape[:2])
    crop2 = cv2.resize(crop, (max(1, int(crop.shape[1] * s)),
                              max(1, int(crop.shape[0] * s))))
    rm = _fm.process(crop2)
    if not rm.multi_face_landmarks:
        return None, facesharp
    lm = rm.multi_face_landmarks[0].landmark
    hh, ww = crop2.shape[:2]
    return readiness.assess_face(lm, ww, hh), facesharp

def analyze(folder, rel):
    try:
        im = Image.open(os.path.join(folder, rel))
        im.draft('RGB', (720, 720)); a = np.asarray(im.convert('RGB'))
        H, W = a.shape[:2]; area = float(H * W)
        # pose / full body
        rp = _pose.process(a); body = 0; bodyvis = 0.0
        if rp.pose_landmarks:
            vis = [l.visibility for l in rp.pose_landmarks.landmark]
            torso = [vis[i] for i in [11, 12, 23, 24]]
            if sum(v > 0.5 for v in torso) >= 2:
                body = 1; bodyvis = float(np.mean(torso))
        # faces
        rf = _fd.process(a); boxes = []
        if rf.detections:
            for det in rf.detections:
                bb = det.location_data.relative_bounding_box
                boxes.append((det.score[0], int(bb.xmin * W), int(bb.ymin * H),
                              int(bb.width * W), int(bb.height * H)))
        boxes.sort(key=lambda b: b[3] * b[4], reverse=True)
        nf = len(boxes); maxf = 0.0
        faces_assessed = []
        any_unready = False; any_smile = False
        for sc, x, y, fw, fh in boxes[:5]:
            fr = fw * fh / area
            maxf = max(maxf, fr)
            if fr < 0.0015:
                continue
            res, fsharp = mesh_on_crop(a, (x, y, fw, fh), W, H)
            if res:
                res['frac'] = round(fr, 4); res['facesharp'] = round(fsharp, 1)
                faces_assessed.append(res)
                if not res['ready']:
                    any_unready = True
                if res['smile']:
                    any_smile = True
        # largest-face summary fields (back-compat with scoring)
        eyes = int(faces_assessed[0]['eyes_open']) if faces_assessed else 0
        on_cam = int(faces_assessed[0]['on_camera']) if faces_assessed else 0
        frontal = int(abs(faces_assessed[0]['yaw']) < readiness.YAW_TURNED) if faces_assessed else 0
        facesharp = faces_assessed[0]['facesharp'] if faces_assessed else 0.0
        return {'rel': rel, 'person': 1 if (body or nf > 0) else 0,
                'body': body, 'bodyvis': round(bodyvis, 2),
                'nf': nf, 'maxf': round(maxf, 4),
                'eyes': eyes, 'on_cam': on_cam, 'frontal': frontal,
                'smile': int(any_smile), 'facesharp': facesharp,
                'group_any_unready': int(any_unready and len(faces_assessed) > 1),
                'faces': faces_assessed}
    except Exception as e:
        return {'rel': rel, 'err': str(e)[:80]}

def main(folder, budget):
    wd = common.work_dir(folder); out = os.path.join(wd, 'vision.jsonl')
    done = common.load_done(out)
    todo = [r for r in common.list_images(folder) if r not in done]
    if not todo:
        print('ALL DONE', len(done)); return
    init(); t0 = time.time(); n = 0
    with open(out, 'a') as fh:
        for rel in todo:
            fh.write(json.dumps(analyze(folder, rel)) + '\n'); n += 1
            if n % 20 == 0:
                fh.flush()
            if time.time() - t0 > budget:
                break
    print(f'processed {n}; remaining ~{len(todo) - n}; total {len(done) + n}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: modern_vision.py <FOLDER> [BUDGET]'); sys.exit(1)
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 36.0)
