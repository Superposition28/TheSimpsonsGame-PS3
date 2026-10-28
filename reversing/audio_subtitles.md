# Original dialogue audio and subtitles

`audio_subtitles.py` reads the original PS3 EU STR archives and SNU files. It
recovers the numeric ALB -> SMB -> SNU / LH2 relationship, then optionally creates
a black MP4 with the decoded original audio and its localized subtitle burned in.
It does not read AudioMap, CSV exports, renamed datasets, or converted audio.

From the game module root, with Python 3.11+:

```powershell
python -B reversing/audio_subtitles.py `
  --snu audiostreams/t8_xxx_0/d_brt8_xxx_00033c4.exa.snu `
  --snu audiostreams/mr_xxx_0/d_homr_xxx_0005046.exa.snu `
  --snu audiostreams/FR/t8_xxx_0/d_brt8_xxx_00033c4.exa.snu `
  --snu audiostreams/IT/t8_xxx_0/d_brt8_xxx_00033c4.exa.snu `
  --snu audiostreams/ES/t8_xxx_0/d_brt8_xxx_00033c4.exa.snu
```

Defaults:

- Original input: `Source/PS3/EU/1/PS3_GAME/USRDIR`.
- Output: `GameFiles/original-audio-subtitles`.
- Tools: the engine's `EngineApps/Tools`, using the versions declared in
  `Tools.toml`: vgmstream-cli r2117 and FFmpeg 8.0.

Use `--source`, `--output`, or `--tools-root` to override those paths. Input must
remain beneath the module's Source directory and output beneath GameFiles.
Omit `--snu` to audit without making videos. Every invocation reads the original
archives again; `report.json` is generated evidence, never a lookup input.

Each demo directory contains `test.mp4`, lossless decoded `audio.wav`,
`subtitle.srt`, decoder/encoder logs, and `evidence.json`. The evidence records the
original SNU hash, decoded sample count, language, and the ALB/SMB/LH2 records.
`report.json` records original archive hashes, member paths, section/record
coordinates, payload hashes, recovered links, and unresolved streams. These local
outputs include game content and are ignored by Git.

The subtitle spans the decoded sample duration for this demonstration. That is
an explicit presentation choice: ALB and LH2 do not recover the original game's
subtitle dwell time, triggering, interruptions, or word timing. Decoding ignores
loop flags so a looping clip cannot create an infinite demo.

The numeric join covers 7,314 distinct individual dialogue streams in the
inspected EU source. Composite IGC tracks, ambience/music, the Nelson exception,
SBK subsongs, MUS/SNR/SNS, and VP6 audio need their respective control/timing data.
The script refuses to invent a subtitle for an unlinked SNU. See the
[LH2 reference](docs/PS3_GAME/FormatAnalysis/STR/imbedded-formats/lh2.html#audio-subtitle-join)
for field layouts, corpus counts, and the worked example.

