# nomercy-libass

One libass, built by us, for every surface NoMercy renders subtitles on.

## Why

Before this, four origins:

| surface | came from |
| --- | --- |
| web | a vendored JavaScript port of libass (SubtitlesOctopus) |
| desktop | **nothing** — `win32-x86-64/ass.dll` not found on Windows |
| Android | `io.github.peerless2012.ass` |
| Apple | a prebuilt XCFramework fetched from a third party |

Four builds, four versions, four ways to fall short — and no way to tell which
one a bug belonged to. This repo builds libass, freetype, fribidi and harfbuzz
from pinned, digest-verified sources and publishes every artifact from one
release, so a subtitle drawn in a browser and one drawn on a television came out
of the same code.

## Layout

- `versions.env` — the one place a version or digest is written
- `scripts/fetch.sh` — fetch and verify every source
- `scripts/build-target.sh` — the four builds, in dependency order, for one target
- `scripts/build-apple.sh` — the four Apple slices and the XCFramework
- `cross/*.ini` — one meson cross file per target
- `.github/workflows/release.yml` — the whole matrix on a tag

## Targets

`linux-x86-64`, `windows-x86-64`, `android-arm64-v8a`, `android-armeabi-v7a`,
`android-x86_64`, `wasm`, `apple` (ios + tvos, device + simulator).

## The bar

The Android app's `lib/nomercy-ass` carries the tuning months of production
found. This pipeline is not done until it matches or beats it, measured:

| tier | pool | glyph cap | libass cache | render ceiling |
| --- | --- | --- | --- | --- |
| LOW (265MB TV boxes) | 14 MB | 2 500 | 8 MB | 1280x720 |
| MEDIUM (1-2 GB) | 20 MB | 4 000 | 16 MB | 1920x1080 |
| HIGH (4 GB+) | 24 MB | 6 000 | 32 MB | 1920x1080 |

The entry cap and the MB cap are independent and both matter: 16 MB with a
1 500-entry cap measured 1 834 ms average dynamic render because the count limit
evicted before the MB budget was reached and every evicted glyph was
re-rasterized. 16 MB / 4 000 returns it to ~400 ms.

## Wiring the consumers

**Desktop — done.** `scripts/package.sh` emits
`libass-<version>-<platform>.tar.gz` flat, which is exactly what
`nomercy-player-core-kmp`'s `NativeArchives` resolves and what
`AssRenderers.jvm` searches. No player change is needed; publishing the artifact
is the whole integration.

**Android — one swap left.** `AndroidAssRenderer` is written against
`io.github.peerless2012:ass-kt`'s JNI wrapper, while the desktop drives libass
through our own JNA interface in `subtitles-libass/src/jvmMain/.../LibAss.kt`.
JNA runs on Android, so the swap is to move `LibAss.kt` to a source set both
share and rewrite `AndroidAssRenderer` against it, loading our `.so` from the
APK's `jniLibs`. That deletes `ass-kt` from `gradle/libs.versions.toml` and
leaves one renderer implementation instead of two.

**Web — the wasm target.** `packages/nomercy-subtitle-octopus` and the vendored
`public/js/octopus/subtitles-octopus.js` go once the wasm artifact publishes;
the video player links ours instead.

**Apple.** `subtitles-libass/build.gradle.kts` fetches a third-party XCFramework
by digest today. Point `libassArchive` at our release and the cinterop is
unchanged.

## The web worker

`scripts/build-wasm-worker.sh` links the wasm build into
`nomercy-libass-worker.js` + `.wasm`, exporting the libass entry points the
NoMercy wrapper's worker bridge calls and preloading the fallback face at
`/fonts`. The wrapper in `packages/nomercy-subtitle-octopus` keeps its API; only
the worker underneath it changes, so retiring SubtitlesOctopus is a three-file
swap rather than a rewrite.
