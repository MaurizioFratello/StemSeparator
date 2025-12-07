# GitHub Release Guide - Version 1.0.0

This guide will walk you through creating your first GitHub release for Stem Separator v1.0.0.

---

## 📋 Pre-Release Checklist

### 1. Code Quality
- [ ] All tests pass: `pytest`
- [ ] Code is formatted: `black .`
- [ ] Linting passes: `flake8 .`
- [ ] No critical bugs in issue tracker

### 2. Documentation
- [x] README.md is complete and accurate
- [x] CHANGELOG.md is up to date
- [x] CONTRIBUTING.md exists
- [ ] All documentation links work
- [ ] API documentation is current

### 3. Version Numbers
- [ ] Version in `config.py` is `1.0.0`
- [ ] Version in `README.md` is `1.0.0`
- [ ] Version in `CHANGELOG.md` is `1.0.0`
- [ ] Git tag will be `v1.0.0`

### 4. Build Artifacts
- [ ] Build Intel DMG: `packaging/build_intel.sh`
- [ ] Build ARM64 DMG: `packaging/build_arm64.sh`
- [ ] Test both DMG files on clean systems
- [ ] Verify app launches and core features work

---

## 🔨 Step 1: Build Release Artifacts

### Build Intel Version
```bash
cd /Users/moritzbruder/Documents/04_Python/StemSeparator
./packaging/build_intel.sh
```

**Expected Output:**
- `dist/StemSeparator-intel.dmg` (~1-2 GB)

### Build ARM64 Version
```bash
./packaging/build_arm64.sh
```

**Expected Output:**
- `dist/StemSeparator-arm64.dmg` (~1-2 GB)

### Verify Builds
```bash
# Check file sizes
ls -lh dist/*.dmg

# Verify DMG integrity
hdiutil verify dist/StemSeparator-intel.dmg
hdiutil verify dist/StemSeparator-arm64.dmg
```

---

## 🏷️ Step 2: Create Git Tag

### Ensure All Changes Are Committed
```bash
git status
# Should show: "nothing to commit, working tree clean"
```

### Create and Push Tag
```bash
# Create annotated tag
git tag -a v1.0.0 -m "Version 1.0.0 - First Stable Release

Major Features:
- AI-powered stem separation with multiple models
- Ensemble separation for maximum quality
- System audio recording (macOS)
- Real-time stem player with mixing
- Beat detection and loop export
- Modern dark theme with native macOS integration
- Comprehensive documentation and testing

This is the first stable release ready for public use."

# Verify tag
git tag -l -n9 v1.0.0

# Push tag to GitHub
git push origin v1.0.0
```

---

## 🚀 Step 3: Create GitHub Release

### Navigate to GitHub
1. Go to: https://github.com/MaurizioFratello/StemSeparator
2. Click **"Releases"** (right sidebar)
3. Click **"Draft a new release"**

### Fill Release Form

#### 1. Choose a tag
- Select: `v1.0.0`
- Or type: `v1.0.0` if not yet pushed

#### 2. Release title
```
Version 1.0.0 - First Stable Release 🎉
```

#### 3. Release description

Copy this template and customize:

```markdown
# Stem Separator v1.0.0

**The first stable release of Stem Separator is here!** 🎉

Stem Separator is a professional macOS application for AI-powered separation of audio stems using state-of-the-art deep learning models.

## 🎯 What's New in v1.0.0

### Core Features
- 🎵 **Multiple AI Models**: Mel-Band RoFormer, BS-RoFormer, MDX-Net, Demucs v4
- 🎚️ **Ensemble Separation**: Combine models for maximum quality
- 🎤 **System Audio Recording**: Direct recording with BlackHole integration
- 🎧 **Stem Player**: Real-time mixing with individual volume control
- ⚡ **GPU Acceleration**: Apple Silicon (MPS) and NVIDIA (CUDA) support

### User Experience
- 🎨 Modern dark theme with native macOS integration
- 🌍 Multilingual support (English/German)
- 📊 Queue system for batch processing
- 🔄 Automatic chunking for long files
- 💪 Intelligent error handling with GPU fallback

### Quality & Stability
- ✅ 89% test coverage with 199+ tests
- ✅ Comprehensive documentation
- ✅ Professional code structure
- ✅ Ready for production use

## 📥 Downloads

Choose the version for your Mac:

- **Apple Silicon (M1/M2/M3)**: Download `StemSeparator-arm64.dmg`
- **Intel Macs**: Download `StemSeparator-intel.dmg`

### Installation
1. Download the DMG file for your Mac
2. Open the DMG and drag "Stem Separator" to Applications
3. Right-click the app and select "Open" (first time only)

## 📚 Documentation

- **[README](https://github.com/MaurizioFratello/StemSeparator#readme)**: Complete feature overview
- **[Installation Guide](https://github.com/MaurizioFratello/StemSeparator#-installation)**: Detailed setup instructions
- **[Usage Guide](https://github.com/MaurizioFratello/StemSeparator#-usage)**: How to use all features
- **[Troubleshooting](https://github.com/MaurizioFratello/StemSeparator#-troubleshooting)**: Common issues and solutions
- **[Contributing](./CONTRIBUTING.md)**: How to contribute
- **[Changelog](./CHANGELOG.md)**: Full version history

## 🔧 System Requirements

### Minimum
- macOS 10.15 (Catalina) or newer
- 8 GB RAM
- ~1.5 GB storage for models

### Recommended
- macOS 11.0+ (Big Sur) for Apple Silicon
- 16 GB RAM
- Apple Silicon (M1/M2/M3) or NVIDIA GPU

## 🐛 Known Issues

None reported for this release.

## 💬 Support

Having issues? Here's how to get help:
1. Check the [Troubleshooting Guide](https://github.com/MaurizioFratello/StemSeparator#-troubleshooting)
2. Search [existing issues](https://github.com/MaurizioFratello/StemSeparator/issues)
3. [Create a new issue](https://github.com/MaurizioFratello/StemSeparator/issues/new) with details

## 🙏 Credits

Special thanks to:
- **audio-separator** team
- **Demucs** (Meta AI Research)
- **BS-RoFormer** (ByteDance AI Lab)
- **Mel-Band RoFormer** community
- All contributors and testers

## 📄 License

This project uses open-source models and is available under the MIT License.

---

**Full Changelog**: [CHANGELOG.md](./CHANGELOG.md)

Made with ❤️ for the music community
```

#### 4. Upload DMG Files
- Drag `StemSeparator-intel.dmg` to the assets area
- Drag `StemSeparator-arm64.dmg` to the assets area

#### 5. Release Options
- [x] Set as the latest release
- [ ] Set as a pre-release (uncheck this)
- [ ] Create a discussion for this release (optional)

#### 6. Publish
- Click **"Publish release"**

---

## 🎨 Step 4: Post-Release Polish

### Add GitHub Topics/Tags
1. Go to repository main page
2. Click ⚙️ next to "About"
3. Add topics:
   ```
   audio-processing
   stem-separation
   music-production
   ai
   machine-learning
   macos
   python
   pyside6
   pytorch
   audio
   music
   demucs
   vocal-remover
   karaoke
   ```

### Update Repository Description
Set description to:
```
AI-powered audio stem separation for macOS with state-of-the-art models. Professional tool for separating vocals, drums, bass, and other instruments from music files.
```

### Add Website Link (optional)
If you have documentation site or landing page, add it.

### Enable Discussions (optional)
Settings → Features → Discussions → Enable

---

## 📢 Step 5: Announce Release

### GitHub Release Notes
Already published! GitHub will notify watchers.

### Social Media (optional)
Share on:
- Twitter/X
- Reddit (r/audioengineering, r/WeAreTheMusicMakers)
- Hacker News
- Product Hunt

Example post:
```
🎉 Stem Separator v1.0.0 is here!

AI-powered audio stem separation for macOS with:
- Multiple state-of-the-art models
- Ensemble mode for maximum quality
- System audio recording
- Real-time stem player

Free & open source!
https://github.com/MaurizioFratello/StemSeparator
```

---

## ✅ Post-Release Checklist

### Immediate (within 24 hours)
- [ ] Monitor GitHub Issues for installation problems
- [ ] Respond to initial user feedback
- [ ] Check download counts
- [ ] Verify DMG files download correctly

### Within 1 week
- [ ] Update any outdated documentation
- [ ] Plan v1.0.1 patch if critical bugs found
- [ ] Thank early adopters and contributors
- [ ] Start planning v1.1.0 features

### Ongoing
- [ ] Triage and respond to issues
- [ ] Review pull requests
- [ ] Update documentation as needed
- [ ] Plan future releases

---

## 🐛 Rollback Plan (If Needed)

If critical bugs are found after release:

### Option 1: Quick Patch (v1.0.1)
1. Fix bug in a new branch
2. Create tag `v1.0.1`
3. Build new DMGs
4. Create new release
5. Mark v1.0.0 as pre-release

### Option 2: Withdraw Release
1. Edit release on GitHub
2. Mark as "pre-release"
3. Add warning in description
4. Create new stable release when ready

---

## 📊 Success Metrics

Track these to measure release success:

- **Downloads**: Check GitHub release downloads
- **Stars**: Monitor repository stars
- **Issues**: Track bug reports vs feature requests
- **Community**: Watch forks, pull requests
- **Usage**: Monitor feedback and testimonials

---

## 🎯 Next Steps After Release

### Version 1.0.1 (Patch)
- Bug fixes only
- No new features
- Quick turnaround

### Version 1.1.0 (Minor)
- New features from roadmap
- Improvements
- Non-breaking changes

### Version 2.0.0 (Major)
- Breaking changes
- Major new features
- Architecture updates

---

## 📞 Need Help?

- **GitHub Issues**: Technical problems
- **GitHub Discussions**: General questions
- **Email**: For private inquiries

---

**Good luck with your release! 🚀**

Remember: The first release is always special. Take time to celebrate, then iterate based on user feedback!
