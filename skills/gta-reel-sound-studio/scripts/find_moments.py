#!/usr/bin/env python3
"""Find candidate edit points in a gameplay clip and grab a frame at each.

usage: find_moments.py clip.mp4 OUT_DIR [--max 25] [--scene 0.35] [--jump 9]

Detects (1) audio spikes - gunshots, crashes, explosions, impacts - as sudden
jumps above the clip's rolling loudness, and (2) hard visual cuts (scene
changes, e.g. the WASTED/BUSTED screen, cutscenes, fast camera switches).
Writes OUT_DIR/moments.json and OUT_DIR/frames/mXX_<time>.jpg so each moment
can be looked at before choosing a sound.
"""
import argparse, json, re, subprocess
from pathlib import Path
import numpy as np

SR = 8000
HOP = 0.05  # seconds per loudness window


def loudness_track(clip):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", clip, "-vn", "-ac", "1",
                          "-ar", str(SR), "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    n = int(SR * HOP)
    if len(x) < n:
        return np.array([])
    x = x[: len(x) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((x ** 2).mean(axis=1)) + 1e-6)


def audio_spikes(db, jump):
    if len(db) == 0:
        return []
    win = int(2.0 / HOP)
    pad = np.pad(db, (win, 0), mode="edge")
    base = np.array([np.median(pad[i:i + win]) for i in range(len(db))])
    rise = db - base
    hits = []
    for i in np.argsort(-rise):
        t = i * HOP
        if rise[i] < jump or db[i] < -40:
            break
        j = i  # walk back to the onset so the sound lands on the first frame of the hit
        while j > 0 and rise[j - 1] > jump / 2 and i - j < int(0.5 / HOP):
            j -= 1
        t = j * HOP
        if all(abs(t - h["t"]) > 0.6 for h in hits):
            hits.append({"t": round(t, 2), "kind": "audio_spike", "score": round(float(rise[i]), 1),
                         "level_db": round(float(db[i]), 1)})
    return hits


def scene_cuts(clip, thresh):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", clip, "-an", "-vf",
                        f"select='gt(scene,{thresh})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True)
    cuts = []
    for m in re.finditer(r"pts_time:([\d.]+)", r.stderr):
        cuts.append({"t": round(float(m.group(1)), 2), "kind": "scene_cut", "score": thresh})
    return cuts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip"); ap.add_argument("out_dir")
    ap.add_argument("--max", type=int, default=25)
    ap.add_argument("--scene", type=float, default=0.35)
    ap.add_argument("--jump", type=float, default=9.0, help="dB above rolling median that counts as a spike")
    a = ap.parse_args()
    out = Path(a.out_dir); (out / "frames").mkdir(parents=True, exist_ok=True)

    db = loudness_track(a.clip)
    moments = audio_spikes(db, a.jump)[: a.max] + scene_cuts(a.clip, a.scene)[: a.max]
    moments.sort(key=lambda m: m["t"])
    for i, m in enumerate(moments):
        f = out / "frames" / f"m{i:02d}_{m['t']:.2f}s.jpg"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(m["t"]), "-i", a.clip,
                        "-frames:v", "1", "-vf", "scale=480:-2", str(f)])
        m["frame"] = str(f)
    (out / "moments.json").write_text(json.dumps(moments, indent=1))
    for m in moments:
        print(f"{m['t']:7.2f}s  {m['kind']:11s}  score={m['score']}")
    print(f"{len(moments)} moments -> {out}/moments.json")


if __name__ == "__main__":
    main()
