# Release Checklist v1.0.0

Quick checklist for releasing Stem Separator v1.0.0 to GitHub.

---

## ✅ Pre-Release

### Code Quality
- [ ] Run tests: `pytest`
- [ ] Format code: `black .`
- [ ] Lint code: `flake8 .`
- [ ] Fix any critical bugs

### Documentation
- [x] README.md complete
- [x] CHANGELOG.md updated
- [x] CONTRIBUTING.md exists
- [ ] All links tested

### Version Consistency
- [ ] Verify version is `1.0.0` in all files
- [ ] Update any hardcoded version numbers

---

## 🔨 Build Process

### Intel Build
```bash
./packaging/build_intel.sh
```
- [ ] Build completes successfully
- [ ] DMG file created: `dist/StemSeparator-intel.dmg`
- [ ] Test on Intel Mac (if available)

### ARM64 Build
```bash
./packaging/build_arm64.sh
```
- [ ] Build completes successfully
- [ ] DMG file created: `dist/StemSeparator-arm64.dmg`
- [ ] Test on Apple Silicon Mac

### Verify Builds
```bash
ls -lh dist/*.dmg
hdiutil verify dist/StemSeparator-intel.dmg
hdiutil verify dist/StemSeparator-arm64.dmg
```
- [ ] Both DMG files exist
- [ ] File sizes reasonable (~1-2 GB each)
- [ ] DMG verification passes

---

## 🏷️ Git Tag

### Commit Everything
```bash
git status  # should be clean
```
- [ ] All changes committed
- [ ] Working tree clean

### Create Tag
```bash
git tag -a v1.0.0 -m "Version 1.0.0 - First Stable Release"
git push origin v1.0.0
```
- [ ] Tag created locally
- [ ] Tag pushed to GitHub

---

## 🚀 GitHub Release

### Navigate to Releases
- [ ] Go to: https://github.com/MaurizioFratello/StemSeparator/releases
- [ ] Click "Draft a new release"

### Fill Form
- [ ] Tag: `v1.0.0`
- [ ] Title: `Version 1.0.0 - First Stable Release 🎉`
- [ ] Description: Use template from `docs/RELEASE_GUIDE.md`
- [ ] Upload: `StemSeparator-intel.dmg`
- [ ] Upload: `StemSeparator-arm64.dmg`
- [ ] Check: "Set as the latest release"
- [ ] Uncheck: "Set as a pre-release"

### Publish
- [ ] Click "Publish release"
- [ ] Verify release is live
- [ ] Test download links

---

## 🎨 Repository Settings

### Topics
- [ ] Add topics: `audio-processing`, `stem-separation`, `music-production`, `ai`, `macos`, `python`

### Description
- [ ] Update repository description
- [ ] Add website link (if applicable)

### Features (Optional)
- [ ] Enable Discussions
- [ ] Enable Wikis
- [ ] Configure Issues templates

---

## 📢 Announce (Optional)

- [ ] Twitter/X post
- [ ] Reddit (r/audioengineering, r/WeAreTheMusicMakers)
- [ ] Hacker News
- [ ] Product Hunt
- [ ] Email notifications to beta testers

---

## ✅ Post-Release

### Monitor (First 24 hours)
- [ ] Check for installation issues
- [ ] Respond to first comments/issues
- [ ] Verify downloads work correctly

### Track
- [ ] Monitor download count
- [ ] Watch for bug reports
- [ ] Note feature requests
- [ ] Track stars/forks

---

## 📊 Success!

**Your release is live!** 🎉

- Release URL: https://github.com/MaurizioFratello/StemSeparator/releases/tag/v1.0.0
- Downloads: Check on release page
- Stars: Watch repository stats

**Next:** Plan v1.0.1 (bug fixes) or v1.1.0 (new features)

---

For detailed instructions, see: [docs/RELEASE_GUIDE.md](docs/RELEASE_GUIDE.md)
