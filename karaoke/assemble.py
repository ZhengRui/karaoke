import math
import subprocess
from pathlib import Path


def clips_needed(audio_dur, dur=6.5, fade=1.0):
    """最少片段数,使 xfade 链总时长 ≥ audio_dur。链总时长 = dur + (n-1)*(dur-fade)。"""
    step = dur - fade
    return 1 + math.ceil((audio_dur - dur) / step)


def build_xfade_filter(n, dur=6.5, fade=1.0):
    """生成链式 xfade 的 filter_complex 字符串。返回 (filter, last_label, total_dur)。"""
    parts = []
    prev = "0:v"
    cumulative = dur
    for i in range(1, n):
        offset = cumulative - fade
        out = f"x{i}"
        parts.append(
            f"[{prev}][{i}:v]xfade=transition=fade:duration={fade}:"
            f"offset={offset:.3f}[{out}]")
        prev = out
        cumulative = cumulative - fade + dur
    return ";".join(parts), prev, cumulative


def assemble(clips, out_mp4, dur=6.5, fade=1.0):
    filt, last, total = build_xfade_filter(len(clips), dur, fade)
    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    cmd += ["-filter_complex", filt, "-map", f"[{last}]",
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(out_mp4)]
    Path(out_mp4).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)
    return total
