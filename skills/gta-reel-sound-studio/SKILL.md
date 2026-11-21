---
name: gta-reel-sound-studio
description: Sound-design GTA 6 (or any gameplay) clips into viral TikTok/Reels/Shorts with the bundled GTA SFX library: 263 cut and tagged sounds (Warrior SFX and TechKeyFi meme sounds, earshot foley and beds). Layers realism and meme sounds on the impact frame, with stop-before-the-hit, ducking, zoom/shake/flash/captions, two-pass -14 LUFS, and a sync/masking check. Use for any game montage, meme edit, reel or short with sound effects, even if GTA isn't named.
---

# GTA Reel Sound Studio

This skill turns raw GTA 6 gameplay (or any game clip) into a reel that sounds produced. Every sound comes from the **GTA SFX library**: 263 sound effects already cut, tagged and level-matched, in three layers.

| Layer | What it does | In the library |
|---|---|---|
| **The world** | game audio, cleaned up, plus an ambience bed when it helps | `earshot` beds: `bed-city-street`, `bed-beach-waves`, `bed-rain-street`, `bed-busy-cafe` |
| **The realism** | the real sound of what the picture shows | 29 `earshot` foley sounds (tag `realistic`): crash, tyres, guns, punches, sirens, helicopter, splash, phone |
| **The joke** | the meme sound that comments on the moment | 230 sounds cut from the Warrior SFX #1–#3 and TechKeyFi compilations |

A pro meme edit layers these: the realistic crash *and* the metal pipe on the same frame.

## 0. The library and the tools ship with this skill

Everything sits in this skill's own folder:
- `${CLAUDE_SKILL_DIR}/gta_sfx_library/`: `library.json` (every sound's id, tags, length and peak time), `sfx/<id>.flac`, `missing.json`, `README.md` (sources and rights).
- `${CLAUDE_SKILL_DIR}/scripts/`: `render_reel.py`, `check_reel.py`, `find_moments.py`, `list_sounds.py`, `index_folder.py`, `extract_compilation.py`.

Start every job with:
```bash
SK="${CLAUDE_SKILL_DIR}"; LIB="$SK/gta_sfx_library"; S="$SK/scripts"
ls "$LIB/library.json" && python3 -c "import numpy" && ffmpeg -version | head -1
```

Put the absolute path of `$LIB` in the plan's `"sfx_dir"`. Requirements:
- **Python:** on Windows, use `python` or `py` if `python3` isn't found.
- **ffmpeg 6.1+** on PATH: `winget install Gyan.FFmpeg` on Windows, `brew install ffmpeg` on macOS.
- **numpy:** `pip install numpy`.

**If the library isn't there** (`${CLAUDE_SKILL_DIR}` is empty, or this copy of the skill came without its files), look in this order:
1. A `gta_sfx_library` folder or `gta_sfx_library.zip` in the working directory.
2. The user's Downloads folder.
3. The session's uploads.

Otherwise, ask the user to clone or download their repo `github.com/mr-zito/gta-reel-sound-studio`. Don't substitute other sounds silently.

Find sounds with the search tool, not from memory, because ids are exact:
```bash
python3 "$S/list_sounds.py" "$LIB" --tag impact --no-music
python3 "$S/list_sounds.py" "$LIB" --find "cash register"
python3 "$S/list_sounds.py" "$LIB" --tag realistic --max-len 2
```

**Tags:** `impact fail win money funny voice music sigma sad awkward transition whoosh glitch flashback buildup suspense hype police chaos notification ui rizz anime crowd explosion car weapon vehicle bed realistic explicit…`

**Duplicate names** get a pack suffix: `bone-crack` is the TechKeyFi one, and `twitch-alert-techkeyfi-a` is TechKeyFi's version of Warrior's `twitch-alert`.

**Not in the library** (`missing.json`): 10 Warrior sounds YouTube had muted in the source copies (Topac Engle, Please Stand By, Ultra Instinct Opening, The Good Ending, Daft Punk – Robot Rock, Goku Prowler, Thousand Yard Stare, Lego Batman Meme, Thumbs Down To Up, Stereo Hearts). Warrior #1's first seven sounds are also missing: Chinese Gong, Taco Bell, Awkward Moment, Awkward Pause, Camera Flash, Collect Gold and Bone Crack. The TechKeyFi stand-ins `taco-bell-bong`, `awkward-pause`, `camera-shutter` and `bone-crack` cover four of them. If the user asks for a missing one, say so and offer the nearest sound.

## The workflow

1. **Set up** `$LIB` and `$S` (section 0).
2. **Take in the footage.** Run `ffprobe` on each clip, then `python3 "$S/find_moments.py" clip.mp4 moments`, and *look at the frames* it saves, so you know what happens at each time. Combine this with what the user describes.
3. **Design the sound** in `plan.json`: world, then realism, then jokes (sections 1–3).
4. **Render a preview**, run `check_reel.py`, fix what it flags, then do the final render (section 4).
5. **Deliver** the mp4 with a cue sheet and the QA numbers (section 6).

## 1. Moment → sound map (ids are library ids)

The meme sound is funny because it comments on the moment, and the realistic layer makes it feel real. Ask "what's the joke here?", not "where is it loud?". Avoid using the same sound twice in a short reel unless the repetition is the joke.

| GTA 6 moment | Realism (`earshot`) | Joke (meme packs) | Picture |
|---|---|---|---|
| Wasted / ragdoll | `body-drop`, `punch-body` | `bone-crack`, `metal-pipe-falling`, `you-died`, `leon-kennedy-death`, `man-falls-down-stairs`, `body-thud` | zoom + shake, then `bw` |
| Car crash / bike bail | `car-crash-real` + `glass-break-real`, `tyres-screech` before | `metal-pipe-falling`, `lego-breaking`, `glass-breaking`, `anvil` | shake + flash |
| Explosion | `explosion-far` (align `start`), `deep-boom` | `flashbang-loud`, `building-explosion`, `thunder-loud`, `bass-drop-vine-boom` | flash + shake |
| Wanted level / chase | `police-siren-pass`, `helicopter` | `police-radio-beep`, `purge-siren`, `999-credit-score-siren`, `hells-kitchen-suspense` | zoom |
| Busted | `car-door-slam` | `record-scratch` → `cat-laughing-at-you` / `crowd-laugh` / `you-stupid-men` | `bw` + caption |
| Heist / money | `register-open`, `coins-handful` | `cash-register-1` … `cash-register-5`, `cash-register`, `mario-coin`, `sonic-ring`, `collect-item` | small zoom 0.08–0.12 |
| Stunt / clutch escape | `riser-air` (align `end`) or `whoosh-fast` on the jump | `build-up` before; `vine-boom-slowed`, `cinematic-boom`, `cinematic-hit` or `boom` on landing; `crowd-cheer` / `kids-yeyy` after | zoom + flash, slow segment |
| Sigma / cold walk-away | `footsteps-concrete` | `i-have-no-enemies`, `berserk-skeleton`, `skeleton-in-hell`, `undertaker-bell`, `da-bells-1`…`3`, `tiktok-mentality`, `they-dont-know-me-son`, `we-do-not-care` | `bw`, slow segment |
| Fail / missed jump | `body-drop` | `bua-wa-wa-wa-wa`, `long-brain-fart`, `lie-detector`, `wrong-answer`, `tone-down`, `faahhhh`, `bruhh`, `nope`, `disappointed` | zoom on the face/car |
| Win / perfect move | `coins-handful` | `correct-answer`, `tone-up`, `game-point`, `anime-wow`, `anime-discovery`, `angel`, `party-horn` | small zoom |
| Awkward NPC moment | the bed only | `awkward-pause`, `blinking`, `question-sound`, `confused-reverb`, `among-us` | none, let it breathe |
| Rizz / Lucia–Jason moment | — | `eye-wink`, `rizz-tiktok`, `rizzz` | small zoom |
| Sad ending | the bed fades | `sad-hamster-violin`, `rude-eternal-youth`, `kanye-wolves`, `strawberry-guy`, `iranian-sadness-batman` | `bw`, slow segment |
| Flashback / "earlier that day" | `whoosh-sweep` | `tape-rewind`, `flashback`, `record-scratch` | caption |
| Scene cut | `whoosh-sweep` (peak on the cut), `whoosh-fast` | `cartoon-transition`, `dbz-teleport`, `whoosh`, `whoosh-2`, `whoosh-fire-transition`, `in-and-out`, `glitch`, `camera-shutter` | flash |
| Phone / message | `phone-ring`, `phone-vibrate` | `iphone-receive`, `discord-call`, `apple-notification`, `message-sound`, `arabic-nokia` | — |
| Hook / intro | `deep-boom` | `netflix-intro-meme`, `ps2-startup`, `windows-startup`, `writing-with-fire` | caption |

## 2. Placement and mix rules

- **Align by what matters** (`align` on a cue):
  - `peak` for hits whose loudest moment comes after their start: crashes, the cash register's "ching", `bone-crack`, whooshes, `vine-boom-slowed`. The loudest moment then lands on `t`. `peak_s` in `library.json` tells you where that moment is.
  - `end` for risers and build-ups: the sound finishes on the hit.
  - `start` for voice lines, music stabs, gunshots and explosions. An explosion's rumble is louder than its blast, so `peak` would put the blast too early.
- **`t` is the contact frame**: the frame where the car touches the wall or the player lands. Being 1–2 frames early feels snappy; being late feels broken.
- **The stop before the hit** (`"stop": 0.15–0.5`): drop the game audio and beds to near-silence just before a big hit. It's the move that makes a vine boom land. Use it on 1–2 moments per reel.
- **Ducking**: duck (`duck: true`, −9 dB) under voice lines and music stabs. For short impacts, use a stop or nothing (`duck: false`): ducking under every hit makes the mix pump.
- **Layering**: put realism and joke cues at the same `t`; the checker treats cues within 50 ms as one event. Keep the realism layer 3–6 dB under the joke.
- **Levels**: every library sound peaks at −1 dBFS, so loudness differs by kind. Starting points for `gain_db`: impacts and stabs 0 to −4, music stabs −4 to −8 (with `max_len` 1.5–4), voice lines −2 to −6, transitions −6 to −10, earshot foley under a meme −3 to −6, beds −18 to −24. A featured hit should stand ≥ 10 dB over what played before it.
- **Spacing**: one featured sound every 2–4 s in a 15–30 s reel. Transitions don't count. Don't start a featured sound while a long music stab is still playing; cut the stab with `max_len`.
- **The hook**: something lands in the first 1.5 s. A cold-open of the payoff, then `tape-rewind` to the setup, works well.
- **Effects stay on the beat**: zoom, shake and flash only on impacts; `bw` for the aftermath. Captions: ≤ 6 words, plain text (no emoji), 1.2–2 s; they wrap into balanced lines.
- **Length**: Reels/TikTok 10–30 s, Shorts < 60 s. Cut dead time with several `segments`; slow-mo with `speed` 0.4–0.6 around the money shot.

### Copyright: say it once

- **Music clips:** sounds tagged `music` are clips of commercial songs (Gangnam Style, Rocky, Oppenheimer, Stayin' Alive, Super Idol…). TikTok, Instagram and YouTube can mute, demonetise or block reels that use them. Keep them short (`max_len`), and say so when you use one.
- **GTA's own audio:** the in-game radio plays licensed songs. Prefer segments without radio, or lower `game_volume` under a bed.
- **Safe mode** (monetised or brand uploads): pick with `list_sounds.py --no-music --no-explicit`. `earshot` sounds are free for commercial use, and TechKeyFi describes its packs as copyright-free.
- **Explicit sounds:** sounds tagged `explicit` only when the user asks for that tone.

## 3. The edit plan

```json
{
  "output": "gta6_reel.mp4",
  "format": "vertical", "fit": "blur", "fps": 30, "sfx_dir": "<absolute path of $LIB>",
  "game_volume": 1.0, "duck_db": -9, "loudness": -14,
  "segments": [
    {"file": "clip.mp4", "in": 41.2, "out": 46.0},
    {"file": "clip.mp4", "in": 46.0, "out": 47.5, "speed": 0.5}
  ],
  "beds": [{"sfx": "bed-city-street", "from": 0, "to": 7.8, "gain_db": -22, "loop": true}],
  "cues": [
    {"t": 0.2, "sfx": "netflix-intro-meme", "gain_db": -6, "max_len": 1.2, "kind": "music", "caption": "GTA 6 PHYSICS"},
    {"t": 3.0, "sfx": "riser-air", "align": "end", "gain_db": -8, "duck": false, "kind": "riser"},
    {"t": 3.0, "sfx": "car-crash-real", "align": "peak", "gain_db": -5, "stop": 0.3},
    {"t": 3.0, "sfx": "metal-pipe-falling", "max_len": 1.8, "fx": ["zoom", "shake", "flash"], "caption": "HE REALLY TRIED IT"},
    {"t": 5.6, "sfx": "bone-crack", "align": "peak", "fx": ["bw"], "bw_dur": 1.6, "caption": "WASTED"}
  ]
}
```

- **Times**: `t` (and a bed's `from`/`to`) are on the final edited timeline. Add up the earlier segments, each `(out − in) / speed`.
- **`sfx`** is a library id (or a file path). A wrong id stops the render and suggests the nearest ids.
- **`kind`**: `hit` by default. `music` and `voice` are judged within 150 ms (slow attacks). `whoosh`, `riser`, `transition`, `ui` and `bed` are supporting sounds, not held to the stand-out or spacing rules.
- **`fx`**: `zoom` (strength `zoom`, 0.18), `shake`, `flash`, `bw` (`bw_dur`); `fx_dur` is how long zoom/shake last. `max_len` cuts a sound short.
- **Frame**: `fit` is `blur` (whole frame over a blurred fill) or `crop`; `format` is `vertical`, `square` or `landscape`.
- **Beds**: `loop`, `in`, `fade`, `duck`. A music track can be a bed too.

## 4. Render and check

```bash
python3 $S/render_reel.py plan.json --preview     # fast 540p look -> *_preview.mp4 (+ .cues.json)
python3 $S/check_reel.py gta6_reel_preview.mp4    # sync, stand-out, spacing, hook, loudness + sheet.png
python3 $S/render_reel.py plan.json               # final: 1080x1920 H.264, AAC 192k, two-pass -14 LUFS, true peak < -1
python3 $S/check_reel.py gta6_reel.mp4
```

The render prints where each sound actually starts after alignment.

`check_reel.py` treats cues at the same moment as one event and flags:
- **`off sync`**: the hit is more than 2 frames from `t` (150 ms for music/voice). Usually a wrong `align`.
- **`masked`**: it stands out less than 4 dB over what played before it began. Raise `gain_db`, add a `stop`, or move it away from a long sound.
- **Pile-ups** under 0.9 s apart, **no hook** in the first 1.5 s, loudness off −14 ± 1 LUFS, and true peak above −1 dBFS.

It writes `sheet.png`: one frame per event with its verdict, over the waveform. **Open it**: is each caption readable, and is the flash on the impact frame? Fix, re-render, re-check, one change at a time.

## 5. Adding sounds

- **Another compilation video** (names shown on screen, like Warrior SFX), or a complete copy of Warrior #1:
  ```bash
  python3 $S/extract_compilation.py detect video.mp4 --box 0.74 0.90     # name strip as fractions of the frame
  # open video.mp4.names.png, fill video.mp4.names.txt: one line per segment, Name|tags, skip or merge
  python3 $S/extract_compilation.py cut video.mp4 video.mp4.names.txt "$LIB" --pack mypack --title "Channel - title"
  ```
  - **The name strip:** for TechKeyFi-style videos ("Sound N" over the name) use `--box 0.20 0.38 0.3 0.7 --thresh 4`.
  - **Missed names:** if names that differ by one digit were missed, lower `--thresh`.
  - **What it handles:** muted stretches are skipped and listed in `missing.json`, and a re-cut replaces that pack.
- **A folder of loose files** (a downloaded pack): `python3 $S/index_folder.py "Pack folder" "$LIB" --pack name --merge`. Tags are guessed from filenames, so check them.
- **More realistic sounds**: earshot (section 7) → `python3 $S/index_folder.py earshot_out "$LIB" --pack earshot2 --merge`.
- **Saving changes**: after adding sounds, offer to commit and push the updated library to the user's GitHub repo (`mr-zito/gta-reel-sound-studio`, path `skills/gta-reel-sound-studio/gta_sfx_library`), so every install gets them.

## 6. Deliver

- Save the final mp4 next to the user's clip and give its path. In a chat app, send it as a file.
- Give a compact cue sheet: time · sounds (realism + joke) · effect · caption.
- Add the QA line: LUFS, true peak, and "all N cues on sync", or what's left.
- Name any `music` clips used, and whether a safe-mode version is available.
- Offer one specific alternative ("want `lego-breaking` instead of `metal-pipe-falling` on the crash?").

If the user edits in CapCut, Premiere or DaVinci and wants the pieces, send the `sfx/*.flac` used plus the cue sheet with the *sound start* times that render_reel.py prints.

## 7. earshot (optional: more realistic sounds)

The library's `earshot` pack covers common GTA foley. For anything else (a specific car, rain on a roof, a boat horn), earshot generates it from public-domain recordings:
```bash
pip install "earshot @ git+https://github.com/Leonxlnx/earshot"     # not the PyPI 'earshot'
earshot sounds --search "boat horn"                                # find the design id
earshot make --spec spec.json -o earshot_out                        # {"sounds":[{"name":"ship-horn","sound":"ship_horn/blast"}]}
```

Read each answer line:
- Anything other than `clean` means remake it with another `"seed"`.
- `also (the pick is a guess…)` means the pick may be wrong: re-ask with `"sound": "<id>"`.
- `earshot makes no X` means the file is a stand-in. Don't present it as the thing.

The optional listen extra (`earshot[listen]`, ~1.1 GB of models) adds `earshot match`/`find`/`timeline`. You can't hear, so never say how a sound sounds without such a reading, and quote its number when you do.
