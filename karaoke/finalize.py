import subprocess
from pathlib import Path

DEFAULT_FONTSDIR = "/System/Library/Fonts"


def finalize(bg_mp4, ass_file, audio, out_mp4, fontsdir=DEFAULT_FONTSDIR):
    subf = f"subtitles={ass_file}"
    if fontsdir:
        subf += f":fontsdir={fontsdir}"
    cmd = ["ffmpeg", "-y", "-i", str(bg_mp4), "-i", str(audio),
           "-filter_complex", f"[0:v]{subf}[v]",
           "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "256k", "-shortest", str(out_mp4)]
    Path(out_mp4).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)
