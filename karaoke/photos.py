import json
import random
import subprocess
from pathlib import Path


def probe_dims(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", str(path)])
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])


def is_portrait(path):
    w, h = probe_dims(path)
    return (w / h) < (16 / 9)


def list_photos(photo_dir):
    def key(p):
        return (0, int(p.stem)) if p.stem.isdigit() else (1, p.stem)
    paths = sorted(Path(photo_dir).glob("*.jpg"), key=key)
    good = []
    for p in paths:
        try:
            probe_dims(p)
            good.append(p)
        except Exception as e:
            print(f"WARN skipping {p}: {e}")
    return good


def build_sequence(photos, target_count, seed=7):
    rng = random.Random(seed)
    seq = list(photos)                      # 第一遍:按序
    while len(seq) < target_count:
        nxt = list(photos)
        rng.shuffle(nxt)
        if seq and nxt and nxt[0] == seq[-1]:   # 避免接缝处重复同一张
            nxt.append(nxt.pop(0))
        seq.extend(nxt)
    return seq[:target_count]
