#!/usr/bin/env python3
"""Add an SFX compilation video (one sound after another, its name shown on screen) to the library.

Step 1  detect: find where the on-screen name changes and make a sheet to read the names from.
  extract_compilation.py detect VIDEO --box Y0 Y1 [X0 X1] [--thresh 2.5]
  -> VIDEO.segments.json, VIDEO.names.png (one labelled crop per segment: open it and read the names),
     VIDEO.names.txt (one line per segment to fill in)
  --box is the name strip as fractions of the frame (e.g. 0.74 0.90 for text under a centred icon).
  Lower --thresh if names that differ by one digit ("Cash Register 1" -> "2") were missed.

Step 2  fill VIDEO.names.txt, one line per segment, in order:
  Name|tag,tag      a sound      skip   an intro / preview / outro      merge   a blank frame: fold into the sound before

Step 3  cut:
  extract_compilation.py cut VIDEO VIDEO.names.txt LIBRARY --pack ID --title "Channel - video title"
  -> LIBRARY/sfx/<id>.flac, appended to LIBRARY/library.json; muted stretches listed in LIBRARY/missing.json

How it cuts: sound is split at digital silence; each stretch goes to the label whose start is nearest where
the audio begins (audio may lead its label by 0.5 s); a sound that runs into the next label is split at the
quietest 10 ms near the change; a segment that is mostly one long (>= 2 s) run of digital silence was muted
by YouTube's Content ID and is skipped, not saved as a fragment. Clips are peak-normalised to -1 dBFS.
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

SR = 44100
BLK = 220  # analysis block: 220 samples (times use BLK / SR exactly, or they drift over minutes)
FONT = next((f for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
                         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"] if Path(f).exists()), None)


def fesc(p):
    """A file path inside an ffmpeg filter option: forward slashes, and the colon of C:/... escaped (Windows)."""
    return str(p).replace("\\", "/").replace(":", "\\:")


def duration(v):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", v],
                                capture_output=True, text=True).stdout)


def detect(a):
    y0, y1 = a.box[0], a.box[1]
    x0, x1 = (a.box[2], a.box[3]) if len(a.box) == 4 else (0.0, 1.0)
    fps, W, H = 10, 320, 40
    crop = f"crop=iw*{x1 - x0}:ih*{y1 - y0}:iw*{x0}:ih*{y0}"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", a.video, "-vf", f"fps={fps},{crop},scale={W}:{H},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, H, W).astype(np.float32)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    ch = [0.0]
    for i in np.nonzero(d > a.thresh)[0]:
        t = round(float(i + 1) / fps, 2)
        if t - ch[-1] >= 0.35:
            ch.append(t)
    dur = duration(a.video)
    Path(a.video + ".segments.json").write_text(json.dumps({"changes": ch, "duration": dur}))
    with tempfile.TemporaryDirectory() as tmp:
        tiles = []
        for i, t in enumerate(ch):
            nxt = ch[i + 1] if i + 1 < len(ch) else t + 1.0
            f = Path(tmp) / f"{i:03d}.png"
            lab = f",drawtext=fontfile='{fesc(FONT)}':text='#{i} {t:.1f}':x=4:y=(h-th)/2:fontsize=20:fontcolor=red" if FONT else ""
            subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t + min(0.4, (nxt - t) / 2):.2f}", "-i", a.video,
                            "-frames:v", "1", "-vf", f"{crop},scale=600:-2,pad=iw+150:ih:150:0:white{lab}", str(f)])
            tiles.append(f)
        rows = (len(tiles) + 1) // 2
        cols = [tiles[:rows], tiles[rows:]]
        args, fc, n, lbl = [], [], 0, []
        for c, col in enumerate(cols):
            if not col:
                continue
            col = col + [col[-1]] * (rows - len(col))
            args += sum((["-i", str(t)] for t in col), [])
            fc.append("".join(f"[{n + k}:v]" for k in range(len(col))) +
                      (f"vstack=inputs={len(col)}[c{c}]" if len(col) > 1 else f"null[c{c}]"))
            n += len(col); lbl.append(f"[c{c}]")
        fc.append("".join(lbl) + (f"hstack=inputs={len(lbl)}[o]" if len(lbl) > 1 else "null[o]"))
        subprocess.run(["ffmpeg", "-y", "-v", "error", *args, "-filter_complex", ";".join(fc), "-map", "[o]",
                        "-frames:v", "1", a.video + ".names.png"], check=True)
    Path(a.video + ".names.txt").write_text("\n".join("?" for _ in ch) + "\n")
    print(f"{len(ch)} segments. Open {a.video}.names.png, then fill {a.video}.names.txt "
          f"(one line per segment: Name|tags, skip, or merge)")


def decode(v):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", v, "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def events(x, thresh_db=-50, min_gap=0.06):
    m = np.abs(x).max(axis=1)
    m = m[: len(m) // BLK * BLK].reshape(-1, BLK).max(axis=1)
    on = 20 * np.log10(m + 1e-9) > thresh_db
    g, ev, i = int(min_gap * SR / BLK), [], 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and (on[j] or (j + g < len(on) and on[j:j + g].any())):
                j += 1
            ev.append([i * BLK / SR, j * BLK / SR]); i = j
        else:
            i += 1
    return ev


def quietest(x, t0, t1):
    n = int(SR * 0.01)
    seg = np.abs(x[int(t0 * SR):int(t1 * SR)]).max(axis=1)
    if len(seg) < n * 2:
        return (t0 + t1) / 2
    seg = seg[: len(seg) // n * n].reshape(-1, n).max(axis=1)
    return t0 + float(np.argmin(seg)) * n / SR + 0.005


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("(explicit)", "")).strip("-")


def cut(a):
    seg_info = json.loads(Path(a.video + ".segments.json").read_text())
    starts, dur = seg_info["changes"], seg_info["duration"]
    rows = [r.strip() for r in Path(a.names).read_text().splitlines() if r.strip()]
    if len(rows) != len(starts):
        sys.exit(f"{a.names} has {len(rows)} lines for {len(starts)} segments")
    if any(r == "?" for r in rows):
        sys.exit("fill every '?' line first (Name|tags, skip or merge)")
    lib_dir = Path(a.library); (lib_dir / "sfx").mkdir(parents=True, exist_ok=True)
    lib_path, miss_path = lib_dir / "library.json", lib_dir / "missing.json"
    lib = json.loads(lib_path.read_text()) if lib_path.exists() else []
    missing = json.loads(miss_path.read_text()) if miss_path.exists() else []
    lib = [l for l in lib if l.get("pack") != a.pack]  # re-cutting a pack replaces it
    missing = [m for m in missing if m.get("pack") != a.pack]
    used = {l["id"] for l in lib}
    segs = []
    for k, r in enumerate(rows):
        end = starts[k + 1] if k + 1 < len(starts) else dur
        if r == "merge" and segs:
            segs[-1][1] = end
        else:
            segs.append([starts[k], end, r])
    x = decode(a.video)
    st = [s[0] for s in segs]
    pieces = {i: [] for i in range(len(segs))}
    for e0, e1 in events(x):
        cand = [i for i, s in enumerate(st) if s <= e0 + 0.5] or [0]
        k = min(cand, key=lambda i: abs(e0 - (st[i] + 0.1)))
        cur, hard = e0, False
        while True:
            nxt = st[k + 1] if k + 1 < len(st) else None
            if nxt is not None and e1 > nxt + 0.1:
                c = quietest(x, max(cur + 0.02, nxt - 0.4), nxt + 0.15)
                if c - cur > 0.03:
                    pieces[k].append((cur, c, hard, True))
                cur, hard, k = c, True, k + 1
            else:
                pieces[k].append((cur, e1, hard, False)); break
    added = 0
    for i, (s, e, r) in enumerate(segs):
        if r == "skip":
            continue
        name, _, tags = r.partition("|")
        sx = np.abs(x[int(s * SR):int(e * SR)]).max(axis=1)
        nb = int(SR * 0.01); sx = sx[: len(sx) // nb * nb].reshape(-1, nb).max(axis=1)
        silent = sx < 1e-6
        run = best = 0
        for q in silent:
            run = run + 1 if q else 0; best = max(best, run)
        if len(sx) and silent.mean() > 0.6 and best * 0.01 >= 2.0 and i < len(segs) - 1:
            missing.append({"name": name, "pack": a.pack, "video_time": round(s, 1), "why": "muted in this copy"})
            print(f"  muted: {name}"); continue
        ps = pieces[i]
        if not ps:
            missing.append({"name": name, "pack": a.pack, "video_time": round(s, 1), "why": "no audio"})
            print(f"  no audio: {name}"); continue
        c0 = min(p[0] for p in ps); c1 = max(p[1] for p in ps)
        hin = any(p[2] and p[0] == c0 for p in ps); hout = any(p[3] and p[1] == c1 for p in ps)
        c0 = max(0.0, c0 - (0 if hin else 0.01)); c1 = min(dur, c1 + (0 if hout else 0.03))
        clip = x[int(c0 * SR):int(c1 * SR)].copy()
        pk = np.abs(clip).max()
        if pk < 1e-4:
            missing.append({"name": name, "pack": a.pack, "video_time": round(s, 1), "why": "silent"}); continue
        clip *= 10 ** (-1 / 20) / pk
        fi = min(int(SR * (0.01 if hin else 0.003)), len(clip) // 4)
        fo = min(int(SR * (0.05 if hout else 0.02)), len(clip) // 4)
        if fi: clip[:fi] *= np.linspace(0, 1, fi)[:, None]
        if fo: clip[-fo:] *= np.linspace(1, 0, fo)[:, None]
        sid = slug(name) or "sfx"
        if sid in used:
            sid = f"{sid}-{slug(a.pack)}"
        n2 = 2
        while sid in used:
            sid = f"{slug(name)}-{slug(a.pack)}-{n2}"; n2 += 1
        used.add(sid)
        f = lib_dir / "sfx" / f"{sid}.flac"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                        "-c:a", "flac", "-sample_fmt", "s16", str(f)], input=clip.astype(np.float32).tobytes(), check=True)
        lib.append({"id": sid, "name": name, "file": f"sfx/{f.name}", "pack": a.pack, "source": a.title,
                    "source_time": round(c0, 2), "duration": round(len(clip) / SR, 3),
                    "peak_s": round(float(np.argmax(np.abs(clip).max(axis=1))) / SR, 3),
                    "tags": [t for t in tags.split(",") if t] or ["untagged"], "split": bool(hin or hout)})
        added += 1
    lib_path.write_text(json.dumps(lib, indent=1))
    miss_path.write_text(json.dumps(missing, indent=1))
    print(f"{a.pack}: {added} sounds added; library now {len(lib)} sounds")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect"); d.add_argument("video"); d.add_argument("--box", type=float, nargs="+", required=True)
    d.add_argument("--thresh", type=float, default=2.5)
    c = sub.add_parser("cut"); c.add_argument("video"); c.add_argument("names"); c.add_argument("library")
    c.add_argument("--pack", required=True); c.add_argument("--title", default="")
    a = ap.parse_args()
    detect(a) if a.cmd == "detect" else cut(a)


if __name__ == "__main__":
    main()
