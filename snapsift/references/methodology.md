# Methodology: the science behind the scoring

Table of contents
1. Why simple approaches fail
2. Technical quality (no-reference)
3. Aesthetic quality (NIMA-style proxies)
4. Subject and face quality
5. Unready-moment detection (blink, gaze, head pose)
6. Duplicate clustering and best-frame selection
7. The composite scores
8. Default thresholds (all in one place)
9. Citations

---

## 1. Why simple approaches fail

Two naive methods look reasonable and are actively harmful:

- **Global sharpness (variance of Laplacian on the whole image).** It rewards busy, high-frequency backgrounds and is blind to a soft subject. On a real collection, the photos the owner deleted had a *higher* median global sharpness than the ones they kept. A sharp palm tree behind a slightly soft face still scores high.
- **"Keep one per perceptual-hash cluster."** It throws away second and third frames of moments people treasure, and it picks the survivor on a near-random sharpness tiebreak rather than on which frame has everyone's eyes open.

The fix is to score the **subject** and the **moment**, and to be conservative about removing people and valued scenes.

## 2. Technical quality (no-reference)

Computed in `scripts/quality_metrics.py` on a downscaled grayscale (long edge ~768-1024 for comparability across resolutions).

- **Sharpness, two measures:** variance of the Laplacian, and Tenengrad energy = mean of (Sobel_x^2 + Sobel_y^2). Two measures are more robust than one. Combine: `sharp = 0.6*clip(lapv/800) + 0.4*clip(tenengrad/15000)`.
- **Exposure / well-exposedness:** fraction of pixels in a healthy band (e.g. 40..215), plus the fraction clipped to shadows (<25 or <12) and highlights (>235 or >243), plus mean luminance. `expo = clip(well/0.85) * (1 - 0.6*max(0,over-0.2) - 0.5*max(0,under-0.2))`.
- **Contrast:** standard deviation of luminance, `clip(std/75)`.
- Optional: with opencv-contrib present (it installs alongside mediapipe), `cv2.quality.QualityBRISQUE` gives a trained no-reference score; treat lower BRISQUE as better and blend lightly. NIQE is also available. These are nice-to-have, not required.

The research basis is the no-reference IQA literature: BRISQUE uses locally normalized luminance natural-scene statistics; NIQE is fully blind. The practical primitive cues (Laplacian variance, Tenengrad, edge density, FFT energy, under/over-exposed fractions) are standard.

## 3. Aesthetic quality (NIMA-style proxies)

A trained neural aesthetic model (Google NIMA predicts a 1-10 human-rating distribution) is the gold standard but its weights are not downloadable in this sandbox. Reproduce its signal with computable proxies:

- **Colourfulness** (Hasler-Susstrunk): with `rg = R-G`, `yb = 0.5*(R+G)-B`, `colorf = sqrt(std(rg)^2 + std(yb)^2) + 0.3*sqrt(mean(rg)^2 + mean(yb)^2)`.
- **Saturation:** mean S channel in HSV.
- **Composition:** spectral-residual saliency map (compute in numpy: log-magnitude of FFT minus its blurred self, inverse-FFT, square, Gaussian-blur, normalize). Take the saliency centroid; reward it sitting near a rule-of-thirds power point. `comp = max(0, 1 - dist_to_nearest_third/0.4)`.

`AE = 0.65*color + 0.35*comp` where `color = 0.6*clip(colorf/65) + 0.4*clip(sat/120)`.

## 4. Subject and face quality

Computed in `scripts/modern_vision.py` with MediaPipe.

- **Person presence:** MediaPipe Pose (full body). This is the most reliable "is there a person" signal at distance, from behind, or at an angle. On a real set it found people in 377 photos including 170 that every face detector missed. Use `body OR face` as the person flag so people shots are never culled as scenery.
- **Faces:** MediaPipe BlazeFace (`face_detection`, model_selection=1). Fewer false positives than Haar cascades, which fire on foliage.
- **Face-region sharpness:** Laplacian variance computed *inside the face box*. This is the focus-on-subject signal. Out-of-focus face => reject.
- **Eyes open / smile / frontality:** run face_mesh on an upscaled crop of the largest face (small travel-photo faces fail mesh at full frame; crop with ~40% margin and resize to 256). See section 5.

## 5. Unready-moment detection (blink, gaze, head pose)

This is the signal that distinguishes a keeper person shot from a reject, and the one naive pipelines lack entirely. All from MediaPipe face_mesh with `refine_landmarks=True` (gives 478 landmarks including 10 iris points). Implemented in `scripts/lib/readiness.py`.

- **Blink / eyes-open — Eye Aspect Ratio (EAR).** For each eye, EAR = (||p2-p6|| + ||p3-p5||) / (2*||p1-p4||) using lid landmarks. Eyes closed if EAR below ~0.15-0.16. Average both eyes. Landmark sets: left [33,160,158,133,153,144], right [362,385,387,263,373,380].
- **Gaze on camera.** With refined landmarks, the iris centers are 468 (left) and 473 (right). For each eye compute the iris offset between the inner and outer eye corners, normalized to half eye-width: `gx = (iris_x - (outer_x+inner_x)/2) / (|outer_x-inner_x|/2)`. ~0 means looking at the lens; |gx| beyond ~0.55 means looking away. Do the same vertically.
- **Head pose (yaw).** Quick proxy: nose-tip x (landmark 1) versus the midpoint of the outer eye corners (33, 263), normalized by inter-eye width. Beyond ~0.12 means the head is turned. For a precise roll/pitch/yaw, run solvePnP on six stable landmarks (nose tip, chin, both eye outer corners, both mouth corners) against a generic 3D face model.
- **Mouth open (talking mid-sentence).** Lip opening (13 to 14) over inter-ocular distance; a large value mid-burst usually means caught talking.
- **Smile.** Lip-corner lift plus mouth-width / inter-ocular ratio. Geometric smile is noisy; treat as a soft bonus only. If the Tasks-API FaceLandmarker with blendshapes is available, `mouthSmileLeft/Right` is far better.

**A face is "ready"** when eyes are open, gaze is roughly on camera, and the head is not strongly turned. **Group rule:** evaluate every prominent face; if any is blinking or clearly looking away, prefer a sibling frame. **Context exception:** closed eyes during a hug/laugh/kiss can be intentional; do not hard-reject solely on a blink when the moment reads as candid.

## 6. Duplicate clustering and best-frame selection

- **Cluster** by chaining shots that are both perceptually similar (dHash Hamming distance within a threshold) and close in capture time (e.g. within 25-30s). For GoPro/phone sequences without reliable timestamps, chain by filename order plus similarity. Note: GoPro chaptered videos (sequential GX01xxxx files) are one continuous recording, not duplicates.
- **Pick keepers** by the expression-aware score (section 7), not raw sharpness. Keep 1 for `strong`, up to 2-3 for `balanced` when frames differ meaningfully (different expressions, someone smiling in one and not another).
- dHash: resize to 9x8 grayscale, compare adjacent columns, 64-bit hash. Hamming distance via `bin(a^b).count('1')`.

## 7. The composite scores

Two scores. **keeper_score** chooses the best frame within a cluster and ranks for the shortlist. **techqual** decides whether a standalone is too poor to keep.

```
TQ = 0.50*sharp + 0.30*expo + 0.20*contrast            # technical
AE = 0.65*color + 0.35*comp                            # aesthetic
if person:
    portrait   = clip(face_fraction/0.06)
    facefocus  = clip(face_sharpness/1200)
    keeper = 0.45*TQ + 0.20*AE + 0.05
           + 0.10*portrait + 0.08*eyes_open + 0.07*smile
           + 0.05*on_camera + 0.03*frontal + 0.05*body_visibility
else:
    keeper = 0.60*TQ + 0.40*AE
```

A standalone is "poor" if: very low sharpness on the subject; mean luminance under ~32 or shadow-clip over ~0.5 (near-black, unless it is an intentional night/fire scene with light sources); highlight blow-out over ~0.42; or well-exposedness under ~0.40. Protect a poor-but-person frame if it is the best of its session.

For the shortlist, allocate slots per session by sqrt(session_size) with a per-session cap (so one huge burst does not dominate), keep a people quota (~50% of the set), enforce dHash diversity across picks, and guarantee at least one from every day/key moment.

## 8. Default thresholds (one place to tune)

| Signal | Default | Meaning |
|---|---|---|
| EAR eyes-closed | < 0.15-0.16 | blink / closed |
| iris gaze off | |gx| > 0.55 | looking away (horizontal) |
| head yaw turned | |yaw_norm| > 0.12 | head turned away |
| mouth-open | lip/iod > 0.12 | likely talking |
| blur floor (subject) | face_lapv low, or global lapv<150 AND tenengrad<6500 | genuinely soft |
| near-black | mean < 32 or shadow-clip > 0.5 | unless intentional night/fire |
| blown highlights | highlight-clip > 0.42 | overexposed |
| dedup similar | dHash Hamming <= 12-14 | near duplicate |
| dedup time gap | <= 25-30 s | same moment |
| portrait | face_fraction >= 0.02-0.05 | prominent face |

Tune against the owner's corrections; do not treat these as fixed.

## 9. Citations

- NIMA: Neural Image Assessment (Talebi & Milanfar, Google). https://research.google/blog/introducing-nima-neural-image-assessment/ and https://arxiv.org/pdf/1709.05424
- BRISQUE no-reference IQA (Mittal et al.). https://live.ece.utexas.edu/publications/2012/TIP%20BRISQUE.pdf
- LIVE no-reference QA / NIQE overview. http://live.ece.utexas.edu/research/Quality/nrqa.htm
- Eye Aspect Ratio blink detection with MediaPipe. https://github.com/Pushtogithub23/Eye-Blink-Detection-using-MediaPipe-and-OpenCV
- Eye blink, tracking and head pose estimation. https://app.readytensor.ai/publications/eye-blink-tracking-and-head-pose-estimation-1ktcLiEdmOpN
- Commercial culling signal confirmation (out-of-focus faces, blinks, expressions, per-face group checks, context-awareness): FilterPixel https://filterpixel.com/culling and Aftershoot comparisons https://imagen-ai.com/valuable-tips/aftershoot-vs-filterpixel-vs-imagen/
