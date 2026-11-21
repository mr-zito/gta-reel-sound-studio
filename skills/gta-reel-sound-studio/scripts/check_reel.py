#!/usr/bin/env python3
"""Check a rendered reel without ears: loudness, true peak, whether every cue landed on time and
stands out of the mix, spacing between featured sounds, plus a review sheet to look at.

usage: check_reel.py reel.mp4 [--out qa_dir]

Reads reel.mp4.cues.json (written by render_reel.py). Writes qa_dir/qa.json and qa_dir/sheet.png:
one frame per cue (time, sound, sync offset) above the reel's waveform with the cues marked.
Exit code 1 if anything failed.
"""
import json, re, shutil, subprocess, sys
from pathlib import Path
import numpy as np

SR, HOP = 8000, 0.005  # 5 ms envelope
FONT = next((f for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                         "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
             if Path(f).exists()), None)
QUIET_KINDS = {"whoosh", "transition", "riser", "ui", "bed"}


def envelope(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    n = int(SR * HOP)
    x = x[: len(x) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((x ** 2).mean(axis=1)) + 1e-6)


def loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = r[r.rfind("Summary:"):]
    g = lambda pat: float(re.search(pat, summary, re.S).group(1)) if re.search(pat, summary, re.S) else None
    return {"lufs": g(r"I:\s+(-?[\d.]+) LUFS"), "lra": g(r"LRA:\s+(-?[\d.]+) LU"),
            "true_peak_dbfs": g(r"True peak:.*?Peak:\s+(-?[\d.]+) dBFS")}


def fesc(p):
    """A file path inside an ffmpeg filter option: forward slashes, and the colon of C:/... escaped (Windows)."""
    return str(p).replace("\\", "/").replace(":", "\\:")


def seg(env, a, b):
    i0, i1 = max(0, int(a / HOP)), max(int(a / HOP) + 1, int(b / HOP))
    return env[i0:i1]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    reel = Path(sys.argv[1])
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else reel.with_suffix("").with_name(reel.stem + "_qa")
    out.mkdir(parents=True, exist_ok=True)
    cues = json.loads(Path(str(reel) + ".cues.json").read_text())
    sheet, fps = cues["sheet"], cues["fps"]
    env = envelope(reel)
    total = len(env) * HOP
    issues, rows = [], []

    lv = loudness(reel)
    if lv["lufs"] is None or abs(lv["lufs"] - (-14)) > 1.0:
        issues.append(f"loudness {lv['lufs']} LUFS, want -14 +-1")
    if lv["true_peak_dbfs"] is not None and lv["true_peak_dbfs"] > -1.0:
        issues.append(f"true peak {lv['true_peak_dbfs']} dBFS, want <= -1")

    # cues within 50 ms of each other are one event (a layered hit); judge each event at its planned moment t:
    # start-aligned -> the steepest rise should be at t, peak-aligned -> the loudest point, end-aligned -> skip
    events = []
    for s in sheet:
        if events and abs(s["t"] - events[-1][0]["t"]) <= 0.05:
            events[-1].append(s)
        else:
            events.append([s])
    frame_ms = 1000 / fps
    smooth = np.convolve(env, np.ones(4) / 4, mode="same")  # 20 ms: game noise must not read as a hit
    for ev in events:
        t = ev[0]["t"]
        prim = next((c for c in ev if c["align"] != "end" and c["kind"] not in QUIET_KINDS),
                    next((c for c in ev if c["align"] != "end"), ev[0]))
        # "before" = what played before this sound began (a peak-aligned sound's own lead-in doesn't count)
        b1 = min(t - 0.15, prim["starts"] - 0.02)
        bed_seg = seg(env, max(0, b1 - 0.45), max(b1, 0.005))
        bed = float(np.median(bed_seg)) if len(bed_seg) else -90.0
        look = seg(env, t, t + 0.2)
        stand_out = float(np.max(look) - bed) if len(look) else 0.0
        i0 = max(0, int((t - 0.12) / HOP))
        w = smooth[i0:int((t + 0.2) / HOP) + 1]
        if prim["align"] == "peak":  # the loudest moment should sit on t
            idx = int(np.argmax(w)) if len(w) else None
        else:  # the first moment 6 dB over what played before should sit on t
            over = np.nonzero(w > bed + 6)[0]
            idx = int(over[0]) if len(over) else None
        offset_ms = None if idx is None else round((i0 + idx) * HOP * 1000 - t * 1000)
        names = " + ".join(c["sfx"] for c in ev)
        row = {"t": t, "sfx": names, "align": prim["align"], "kind": prim["kind"], "onset_ms": offset_ms,
               "stands_out_db": round(stand_out, 1)}
        if prim["align"] == "end":
            row["verdict"] = "ok (riser)"
        elif stand_out < 4 and prim["kind"] not in QUIET_KINDS:
            row["verdict"] = "masked"
            issues.append(f"{t:.2f}s {names}: only {stand_out:.1f} dB over what plays before it in the 200 ms after t - buried (raise gain_db, duck, add a stop) or starting late (leading silence: re-trim)")
        elif offset_ms is None or abs(offset_ms) > (150 if prim["kind"] in ("music", "voice") else 2 * frame_ms):
            row["verdict"] = "off sync"
            where = "no clear onset near t" if offset_ms is None else f"the hit lands {offset_ms:+} ms from plan"
            issues.append(f"{t:.2f}s {names}: {where} (trim silence, change align, or add a stop so it stands out)")
        else:
            row["verdict"] = "ok"
        rows.append(row)

    featured = [ev[0] for ev in events if any(c["kind"] not in QUIET_KINDS for c in ev)]
    for a, b in zip(featured, featured[1:]):
        if b["t"] - a["t"] < 0.9:
            issues.append(f"{a['t']:.2f}s -> {b['t']:.2f}s: featured sounds {b['t'] - a['t']:.2f}s apart (pile-up; aim 2-4 s)")
    if featured and featured[0]["t"] > 1.5:
        issues.append(f"first featured sound at {featured[0]['t']:.2f}s - the hook needs something in the first 1.5 s")

    # review sheet: one frame per cue over the waveform with cue lines
    tiles = []
    for i, (ev, r) in enumerate(zip(events, rows)):
        s = ev[0]
        tile = out / f"cue{i:02d}.png"
        lab = out / f"cue{i:02d}.txt"
        lab.write_text(f"{s['t']:.2f}s  {r['verdict']}\n{r['sfx'][:30]}\n"
                       f"{'' if r['onset_ms'] is None else str(r['onset_ms']) + ' ms, '}+{r['stands_out_db']} dB")
        dt = (f",drawtext=fontfile='{fesc(FONT)}':textfile='{fesc(lab)}':fontsize=14:line_spacing=3:fontcolor=white"
              f":box=1:boxcolor=black@0.75:boxborderw=5:x=6:y=6" if FONT else "")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s['t'] + 0.03:.3f}", "-i", str(reel), "-frames:v", "1",
                        "-vf", f"scale=240:-2{dt}", str(tile)])
        if tile.exists():
            tiles.append(tile)
    wave = out / "wave.png"
    width = max(240 * min(len(tiles), 6), 960)
    marks = ",".join(f"drawbox=x={int(s['t'] / total * width)}:y=0:w=2:h=ih:color=red@0.9:t=fill" for s in sheet) or "null"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(reel), "-filter_complex",
                    f"[0:a]aformat=channel_layouts=mono,showwavespic=s={width}x160:colors=white:scale=sqrt,{marks}[w]",
                    "-map", "[w]", "-frames:v", "1", str(wave)])
    png = out / "sheet.png"
    if tiles:
        rowsz = [tiles[i:i + 6] for i in range(0, len(tiles), 6)]
        parts, n = [], 0
        cmd = ["ffmpeg", "-y", "-v", "error"]
        for r_ in rowsz:
            for t_ in r_:
                cmd += ["-i", str(t_)]
        cmd += ["-i", str(wave)]
        fc, rows_lbl = [], []
        for ri, r_ in enumerate(rowsz):
            ins = "".join(f"[{n + j}:v]" for j in range(len(r_)))
            n += len(r_)
            fc.append(f"{ins}hstack=inputs={len(r_)}[r{ri}]" if len(r_) > 1 else f"{ins}null[r{ri}]")
            fc.append(f"[r{ri}]pad={width}:ih:0:0:black[p{ri}]")
            rows_lbl.append(f"[p{ri}]")
        fc.append(f"{''.join(rows_lbl)}[{n}:v]vstack=inputs={len(rows_lbl) + 1}[o]")
        subprocess.run(cmd + ["-filter_complex", ";".join(fc), "-map", "[o]", "-frames:v", "1", str(png)])
        for t_ in tiles:
            t_.unlink()
        for f_ in out.glob("cue*.txt"):
            f_.unlink()

    report = {"reel": str(reel), "duration": round(total, 2), **lv, "cues": rows, "issues": issues,
              "sheet": str(png) if png.exists() else None}
    (out / "qa.json").write_text(json.dumps(report, indent=1))
    print(f"loudness {lv['lufs']} LUFS, true peak {lv['true_peak_dbfs']} dBFS, LRA {lv['lra']} LU")
    for r in rows:
        print(f"  {r['t']:6.2f}s  {r['sfx']:32s} {r['verdict']:9s} onset {r['onset_ms']} ms  +{r['stands_out_db']} dB")
    print("issues:" if issues else "no issues", *("  - " + i for i in issues), sep="\n")
    print(f"sheet: {png}")
    if shutil.which("earshot"):
        print(f"earshot found: for a listening pass run  earshot timeline {reel} --cues {reel}.cues.json  "
              f"and  earshot sheet {reel} -o {out}/earshot_sheet.png --cues {reel}.cues.json  (needs the listen extra)")
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
