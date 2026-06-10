# Publishing SnapSift to GitHub

These steps publish the repo under your account. Replace TrueGrit16 first
(it appears in README.md badges and clone URL).

## Option A: GitHub CLI (fastest)

```bash
# one-time: install gh and log in
gh auth login

cd snapsift
# swap the placeholder for your username everywhere
grep -rl TrueGrit16 . | xargs sed -i '' 's/TrueGrit16/your-handle/g'   # macOS
# (on Linux: grep -rl TrueGrit16 . | xargs sed -i 's/TrueGrit16/your-handle/g')

git init && git add . && git commit -m "SnapSift: AI photo culler that judges the moment, not just the megapixels"
gh repo create snapsift --public --source=. --remote=origin --push
```

## Option B: plain git + web

1. Create an empty repo named `snapsift` at https://github.com/new (no README/license).
2. Then:

```bash
cd snapsift
sed -i 's/TrueGrit16/your-handle/g' README.md
git init && git add . && git commit -m "Initial commit: SnapSift"
git branch -M main
git remote add origin https://github.com/your-handle/snapsift.git
git push -u origin main
```

## After pushing (for stars)

- Add 5-8 Topics: `photography`, `ai`, `computer-vision`, `mediapipe`, `photo-culling`, `claude`, `image-quality`, `cli`.
- Write a one-line repo description matching the README tagline.
- Attach `snapsift.skill` to a GitHub Release so people can one-click install.
- Record a 20-30s screen capture of a real cull and save it as `assets/demo.gif`, then add `![demo](assets/demo.gif)` near the top of the README. A demo GIF is the single biggest driver of stars.
- Replace the placeholder screenshots with your own (avoid posting other people's faces without consent).
- Share on r/photography, r/Lightroom, Hacker News ("Show HN"), and X with the before/after and the benchmark table.
