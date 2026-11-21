#!/usr/bin/env python3
"""Render a sound-designed reel from a JSON edit plan.

usage: render_reel.py plan.json [--preview]

Plan (all cue / bed times are on the FINAL edited timeline, in seconds):
{
  "output": "reel.mp4",
  "format": "vertical",            # vertical 1080x1920 | square 1080x1080 | landscape 1920x1080
  "fit": "blur",                   # blur = whole frame over a blurred fill, crop = fill the frame
  "fps": 30,
  "sfx_dir": "gta_sfx_library",    # library folder (library.json ids); a cue "sfx" may also be a path
  "game_volume": 1.0,
  "duck_db": -9,                   # how far game audio + beds dip under a ducking cue
  "loudness": -14,                 # integrated LUFS (TikTok / Reels / Shorts)
  "segments": [{"file": "clip.mp4", "in": 4.0, "out": 11.5, "speed": 1.0}],
  "beds": [{"sfx": "city", "from": 0, "to": 12, "gain_db": -20, "loop": true, "duck": true}],
  "cues": [
    {"t": 3.2, "sfx": "vine-boom-slowed", "align": "peak", "gain_db": 0, "duck": true, "stop": 0.3,
     "fx": ["zoom", "shake", "flash", "bw"], "fx_dur": 0.6, "zoom": 0.18,
     "caption": "bro thought he was safe", "caption_dur": 1.5, "kind": "hit"}
    kind: hit (default) | music | voice (sync judged within 150 ms: slow attacks) |
          whoosh | riser | transition | ui | bed (supporting: not held to stand-out or spacing rules)
  ]
}
align: start (the file starts at t), peak (its loudest moment lands on t: hits, whooshes),
       end (it finishes on t: risers, build-ups).
stop:  seconds of near-silence of game audio and beds just before t (the "stop before the hit").
Writes OUT and OUT.cues.json (earshot's cue format, for `earshot timeline OUT --cues ...`).
--preview renders 540 wide, ultrafast, for a quick look.
"""
import json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

SIZES = {"vertical": (1080, 1920), "square": (1080, 1080), "landscape": (1920, 1080)}
FONT_CANDIDATES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                   "/System/Library/Fonts/Supplemental/Impact.ttf", "C:/Windows/Fonts/impact.ttf",
                   "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg failed:\n" + r.stderr[-3000:])
    return r


def probe(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error"] + (["-select_streams", stream] if stream else [])
    cmd += ["-show_entries", entries, "-of", "csv=p=0", str(path)]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def has_audio(path):
    return bool(probe(path, "stream=index", "a"))


def dur(path):
    return float(probe(path, "format=duration") or 0)


def peak_time(path):
    """Time of the loudest 10 ms in a sound file (decoded by ffmpeg, any format)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.abs(np.frombuffer(raw, dtype=np.int16).astype(np.float32))
    if len(x) < 80:
        return 0.0
    x = x[: len(x) // 80 * 80].reshape(-1, 80).mean(axis=1)
    return float(np.argmax(x)) * 0.01


def fesc(p):
    """A file path inside an ffmpeg filter option: forward slashes, and the colon of C:/... escaped (Windows)."""
    return str(p).replace("\\", "/").replace(":", "\\:")


def windows(ranges):
    """ffmpeg expression that is 1 inside any (a, b) window, else 0."""
    if not ranges:
        return "0"
    return "min(1," + "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in ranges) + ")"


def build_base(plan, W, H, fps, tmp):
    """Pass 1: trim / speed / reframe every segment and join them."""
    inputs, chains, labels = [], [], []
    for i, s in enumerate(plan["segments"]):
        src = s["file"]; spd = float(s.get("speed", 1.0))
        tin = float(s.get("in", 0)); tout = float(s.get("out", dur(src)))
        inputs += ["-i", src]
        v = f"[{i}:v]trim={tin}:{tout},setpts=(PTS-STARTPTS)/{spd},fps={fps}"
        if plan.get("fit", "blur") == "crop":
            v += f",scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[v{i}]"
        else:
            v += (f",split[a{i}][b{i}];[a{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"boxblur=30:2,eq=brightness=-0.08[bg{i}];[b{i}]scale={W}:{H}:force_original_aspect_ratio=decrease[fg{i}];"
                  f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,setsar=1[v{i}]")
        chains.append(v)
        seg_len = (tout - tin) / spd
        if has_audio(src):
            at, rest = [], spd
            while rest > 2.0: at.append("atempo=2.0"); rest /= 2.0
            while rest < 0.5: at.append("atempo=0.5"); rest /= 0.5
            at.append(f"atempo={rest:.4f}")
            chains.append(f"[{i}:a]atrim={tin}:{tout},asetpts=PTS-STARTPTS,{','.join(at)},"
                          f"aresample=48000,aformat=channel_layouts=stereo[s{i}]")
        else:
            chains.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{seg_len:.3f}[s{i}]")
        labels.append(f"[v{i}][s{i}]")
    n = len(plan["segments"])
    graph = ";".join(chains) + ";" + "".join(labels) + f"concat=n={n}:v=1:a=1[v][a]"
    base = Path(tmp) / "base.mov"
    gfile = Path(tmp) / "pass1.txt"; gfile.write_text(graph)
    run(["ffmpeg", "-y", "-hide_banner", *inputs, "-filter_complex_script", str(gfile), "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(base)])
    return base


_LIB = {}


def resolve_sfx(name, sfx_dir):
    """A cue's sound: a library id (sfx_dir/library.json), a file in sfx_dir, or a path."""
    root = Path(sfx_dir)
    if root not in _LIB:
        lj = root / "library.json"
        _LIB[root] = {e["id"]: e for e in json.loads(lj.read_text())} if lj.exists() else {}
    if name in _LIB[root]:
        return root / _LIB[root][name]["file"]
    cands = [Path(name), root / name] + [d / f"{name}{ext}" for d in (root, root / "sfx")
                                         for ext in (".flac", ".wav", ".mp3", ".ogg", ".m4a")]
    for cand in cands:
        if cand.is_file():
            return cand
    import difflib
    near = difflib.get_close_matches(name, list(_LIB[root]), n=5, cutoff=0.5)
    sys.exit(f"sound not found: {name} (in {sfx_dir})" + (f"; did you mean: {', '.join(near)}" if near else ""))


def caption_filter(c, i, tmp, W, font):
    words = c["caption"].upper().split()
    text = " ".join(words)
    n_lines = max(1, -(-len(text) // 16))                 # ~16 characters a line keeps captions inside the frame
    width = max(max(len(w) for w in words), -(-len(text) // n_lines))  # balanced lines: no lone last word
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    fs = int(min(W * 0.085, (W * 0.9) / (0.62 * max(max(len(l) for l in lines), 1))))
    tf = Path(tmp) / f"cap{i}.txt"; tf.write_text("\n".join(lines))
    t = float(c["t"]); e = t + float(c.get("caption_dur", 1.5))
    return (f"drawtext=fontfile='{fesc(font)}':textfile='{fesc(tf)}':fontsize={fs}:fontcolor=white:borderw={max(3, fs // 11)}"
            f":bordercolor=black:line_spacing={fs // 5}:text_align=C:x=(w-text_w)/2:y=h*0.68"
            f":enable='between(t,{t:.3f},{e:.3f})'")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    preview = "--preview" in sys.argv
    plan = json.loads(Path(sys.argv[1]).read_text())
    W, H = SIZES[plan.get("format", "vertical")]
    fps = int(plan.get("fps", 30))
    sfx_dir = plan.get("sfx_dir", "gta_sfx_library")
    cues = sorted(plan.get("cues", []), key=lambda c: c["t"])
    font = next((f for f in FONT_CANDIDATES if Path(f).exists()), None)

    with tempfile.TemporaryDirectory() as tmp:
        base = build_base(plan, W, H, fps, tmp)
        total = dur(base)

        # ---------- picture effects ----------
        zoom_terms, shake, flash1, flash2, bw, vf = [], [], [], [], [], []
        for c in cues:
            t, d = float(c["t"]), float(c.get("fx_dur", 0.6))
            fx = c.get("fx", [])
            if "zoom" in fx:  # punch in on the hit, ease back out
                z = float(c.get("zoom", 0.18))
                zoom_terms.append(f"{z}*between(it,{t:.3f},{t + d:.3f})*exp(-(it-{t:.3f})*{4.0 / d:.3f})")
            if "shake" in fx: shake.append((t, t + min(d, 0.5)))
            if "flash" in fx: flash1.append((t, t + 0.06)); flash2.append((t + 0.06, t + 0.14))
            if "bw" in fx: bw.append((t, t + float(c.get("bw_dur", d))))
        if zoom_terms:
            vf.append(f"zoompan=z='1+min(0.6,{'+'.join(zoom_terms)})':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'"
                      f":d=1:s={W}x{H}:fps={fps}")
        if shake:
            m, on = 40, windows(shake)
            vf.append(f"scale={W + 2 * m}:{H + 2 * m},crop={W}:{H}:x='{m}+{m * 0.8}*sin(t*83)*{on}'"
                      f":y='{m}+{m * 0.8}*cos(t*71)*{on}'")
        if bw:
            vf.append(f"hue=s=0:enable='{windows(bw)}'")
        if flash1:
            vf.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.85:t=fill:enable='{windows(flash1)}'")
            vf.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.35:t=fill:enable='{windows(flash2)}'")
        for i, c in enumerate(cues):
            if c.get("caption") and font:
                vf.append(caption_filter(c, i, tmp, W, font))
        if preview:
            vf.append("scale=540:-2")
        vchain = "[0:v]" + (",".join(vf) if vf else "null") + "[vout]"

        # ---------- sounds on the timeline ----------
        inputs, achains, mix, duck, stops, sheet = ["-i", str(base)], [], [], [], [], []
        k = 0
        for c in cues:
            path = resolve_sfx(c["sfx"], sfx_dir)
            L_full = dur(path)
            L = min(L_full, float(c.get("max_len", 8.0)))
            align = c.get("align", "start")
            off = {"start": 0.0, "peak": peak_time(path), "end": L}[align]
            t = float(c["t"]); start = t - off; head = 0.0
            if start < 0:  # the sound would begin before the reel: cut its head instead
                head, start = -start, 0.0
            k += 1
            inputs += ["-i", str(path)]
            achains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,atrim={head:.3f}:{L:.3f},"
                           f"asetpts=PTS-STARTPTS,volume={float(c.get('gain_db', 0))}dB,"
                           f"adelay={int(start * 1000)}:all=1[x{k}]")
            mix.append(f"[x{k}]")
            if c.get("duck", True):
                duck.append((start, start + L - head))
            if c.get("stop"):
                stops.append((max(0.0, t - float(c["stop"])), t))
            sheet.append({"t": round(t, 3), "starts": round(start, 3), "align": align, "sfx": str(path.name),
                          "kind": c.get("kind", "hit"), "len": round(L - head, 3), "gain_db": c.get("gain_db", 0),
                          "fx": c.get("fx", []), "caption": c.get("caption", "")})

        dip = 10 ** (float(plan.get("duck_db", -9)) / 20)
        level = f"(1-{1 - dip:.3f}*{windows(duck)})*(1-0.97*{windows(stops)})"
        gv = float(plan.get("game_volume", 1.0))
        game = f"[0:a]volume='{gv}*{level}':eval=frame[g]"
        for b in plan.get("beds", []):
            path = resolve_sfx(b["sfx"], sfx_dir)
            b0 = float(b.get("from", 0)); b1 = float(b.get("to", total)); span = max(0.1, b1 - b0)
            k += 1
            inputs += (["-stream_loop", "-1"] if b.get("loop", True) else []) + ["-i", str(path)]
            fade = min(float(b.get("fade", 0.4)), span / 3)
            lv = level if b.get("duck", True) else "1"
            achains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,atrim={float(b.get('in', 0)):.3f}:"
                           f"{float(b.get('in', 0)) + span:.3f},asetpts=PTS-STARTPTS,volume={float(b.get('gain_db', -18))}dB,"
                           f"afade=t=in:d={fade:.2f},afade=t=out:st={span - fade:.3f}:d={fade:.2f},"
                           f"adelay={int(b0 * 1000)}:all=1,volume='{lv}':eval=frame[x{k}]")
            mix.append(f"[x{k}]")
        lufs = plan.get("loudness", -14)
        tail = f"[g]{''.join(mix)}amix=inputs={len(mix) + 1}:normalize=0:duration=first[aout]"
        graph = ";".join([vchain, game, *achains, tail])
        gfile = Path(tmp) / "pass2.txt"; gfile.write_text(graph)
        out = Path(plan.get("output", "reel.mp4"))
        if preview:
            out = out.with_name(out.stem + "_preview" + out.suffix)
        mixed = Path(tmp) / "mixed.mov"
        run(["ffmpeg", "-y", "-hide_banner", *inputs, "-filter_complex_script", str(gfile),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
             "-c:v", "libx264", "-preset", "ultrafast" if preview else "veryfast", "-crf", "28" if preview else "18",
             "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "pcm_s24le", str(mixed)])
        # two-pass loudness: measure the mix, then apply one linear gain (+ true-peak limit) to hit the target
        ln = f"loudnorm=I={lufs}:TP=-2:LRA=11"
        r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(mixed), "-vn", "-af", ln + ":print_format=json",
                 "-f", "null", "-"]).stderr
        m = json.loads(r[r.rfind("{"):r.rfind("}") + 1])
        ln2 = (f"{ln}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
               f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=48000,"
               f"alimiter=limit=0.75:level=0:attack=1:release=40")  # keeps true peak under -1 dBFS after AAC
        run(["ffmpeg", "-y", "-hide_banner", "-i", str(mixed), "-c:v", "copy", "-af", ln2,
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])

    # cue sheet: ours for check_reel.py, and earshot's picture-cue format for `earshot timeline --cues`
    es = {"fps": fps, "total": round(total * fps),
          "events": [{"f": round(s["t"] * fps, 2), "kind": s["kind"], "weight": 1,
                      "id": f"reel:{s['kind']}:{n}"} for n, s in enumerate(sheet)]}
    Path(str(out) + ".cues.json").write_text(json.dumps({**es, "sheet": sheet}, indent=1))
    print(f"rendered {out}  ({total:.1f}s, {len(cues)} cues, {len(plan.get('beds', []))} beds); cues -> {out}.cues.json")
    for s in sheet:
        print(f"  {s['t']:6.2f}s  {s['sfx']:34s} {s['align']:5s} starts {s['starts']:6.2f}s  {s['gain_db']:+} dB")


if __name__ == "__main__":
    main()
