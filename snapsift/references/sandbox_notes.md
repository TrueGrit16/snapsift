# Sandbox and environment notes (read before running)

These are real failure modes hit while building this pipeline in a Cowork / isolated-Linux sandbox over a mounted user folder. Ignoring them wastes hours.

## Compute and time limits

- **No GPU, ~2 CPU cores.** Deep stacks that need PyTorch (ultralytics/YOLO, insightface, deepface) are too large/slow to install within the per-call time limit and may need GPU. Use MediaPipe, which is CPU-friendly and bundles small models.
- **Each shell call is independent and time-capped (~45s).** No cwd/env carryover. Long jobs are killed mid-run.
- **Background processes do NOT survive between calls.** `nohup ... &` gets reaped when the spawning call returns. Do not rely on it.
- **Therefore: every heavy script must be resumable and time-budgeted.** Write results to a `.jsonl` as you go, record completed file ids, accept a wall-clock budget argument (e.g. 36-40s), stop cleanly when the budget is hit, and skip already-done files on the next call. Re-invoke until it prints `ALL DONE`. All scripts in this skill already do this; keep the pattern if you extend them.
- If a call times out, a child process may linger and block the next call ("process already running"). Wait a few seconds, `pkill -9 -f <script>`, then continue.

## The mounted-folder filesystem (most important)

The user's folder is a synced mount. It behaves unlike a normal disk:

- **`os.path.exists` returns stale True for files the user deleted.** Trust `os.listdir` for ground truth. A file can report exists=True yet fail to open. When diffing what changed, list directories; do not stat by path.
- **Overwrite works; creating a file with a name the user previously deleted FAILS.** Deleted names are tombstoned (`FileNotFoundError` on open-for-write). If you must regenerate output and names may be tombstoned, write to a fresh folder or fresh names.
- **Deletion from the sandbox is blocked by default** (`rm` returns Operation not permitted). To actually delete, call the `allow_cowork_file_delete` tool for the folder first. For culling you never need this: move to Archive instead of deleting.
- **Moving (shutil.move / rename) works** within the mount and is instant (same filesystem). This is how files go to Archive and how restores come back.
- **Large `find`/`ls` output can exceed tool limits.** Summarize (counts, `uniq -c` on extensions) instead of dumping full listings.

## Reading and writing across the two filesystems

- The shell sandbox and the file tools (Read/Write/Edit) can see the same mounted files but via different path roots. Build text/markdown with whichever is convenient, but run image/CV processing in the shell where Python, OpenCV and MediaPipe live.
- To let yourself view a rendered contact sheet, write the PNG into the outputs folder and open it with the image Read path; the sandbox path and the viewer path differ.

## Installing MediaPipe (do this exactly)

- `pip install --break-system-packages "mediapipe==0.10.14"`. Pin 0.10.14: it ships the offline `mp.solutions` API (face_detection, face_mesh with refine_landmarks for iris, pose) whose small models are bundled in the wheel, so no runtime model download is needed. Newer 0.10.3x exposes only the Tasks API, which requires downloading `.task` model files at runtime (often blocked).
- The install is large; pip may time out once or twice but caches downloads. Re-run the same command until it completes, then verify `python -c "import mediapipe as mp; print(hasattr(mp,'solutions'))"` prints True.
- Installing mediapipe also pulls `opencv-contrib-python`, which adds `cv2.quality` (BRISQUE/NIQE) and `cv2.saliency`. Handy bonus, not required.
- Quiet the noisy logs with `os.environ['GLOG_minloglevel']='3'` and filter stderr lines containing WARNING/I0000/W0000/XNNPACK in shell pipelines.
- MediaPipe solution objects are not picklable and graphs are per-process. Instantiate them once per process (or per worker) and reuse across images; running single-process at ~4 images/sec is fine, batched across calls.

## pip / packages generally

- Always `pip install --break-system-packages`. PIL, numpy, OpenCV, ffmpeg/ffprobe are typically preinstalled. Check with a quick import before assuming.
- exiftool is usually absent; read EXIF with PIL (`_getexif`) and video metadata with `ffprobe -show_format -show_streams -print_format json`.

## Don't bypass restricted web fetching

Use the provided web search / fetch tools for any web content. Do not curl/wget arbitrary URLs from the shell. Model files that come bundled with a pinned pip package (as with mediapipe 0.10.14) are the clean way to get vision models here.
