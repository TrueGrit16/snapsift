# Final step: push SnapSift to GitHub

The repo already exists (created for you): https://github.com/TrueGrit16/snapsift
These files are staged and ready. Open a terminal here and run:

```powershell
cd "F:\1. P71 Backup\MY WORK\SnapSift"
git init
git add .
git commit -m "SnapSift: AI photo culler that judges the moment, not just the megapixels"
git branch -M main
git remote add origin https://github.com/TrueGrit16/snapsift.git
git push -u origin main
```

If git asks you to sign in, use the GitHub login you already have in Chrome
(a browser window will pop up), or install GitHub CLI and run `gh auth login` first.

## Right after the push (this is what actually earns stars)
1. Open https://github.com/TrueGrit16/snapsift and confirm the README renders with the demo GIF up top.
2. Click the gear next to "About" and add topics:
   photography, ai, computer-vision, mediapipe, photo-culling, claude, image-quality, cli, photography-tools
3. Create a Release and attach `snapsift.skill` so people can one-click install the Claude skill.
4. Record a 20-30s screen capture of a real cull and replace assets/demo.gif with it (the synthetic one is a placeholder).
5. Post a "Show HN" and share on r/photography, r/Lightroom and X with the before/after and the benchmark table.
