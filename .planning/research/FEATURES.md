# Feature Landscape: Windows Desktop Audio (Stem Separation & Capture)

**Domain:** Windows desktop apps with playback, recording, and system-audio capture — scoped to **StemSeparator**’s Windows port with **macOS feature parity** (including recording).
**Researched:** 2026-04-01
**Overall confidence:** **MEDIUM–HIGH** for WASAPI behavior (Microsoft Learn); **MEDIUM** for market “table stakes” (synthesis from common product patterns + official audio docs).

## Table Stakes

Features users expect from a credible Windows desktop audio tool in this class. Missing these tends to feel broken or “unfinished,” regardless of stem quality.

| Feature | Why expected | Complexity | Notes |
|--------|----------------|------------|--------|
| **WASAPI shared-mode playback & capture** | Default path for modern Windows audio; broad device compatibility | Med | Exclusive mode is niche; shared mode matches typical DAW-adjacent tools and is required for **loopback** (exclusive streams cannot use loopback per Microsoft). |
| **Endpoint loopback (“system mix”) capture** | “Record what’s playing” without extra cables — parity with macOS system capture goals | Med–High | WASAPI: capture on the **render** endpoint with `AUDCLNT_STREAMFLAGS_LOOPBACK` (shared mode). Delivers the mix playing on that endpoint, not a single app by default. |
| **Microphone / line-in capture** | Musicians expect to capture interface input alongside or instead of loopback | Low–Med | Distinct from loopback; still standard for recording workflows. |
| **Device enumeration & user selection** | Multiple outputs (interface, HDMI, Bluetooth) are normal on Windows | Med | Users must pick the correct render device for loopback to match what they hear. |
| **Clear handling of format / sample-rate** | WASAPI and devices expose different mix formats | Med | Resampling or explicit format negotiation avoids silent failures or speed/pitch errors. |
| **Windows privacy & permission UX** | Microphone access can be blocked by OS settings | Low (UX) | Actionable errors and links to Settings — not optional polish for recording features. |
| **Stable separation pipeline with CPU fallback** | Table stakes *for this product* after macOS validation | Med | GPU (CUDA) when available; must complete on CPU without corrupting output — already a project requirement. |
| **Export & preview of stems** | Core product promise | Med | WAV (or advertised formats), progress, cancel — baseline for any separator app. |

## Differentiators

Not universally “expected,” but they justify choosing this product over a generic recorder or a web tool.

| Feature | Value proposition | Complexity | Notes |
|--------|-------------------|------------|--------|
| **High-quality stem separation** | The reason to use StemSeparator vs. only recording | High | Model quality, chunking, ensemble — product core. |
| **CUDA-accelerated inference + graceful CPU fallback** | Speed on NVIDIA PCs; accessibility elsewhere | Med | Differentiator vs. CPU-only or cloud-only tools. |
| **Time-stretch, loops, beat-related workflows** | Producer-oriented workflow depth | Med–High | Matches validated macOS scope; strengthens “one app” positioning. |
| **Application / process-scoped loopback (where supported)** | Capture **one** app’s audio without the full system mix | High | Microsoft documents **ActivateAudioInterfaceAsync** + structures that restrict capture to a **specific process tree** (include/exclude modes); sample requires **Windows 10 build 20348 or later**. This is **not** the same as classic endpoint loopback — stronger when it works, but narrower OS floor and edge cases (e.g. reported gaps with some apps). Treat as **optional tier** or phase-gated differentiator vs. parity baseline. |
| **Low-latency monitoring / sensible buffer defaults** | Recording and playback feel “pro” | Med | Especially if users monitor through the app. |
| **Internationalization & cohesive PySide6 UI** | Professional desktop bar | Med | Already on macOS; parity is a differentiator vs. rough ports. |

## Anti-Features

Things that are tempting but should be avoided or sharply scoped.

| Anti-feature | Why avoid | What to do instead |
|--------------|-----------|---------------------|
| **Relying on “Stereo Mix” / vendor loopback as the only path** | Not present on all hardware; inconsistent naming; user confusion | Prefer **WASAPI endpoint loopback**; optional legacy device if detected. |
| **Exclusive-mode-only capture for “system” audio** | Loopback and exclusive mode are incompatible in the documented WASAPI model | Use **shared mode** for loopback; document exclusive use for specialist playback only. |
| **Promising DRM’d or protected content capture** | Trusted/DRM audio paths may block loopback capture | Document limitations; do not market as circumvention. |
| **Shipping unsigned or sketchy kernel virtual audio drivers by default** | Trust, security, and support burden | If virtual devices are needed, prefer documented installers, licensing clarity, and explicit user consent (aligns with PROJECT.md licensing constraint). |
| **“macOS parity” without documenting Windows capture deltas** | Different APIs and OS floors (e.g. process loopback build requirement) | Explicit **parity scope B** matrix: what matches, what degrades, what’s unsupported. |

## Feature Dependencies

```
Microphone / line-in capture → (independent) basic recording
Endpoint WASAPI loopback → render device selection + shared-mode capture path
Application/process loopback → OS build check + process picker + fallback to endpoint loopback
Stem separation → model assets + device (CUDA/CPU) + export pipeline
Recording → separation queue / file pipeline (product-defined wiring)
```

## MVP Recommendation (Windows Port)

Prioritize:

1. **Endpoint loopback + input capture + playback** using WASAPI-appropriate patterns — establishes **recording parity** with macOS at the “system / input” level.
2. **Separation, preview, export** with **CUDA + CPU fallback** — core value.
3. **One clear differentiator** in the first release window: either **application loopback** (if OS floor is acceptable) or **polished device/format UX** — avoid half-shipping both.

Defer: **Process-scoped loopback** until baseline loopback is solid and OS compatibility is validated; treat per-app capture as **stretch** unless roadmap explicitly prioritizes it over other parity items.

## Sources

- [Loopback Recording (WASAPI)](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording) — Microsoft Learn (loopback definition, `AUDCLNT_STREAMFLAGS_LOOPBACK`, shared mode requirement, DRM note).
- [Application loopback audio capture (sample)](https://learn.microsoft.com/en-us/samples/microsoft/windows-classic-samples/applicationloopbackaudio-sample/) — Microsoft Learn (process-scoped capture, build **20348+** requirement, `ActivateAudioInterfaceAsync`).
- Project scope: `.planning/PROJECT.md` (Windows port, CUDA/CPU, parity including recording).
