# GTA Reel Sound Studio

A Claude skill that turns GTA 6 (or any gameplay) clips into viral-style Reels, TikToks and Shorts. It layers realistic foley and meme sounds on the impact frame, with a stop before the hit, ducking, zoom/shake/flash and captions, mixes to -14 LUFS, and checks sync and masking before delivering.

The sound library ships inside the skill: `skills/gta-reel-sound-studio/gta_sfx_library/` holds 263 sounds (`sfx/*.flac` plus `library.json`). Whatever way you get this repo, you get both the skill and the sounds.

## Install in Claude Code

**As a plugin** (installs the skill and its library together):
```
/plugin marketplace add mr-zito/gta-reel-sound-studio
/plugin install gta-reel-sound-studio@gta-reel-sound-studio
```

**Or as a personal skill**, by copying the skill folder into your skills directory:
```bash
git clone https://github.com/mr-zito/gta-reel-sound-studio.git
# macOS / Linux / Git Bash
mkdir -p ~/.claude/skills && cp -r gta-reel-sound-studio/skills/gta-reel-sound-studio ~/.claude/skills/
```
```powershell
# Windows PowerShell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse -Force gta-reel-sound-studio\skills\gta-reel-sound-studio "$env:USERPROFILE\.claude\skills\"
```

**Downloading the ZIP** from GitHub (Code → Download ZIP) gives the same files: unzip it and copy `skills/gta-reel-sound-studio` as above.

## Requirements

- **ffmpeg 6.1+** on PATH: `winget install Gyan.FFmpeg` (Windows) or `brew install ffmpeg` (macOS).
- **Python 3** with numpy: `pip install numpy`.
- **Optional, for making new realistic sounds:** `pip install "earshot @ git+https://github.com/Leonxlnx/earshot"`.

## Use

Give Claude a clip: *"make a 20 s TikTok of this GTA 6 clip with meme sounds"*. It finds the moments, writes an edit plan from the library, renders a preview, checks it and delivers the final mp4 with a cue sheet.

## Layout

```
.claude-plugin/            plugin + marketplace manifests
skills/gta-reel-sound-studio/
  SKILL.md                 the instructions
  scripts/                 render_reel, check_reel, find_moments, list_sounds, index_folder, extract_compilation
  gta_sfx_library/         library.json, sfx/*.flac, missing.json, README.md (sources and rights)
```

## Rights

The library contains clips cut from YouTube compilations (Warrior SFX, TechKeyFi), including short clips of commercial songs (tag `music`). Keep this repository **private** and use the sounds for your own edits only. The `earshot` sounds are free for commercial use.
