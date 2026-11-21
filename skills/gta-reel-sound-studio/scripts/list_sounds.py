#!/usr/bin/env python3
"""Search the sound library by tag and/or words.

usage: list_sounds.py [LIBRARY] [--tag impact] [--tag fail] [--find "metal pipe"] [--pack warrior2] [--max-len 3]
       [--no-music] [--no-explicit]
Prints id, length, peak time, tags and source. Tags combine with AND; --find matches id or name.
"""
import argparse, json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("library", nargs="?", default="gta_sfx_library")
ap.add_argument("--tag", action="append", default=[]); ap.add_argument("--find", default="")
ap.add_argument("--pack", default=""); ap.add_argument("--max-len", type=float, default=0)
ap.add_argument("--no-music", action="store_true"); ap.add_argument("--no-explicit", action="store_true")
a = ap.parse_args()
lib = json.loads((Path(a.library) / "library.json").read_text())
words = a.find.lower().split()
rows = [e for e in lib
        if all(t in e["tags"] for t in a.tag)
        and all(w in (e["id"] + " " + e["name"]).lower() for w in words)
        and (not a.pack or e["pack"] == a.pack)
        and (not a.max_len or e["duration"] <= a.max_len)
        and not (a.no_music and "music" in e["tags"]) and not (a.no_explicit and "explicit" in e["tags"])]
for e in rows:
    print(f"{e['id']:34s} {e['duration']:5.2f}s  peak {e.get('peak_s', 0):4.2f}s  {','.join(e['tags']):28s} {e['pack']}")
print(f"{len(rows)} of {len(lib)} sounds")
