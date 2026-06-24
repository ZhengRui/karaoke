import subprocess
from pathlib import Path

from karaoke.photos import probe_dims


def compose_still(photo, out_png, w=1920, h=1080):
    """16:9 静帧。
    横图(含 4:3,宽≥高):裁切铺满整个画面,更沉浸。
    竖图(高>宽):完整居中不裁人,左右用同图模糊放大压暗版补边。
    """
    pw, ph = probe_dims(photo)
    portrait = pw < ph
    if portrait:
        vf = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},boxblur=20:2,eq=brightness=-0.18[bg];"
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
        )
    else:
        vf = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}[v]"
        )
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(photo), "-filter_complex", vf,
                    "-map", "[v]", "-frames:v", "1", str(out_png)], check=True)


def ken_burns(still_png, out_mp4, dur=6.5, fps=30, zoom_in=True, w=1920, h=1080):
    """对静帧做缓慢推拉,输出固定时长、1920x1080、30fps、yuv420p 的无声片段。"""
    if zoom_in:
        z = "min(zoom+0.0006,1.12)"
    else:
        z = "if(eq(on,0),1.12,max(zoom-0.0006,1.0))"
    zp = (
        f"zoompan=z='{z}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={w}x{h}:fps={fps},trim=duration={dur},setpts=PTS-STARTPTS,format=yuv420p[v]"
    )
    Path(out_mp4).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(still_png), "-t", str(dur),
                    "-filter_complex", zp, "-map", "[v]", "-r", str(fps),
                    "-c:v", "libx264", "-crf", "18", "-t", str(dur), str(out_mp4)],
                   check=True)
