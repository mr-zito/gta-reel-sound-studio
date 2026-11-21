#!/usr/bin/env python3
"""Add a folder of loose SFX files (a downloaded pack, an earshot output folder) to the library:
silence-trimmed, peak-normalised OUT_DIR/sfx/<id>.flac plus entries in OUT_DIR/library.json,
with tags guessed from each filename.

usage: index_folder.py IN_DIR OUT_DIR [--pack techkeyfi|earshot] [--peak -1.0] [--merge]

An earshot output folder (with manifest.json) is tagged from earshot's design ids.

--merge adds to the existing OUT_DIR/library.json (always use it on the shared library);
re-running a pack with --merge replaces that pack's entries.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

EXTS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".opus", ".webm", ".mp4"}
# filename keyword -> tags (first matches win, several can apply)
RULES = [
    (r"whoosh|woosh|swoosh|swish|swipe|wind", ["transition", "whoosh"]),
    (r"glitch|static|distort|error|corrupt", ["transition", "glitch"]),
    (r"click|tap|pop|ui|button|select|mouse", ["ui", "click"]),
    (r"typ(e|ing)|keyboard", ["ui", "typing"]),
    (r"gear|mechanic|cog|ratchet", ["mechanical"]),
    (r"boom|impact|hit|punch|slam|thud|bass|drop|braam|kick", ["impact"]),
    (r"riser|rise|build|uplifter|tension|suspense", ["buildup"]),
    (r"cinematic|trailer|epic", ["cinematic", "impact"]),
    (r"explo|blast|bomb|nuke|thunder", ["explosion", "impact"]),
    (r"gun|shot|reload|bullet|rifle|pistol", ["weapon"]),
    (r"car|engine|drift|skid|tyre|tire|horn|crash|brake", ["car"]),
    (r"siren|police|cop|radio", ["police", "chaos"]),
    (r"cash|coin|money|register|cha.?ching", ["money", "win"]),
    (r"laugh|funny|cartoon|boing|honk|fart|goofy|bruh", ["funny"]),
    (r"fail|wrong|error|sad|trombone|wah", ["fail"]),
    (r"win|success|correct|ding|level.?up|achievement|cheer|applause", ["win"]),
    (r"camera|shutter|flash", ["flash", "transition"]),
    (r"notif|message|bell|alert|ring", ["notification"]),
    (r"rewind|tape|scratch|vinyl", ["flashback", "transition"]),
    (r"slow|time.?stop|zawarudo", ["slowmo"]),
    (r"horror|scary|creep|jumpscare", ["horror", "suspense"]),
    (r"glass|shatter|break|smash", ["impact", "glass"]),
    (r"step|footstep|walk|\brun\b", ["foley"]),
    (r"fall|thud|drop", ["impact", "fail"]),
    (r"helicopter|rotor|jet|plane|motorcycle|motorboat|boat", ["vehicle"]),
    (r"crowd|cheer|\bboo\b", ["crowd"]),
    (r"song|music|theme|remix|beat|phonk", ["music"]),
]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(p):
    try:
        return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout)
    except ValueError:
        return 0.0


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "sfx"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("in_dir"); ap.add_argument("out_dir")
    ap.add_argument("--pack", default="folder")
    ap.add_argument("--peak", type=float, default=-1.0)
    ap.add_argument("--merge", action="store_true")
    a = ap.parse_args()
    out = Path(a.out_dir); (out / "sfx").mkdir(parents=True, exist_ok=True)
    lib_path = out / "library.json"
    library = json.loads(lib_path.read_text()) if a.merge and lib_path.exists() else []
    library = [x for x in library if x.get("pack") != a.pack]
    taken = {x["id"] for x in library}
    files = sorted(p for p in Path(a.in_dir).rglob("*") if p.suffix.lower() in EXTS)
    # an earshot output folder carries manifest.json: its design ids ("impact/car") tag better than file names
    design = {}
    for mf in Path(a.in_dir).rglob("manifest.json"):
        try:
            for e in json.loads(mf.read_text()).get("sounds", []):
                for f in e.get("files", [e.get("file")]):
                    design[str((mf.parent / f).resolve())] = (e.get("sound", ""), bool(e.get("loop")))
        except (ValueError, AttributeError):
            pass
    for src in files:
        name = src.stem
        sid = slug(name)
        while sid in taken:
            sid += "-" + a.pack
        taken.add(sid)
        des, is_loop = design.get(str(src.resolve()), ("", False))
        rel = (str(src.relative_to(a.in_dir)) + " " + des.replace("/", " ")).lower()
        tags = []
        for pat, tg in RULES:
            if re.search(pat, rel):
                tags += [t for t in tg if t not in tags]
        tmp, dst = out / "sfx" / f".{sid}.tmp.wav", out / "sfx" / f"{sid}.flac"
        # earshot files start on their sound and end on a whole tail, and loops must stay seamless: never trim them
        trim = ("anull" if des else
                "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02,areverse,"
                "silenceremove=start_periods=1:start_threshold=-65dB:start_silence=0.15,areverse")
        r = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vn", "-af", trim,
                 "-ar", "48000", "-ac", "2", str(tmp)])
        d = duration(tmp)
        if r.returncode or d < 0.05:
            tmp.unlink(missing_ok=True); print(f"! skipped {src.name}", file=sys.stderr); continue
        m = re.search(r"max_volume: (-?[\d.]+) dB",
                      run(["ffmpeg", "-hide_banner", "-i", str(tmp), "-af", "volumedetect", "-f", "null", "-"]).stderr)
        gain = a.peak - (float(m.group(1)) if m else 0.0)
        fo = min(0.04, d / 4)
        fades = "" if is_loop else f",afade=t=in:d=0.005,afade=t=out:st={d - fo:.3f}:d={fo:.3f}"
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp), "-af", f"volume={gain:.2f}dB{fades}",
             "-c:a", "flac", "-sample_fmt", "s16", str(dst)])
        tmp.unlink(missing_ok=True)
        if is_loop:
            tags.append("bed")
        elif d > 12 and "music" not in tags:
            tags.append("music")
        library.append({"id": sid, "name": name + (f" ({des})" if des else ""), "file": f"sfx/{dst.name}", "pack": a.pack,
                        "duration": round(duration(dst), 3), "tags": tags or ["untagged"]})
        print(f"  {dst.name:42s} {library[-1]['duration']:6.2f}s  {'|'.join(library[-1]['tags'])}")
    lib_path.write_text(json.dumps(library, indent=1))
    print(f"{len(library)} sounds in {lib_path}")


if __name__ == "__main__":
    main()
