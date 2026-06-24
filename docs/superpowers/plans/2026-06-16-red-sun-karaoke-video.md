# 红日卡拉OK视频 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `remix.wav` 伴奏 + 21 张会员照片(滚动+模糊补边+推拉) + 由 `lyrics.lrc` 生成的特大同步字幕，渲染成 `red_sun_karaoke.mp4`(1920×1080)。

**Architecture:** 一个 Python 包 `karaoke/` 提供纯逻辑(LRC 解析、ASS 生成、照片排序、xfade 滤镜图字符串)和 ffmpeg 封装(合成静帧、Ken Burns、拼接、烧字幕+合音)。`build_video.py` 是分阶段 CLI 编排器(`--stage subs|stills|clips|assemble|finalize|all`),中间产物落 `build/`,可单独重跑某阶段(改字幕样式无需重渲照片)。

**Tech Stack:** Python 3.10(stdlib only,测试用 `unittest`)、ffmpeg/ffprobe(filters: scale/crop/boxblur/overlay/zoompan/xfade/subtitles)、libass(STHeiti / "Heiti SC" 字体,经 `fontsdir`)。

**环境事实(已核实):**
- `remix.wav` 时长 285.373s。
- CJK 字体:`/System/Library/Fonts/STHeiti Medium.ttc`(family "Heiti SC")。无 PingFang。
- 非 git 仓库 → 用验证检查点代替 commit。
- pytest 未装 → 用 stdlib `unittest`,跑 `python3 -m unittest discover -s tests`。

---

## File Structure

```
red_sun/
  karaoke/
    __init__.py
    lrc.py          # LRC 解析 → 排序后的 LyricLine 列表
    ass_gen.py      # LyricLine 列表 → ASS 字幕文本(Cur + Next 两样式)
    photos.py       # 列目录/probe 朝向/构造铺满整首的照片序列
    clips.py        # ffmpeg 封装:compose_still + ken_burns
    assemble.py     # 生成 xfade 滤镜图字符串 + 执行拼接
    finalize.py     # 烧字幕 + 合伴奏 → 最终 mp4
  build_video.py    # CLI 编排器 + CONFIG 常量
  tests/
    test_lrc.py
    test_ass_gen.py
    test_photos.py
    test_assemble.py
  build/            # 中间产物(stills/*.png, clips/*.mp4, bg.mp4, subtitles.ass)
```

---

### Task 1: 包骨架与 LRC 解析

**Files:**
- Create: `karaoke/__init__.py` (空)
- Create: `karaoke/lrc.py`
- Test: `tests/test_lrc.py`

- [ ] **Step 1: 写失败测试**

`tests/test_lrc.py`:
```python
import unittest
from karaoke.lrc import parse_lrc, LyricLine

SAMPLE = """[00:00.34]李克勤 - 红日
[00:00.20]词：李克勤
[00:00.30]曲：立川俊之
[00:21.23]命运就算颠沛流离
[00:22.91]命运就算曲折离奇
[00:28.47]别流泪心酸更不应舍弃
"""

class TestParseLrc(unittest.TestCase):
    def test_skips_metadata(self):
        lines = parse_lrc(SAMPLE)
        texts = [l.text for l in lines]
        self.assertNotIn("李克勤 - 红日", texts)
        self.assertNotIn("词：李克勤", texts)
        self.assertEqual(texts[0], "命运就算颠沛流离")

    def test_parses_time_seconds(self):
        lines = parse_lrc(SAMPLE)
        self.assertAlmostEqual(lines[0].time, 21.23, places=2)

    def test_sorted_by_time(self):
        lines = parse_lrc(SAMPLE)
        times = [l.time for l in lines]
        self.assertEqual(times, sorted(times))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd ~/Documents/Talks/SoarHigh/2026.06.17_ai_boom_or_doom/red_sun && python3 -m unittest tests.test_lrc -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'karaoke'`

- [ ] **Step 3: 实现 `karaoke/__init__.py`(空)与 `karaoke/lrc.py`**

```python
# karaoke/lrc.py
import re
from dataclasses import dataclass

_LRC_LINE = re.compile(r'^\[(\d{2}):(\d{2})\.(\d{2})\](.*)$')
_META_MARKERS = ('李克勤', '词：', '曲：', '词:', '曲:')


@dataclass
class LyricLine:
    time: float   # 秒
    text: str


def parse_lrc(text: str) -> list:
    """解析 LRC 文本为按时间排序的 LyricLine 列表,跳过元数据行。"""
    out = []
    for raw in text.splitlines():
        m = _LRC_LINE.match(raw.strip())
        if not m:
            continue
        mm, ss, cc, content = m.groups()
        content = content.strip()
        if not content or any(mk in content for mk in _META_MARKERS):
            continue
        t = int(mm) * 60 + int(ss) + int(cc) / 100.0
        out.append(LyricLine(t, content))
    out.sort(key=lambda l: l.time)
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_lrc -v`
Expected: PASS(3 tests)

- [ ] **Step 5: 用真实歌词冒烟验证**

Run: `python3 -c "from karaoke.lrc import parse_lrc; ls=parse_lrc(open('lyrics.lrc').read()); print(len(ls),'lines; first:',ls[0].time,ls[0].text,'; last:',ls[-1].time,ls[-1].text)"`
Expected: 约 60 行；first ≈ 21.23 命运就算颠沛流离；last ≈ 268.67 哦

---

### Task 2: ASS 字幕生成(Cur + Next 两样式)

**Files:**
- Create: `karaoke/ass_gen.py`
- Test: `tests/test_ass_gen.py`

- [ ] **Step 1: 写失败测试**

`tests/test_ass_gen.py`:
```python
import unittest
from karaoke.lrc import LyricLine
from karaoke.ass_gen import build_ass, fmt_time

class TestAss(unittest.TestCase):
    def test_fmt_time(self):
        self.assertEqual(fmt_time(21.23), "0:00:21.23")
        self.assertEqual(fmt_time(3661.5), "1:01:01.50")

    def test_event_uses_next_line_start_as_end(self):
        lines = [LyricLine(21.23, "A"), LyricLine(22.91, "B")]
        ass = build_ass(lines, audio_end=300.0, show_next=True)
        # 当前句 A 显示到 B 的开始
        self.assertIn("0:00:21.23,0:00:22.91,Cur,,0,0,,,A", ass)
        # 预读句:在 A 的时段显示 B
        self.assertIn("0:00:21.23,0:00:22.91,Next,,0,0,,,B", ass)

    def test_last_line_ends_at_audio_end(self):
        lines = [LyricLine(21.23, "A")]
        ass = build_ass(lines, audio_end=300.0)
        self.assertIn("0:00:21.23,0:05:00.00,Cur,,0,0,,,A", ass)

    def test_styles_present(self):
        ass = build_ass([LyricLine(1.0, "x")], audio_end=5.0, font="Heiti SC")
        self.assertIn("Style: Cur,Heiti SC", ass)
        self.assertIn("Style: Next,Heiti SC", ass)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_ass_gen -v`
Expected: FAIL — `No module named 'karaoke.ass_gen'`

- [ ] **Step 3: 实现 `karaoke/ass_gen.py`**

颜色为 ASS `&HAABBGGRR`:当前句金黄 `#FFD24A` → `&H004AD2FF`;预读句白色约 65% 不透明 → alpha `&H59` → `&H59FFFFFF`。

```python
# karaoke/ass_gen.py
_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cur,{font},{cur_size},&H004AD2FF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,3,2,80,80,{cur_marginv},1
Style: Next,{font},{next_size},&H59FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,2,2,80,80,{next_marginv},1

[Events]
Format: Layer, Start, End, Style, MarginL, MarginR, Effect, Name, Text
"""


def fmt_time(t: float) -> str:
    if t < 0:
        t = 0.0
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(lines, audio_end, font="Heiti SC",
              cur_size=84, next_size=48,
              cur_marginv=150, next_marginv=70,
              show_next=True) -> str:
    header = _HEADER.format(font=font, cur_size=cur_size, next_size=next_size,
                            cur_marginv=cur_marginv, next_marginv=next_marginv)
    events = []
    n = len(lines)
    for i, ln in enumerate(lines):
        start = ln.time
        end = lines[i + 1].time if i + 1 < n else audio_end
        events.append(
            f"Dialogue: 0,{fmt_time(start)},{fmt_time(end)},Cur,,0,0,,,{ln.text}")
        if show_next and i + 1 < n:
            events.append(
                f"Dialogue: 0,{fmt_time(start)},{fmt_time(end)},Next,,0,0,,,{lines[i + 1].text}")
    return header + "\n".join(events) + "\n"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_ass_gen -v`
Expected: PASS(4 tests)

注:`cur_marginv=150` 让当前句抬高,`next_marginv=70` 让预读句落在其下方(均为 Alignment 2 底部锚点,MarginV 自底向上)。字号/边距是 CONFIG 可调项。

---

### Task 3: 照片排序与朝向探测

**Files:**
- Create: `karaoke/photos.py`
- Test: `tests/test_photos.py`

- [ ] **Step 1: 写失败测试**

`tests/test_photos.py`:
```python
import unittest
from karaoke.photos import build_sequence, list_photos

class TestSequence(unittest.TestCase):
    def test_fills_to_target_count(self):
        photos = [f"p{i}.jpg" for i in range(5)]
        seq = build_sequence(photos, target_count=12, seed=7)
        self.assertEqual(len(seq), 12)

    def test_first_pass_in_order(self):
        photos = [f"p{i}.jpg" for i in range(5)]
        seq = build_sequence(photos, target_count=12, seed=7)
        self.assertEqual(seq[:5], photos)

    def test_deterministic_with_seed(self):
        photos = [f"p{i}.jpg" for i in range(5)]
        a = build_sequence(photos, 20, seed=7)
        b = build_sequence(photos, 20, seed=7)
        self.assertEqual(a, b)

    def test_no_immediate_repeat_at_seam(self):
        photos = [f"p{i}.jpg" for i in range(5)]
        seq = build_sequence(photos, 30, seed=7)
        for i in range(1, len(seq)):
            self.assertNotEqual(seq[i], seq[i - 1])

class TestListPhotos(unittest.TestCase):
    def test_lists_21_real_photos(self):
        photos = list_photos("photos")
        self.assertEqual(len(photos), 21)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_photos -v`
Expected: FAIL — `No module named 'karaoke.photos'`

- [ ] **Step 3: 实现 `karaoke/photos.py`**

```python
# karaoke/photos.py
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_photos -v`
Expected: PASS(5 tests)

---

### Task 4: 单张照片 → 合成静帧 + Ken Burns 片段

**Files:**
- Create: `karaoke/clips.py`

无单元测试(纯 ffmpeg 副作用);用真实素材产物 + ffprobe 验证。

- [ ] **Step 1: 实现 `karaoke/clips.py`**

```python
# karaoke/clips.py
import subprocess
from pathlib import Path


def compose_still(photo, out_png, w=1920, h=1080):
    """16:9 静帧:横图裁切铺满;竖图完整居中 + 同图模糊放大压暗补边。"""
    vf = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},boxblur=20:2,eq=brightness=-0.18[bg];"
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
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
```

- [ ] **Step 2: 对一张横图 + 一张竖图各产一帧验证补边**

Run:
```bash
python3 -c "from karaoke.clips import compose_still; compose_still('photos/1.jpg','build/_t_land.png'); compose_still('photos/6.jpg','build/_t_port.png')"
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 build/_t_land.png
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 build/_t_port.png
```
Expected: 两个都输出 `1920,1080`。

- [ ] **Step 3: 人眼验证补边正确**

Run: `open build/_t_port.png`
Expected: 竖照片(6.jpg)完整居中不裁人,左右是它自己的模糊放大压暗版;横照片(1.jpg)铺满全屏。若竖图仍被裁,停下来检查 `scale=...:force_original_aspect_ratio=decrease`。

- [ ] **Step 4: 产一个 Ken Burns 片段验证时长/规格**

Run:
```bash
python3 -c "from karaoke.clips import ken_burns; ken_burns('build/_t_port.png','build/_t_clip.mp4',dur=6.5)"
ffprobe -v error -show_entries format=duration:stream=width,height,r_frame_rate -of default=noprint_wrappers=1 build/_t_clip.mp4
```
Expected: duration≈6.5,width=1920,height=1080,r_frame_rate=30/1。

- [ ] **Step 5: 清理临时文件**

Run: `rm -f build/_t_land.png build/_t_port.png build/_t_clip.mp4`

---

### Task 5: xfade 拼接滤镜图

**Files:**
- Create: `karaoke/assemble.py`
- Test: `tests/test_assemble.py`

- [ ] **Step 1: 写失败测试**

`tests/test_assemble.py`:
```python
import unittest
from karaoke.assemble import build_xfade_filter, clips_needed

class TestXfade(unittest.TestCase):
    def test_clips_needed_covers_audio(self):
        # dur=6.5 fade=1.0 → 每段净增 5.5,首段 6.5
        n = clips_needed(285.373, dur=6.5, fade=1.0)
        total = 6.5 + (n - 1) * 5.5
        self.assertGreaterEqual(total, 285.373)
        self.assertLess(6.5 + (n - 2) * 5.5, 285.373)  # n 是最小满足值

    def test_filter_has_n_minus_1_xfades(self):
        filt, last, total = build_xfade_filter(3, dur=6.5, fade=1.0)
        self.assertEqual(filt.count("xfade="), 2)
        self.assertEqual(last, "x2")
        self.assertAlmostEqual(total, 6.5 + 2 * 5.5, places=3)

    def test_first_offset_is_dur_minus_fade(self):
        filt, _, _ = build_xfade_filter(2, dur=6.5, fade=1.0)
        self.assertIn("offset=5.500", filt)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python3 -m unittest tests.test_assemble -v`
Expected: FAIL — `No module named 'karaoke.assemble'`

- [ ] **Step 3: 实现 `karaoke/assemble.py`**

```python
# karaoke/assemble.py
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_assemble -v`
Expected: PASS(3 tests)

---

### Task 6: 烧字幕 + 合伴奏 = 最终输出

**Files:**
- Create: `karaoke/finalize.py`

- [ ] **Step 1: 实现 `karaoke/finalize.py`**

`fontsdir` 指向 `/System/Library/Fonts`(含 STHeiti),配合 ASS 内 `Fontname: Heiti SC`,即便系统无 fontconfig 也能被 libass 找到。

```python
# karaoke/finalize.py
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
```

注:`-shortest` 让成品长度对齐伴奏(285.37s);背景视频被裁到该长度。

---

### Task 7: CLI 编排器 `build_video.py`

**Files:**
- Create: `build_video.py`

- [ ] **Step 1: 实现编排器(CONFIG 常量集中在顶部)**

```python
# build_video.py
import argparse
import subprocess
from pathlib import Path

from karaoke.lrc import parse_lrc
from karaoke.ass_gen import build_ass
from karaoke.photos import list_photos, build_sequence
from karaoke.clips import compose_still, ken_burns
from karaoke.assemble import clips_needed, assemble
from karaoke.finalize import finalize

# ---------------- CONFIG(可微调) ----------------
ROOT = Path(__file__).parent
PHOTOS_DIR = ROOT / "photos"
LRC_FILE = ROOT / "lyrics.lrc"
AUDIO = ROOT / "separated/htdemucs/red_sun/remix.wav"
BUILD = ROOT / "build"
OUT = ROOT / "red_sun_karaoke.mp4"

PHOTO_DUR = 6.5          # 每张照片停留秒数
FADE = 1.0               # 交叉淡化秒数
FONT = "Heiti SC"
CUR_SIZE = 84            # 当前句字号(特大)
NEXT_SIZE = 48           # 预读句字号
CUR_MARGINV = 150
NEXT_MARGINV = 70
SHOW_NEXT = True
SEED = 7
# ------------------------------------------------


def audio_duration():
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(AUDIO)])
    return float(out.strip())


def stage_subs():
    dur = audio_duration()
    lines = parse_lrc(LRC_FILE.read_text())
    ass = build_ass(lines, audio_end=dur, font=FONT,
                    cur_size=CUR_SIZE, next_size=NEXT_SIZE,
                    cur_marginv=CUR_MARGINV, next_marginv=NEXT_MARGINV,
                    show_next=SHOW_NEXT)
    BUILD.mkdir(exist_ok=True)
    (BUILD / "subtitles.ass").write_text(ass)
    print(f"subs: {len(lines)} lines → build/subtitles.ass (audio_end={dur:.2f})")


def stage_stills():
    photos = list_photos(PHOTOS_DIR)
    (BUILD / "stills").mkdir(parents=True, exist_ok=True)
    for p in photos:
        compose_still(p, BUILD / "stills" / f"{p.stem}.png")
    print(f"stills: {len(photos)} composed")


def stage_clips():
    photos = list_photos(PHOTOS_DIR)
    n = clips_needed(audio_duration(), dur=PHOTO_DUR, fade=FADE)
    seq = build_sequence(photos, target_count=n, seed=SEED)
    (BUILD / "clips").mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(seq):
        still = BUILD / "stills" / f"{p.stem}.png"
        ken_burns(still, BUILD / "clips" / f"clip_{i:03d}.mp4",
                  dur=PHOTO_DUR, fps=30, zoom_in=(i % 2 == 0))
    print(f"clips: {n} generated")


def stage_assemble():
    n = clips_needed(audio_duration(), dur=PHOTO_DUR, fade=FADE)
    clips = [BUILD / "clips" / f"clip_{i:03d}.mp4" for i in range(n)]
    total = assemble(clips, BUILD / "bg.mp4", dur=PHOTO_DUR, fade=FADE)
    print(f"assemble: {n} clips → build/bg.mp4 (~{total:.1f}s)")


def stage_finalize():
    finalize(BUILD / "bg.mp4", BUILD / "subtitles.ass", AUDIO, OUT)
    print(f"finalize: → {OUT}")


STAGES = {
    "subs": stage_subs, "stills": stage_stills, "clips": stage_clips,
    "assemble": stage_assemble, "finalize": stage_finalize,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=list(STAGES) + ["all"])
    args = ap.parse_args()
    order = ["subs", "stills", "clips", "assemble", "finalize"]
    todo = order if args.stage == "all" else [args.stage]
    for s in todo:
        print(f"=== {s} ===")
        STAGES[s]()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑字幕阶段并人眼检查 ASS**

Run: `python3 build_video.py subs && head -20 build/subtitles.ass`
Expected: 打印 “subs: ~60 lines … audio_end=285.37”;ASS 含 `Style: Cur,Heiti SC,84,...` 和首条 Dialogue。

- [ ] **Step 3: 跑静帧阶段并抽查**

Run: `python3 build_video.py stills && ls build/stills | wc -l && open build/stills/6.png build/stills/1.png`
Expected: 21 张 png;6(竖)补边居中不裁人,1(横)铺满。

---

### Task 8: 整片渲染与验证

**Files:** 无新文件;运行全流程并验证成品。

- [ ] **Step 1: 跑片段 + 拼接(较慢,数分钟)**

Run: `python3 build_video.py clips && python3 build_video.py assemble`
Expected: 生成 `build/clips/clip_*.mp4`(约 52 个)与 `build/bg.mp4`;bg 时长 ≥285s。

- [ ] **Step 2: 合成最终成品**

Run: `python3 build_video.py finalize`
Expected: 生成 `red_sun_karaoke.mp4`。

- [ ] **Step 3: 校验成品规格与时长**

Run:
```bash
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,codec_name -of default=noprint_wrappers=1 red_sun_karaoke.mp4
```
Expected: duration≈285.37;video h264 1920×1080;audio aac。

- [ ] **Step 4: 抽帧校验字幕与歌词对齐**

在已知有歌词的时间点抽帧(如 22s “命运就算颠沛流离”、85s 副歌、165s):
```bash
for t in 22 85 100 165 250; do ffmpeg -y -ss $t -i red_sun_karaoke.mp4 -frames:v 1 build/_check_$t.png 2>/dev/null; done
open build/_check_22.png build/_check_85.png build/_check_100.png build/_check_165.png build/_check_250.png
```
Expected: 每帧底部有特大金黄当前句 + 下方白色预读句,且与该时间点 `lyrics.lrc` 内容一致;字幕未超出画面、未压住人脸主体。前奏时间点(如 5s)应无字幕。

- [ ] **Step 5: 整段试播(现场前必做)**

Run: `open red_sun_karaoke.mp4`
人工确认:音画同步、字幕跟唱节奏正确、竖照片无裁脸、转场顺滑、收尾“哦”之后照片续放至音乐结束。
若字幕字号/位置要调:改 `build_video.py` 顶部 CONFIG → 只重跑 `python3 build_video.py subs finalize`(无需重渲照片)。

- [ ] **Step 6: 清理抽帧临时文件**

Run: `rm -f build/_check_*.png`

---

## Self-Review

**Spec coverage:**
- 成品 MP4 1920×1080/伴奏时长 → Task 6/8 ✓
- 布局 A 满屏+底部歌词 → Task 2(ASS 底部)+Task 4(满屏)✓
- Ken Burns 推拉/6.5s/1s 淡化/循环铺满/第二遍乱序 → Task 4/5/3 ✓
- 竖图模糊补边 → Task 4 ✓
- 特大金黄当前句 + 白色预读句 → Task 2 ✓
- 时间轴用 LRC、间奏留白、末句“哦”后续放 → Task 1/2/8 ✓
- remix.wav 伴奏 → Task 6 ✓
- 动态读取照片数、损坏跳过、音频为准、字体检查 → Task 3/6/8 ✓
- 可调参数集中 → Task 7 CONFIG ✓
- 分阶段重跑 → Task 7 ✓

**Placeholder scan:** 无 TBD/TODO;每个代码步骤含完整代码。✓

**Type consistency:** `LyricLine(time,text)` 跨 Task 1/2 一致;`build_ass` 参数与 Task 7 调用一致;`clips_needed/build_xfade_filter/assemble` 签名跨 Task 5/7 一致;`compose_still/ken_burns` 跨 Task 4/7 一致;`finalize` 跨 Task 6/7 一致。✓

**注意事项(实现时验证,非阻塞):**
- `zoompan` 推拉在某些 ffmpeg 版本可能轻微抖动;若明显,Task 4 可把 `z` 步进调小或改用纯 `scale` 缓动。
- `Heiti SC` 字体名若 libass 不识别,改用 `STHeiti` 或在 ASS 里直接用文件;Task 8 Step 4 抽帧即可发现(字幕变方框/缺字)。
- 字幕 Cur/Next 边距若重叠,调 `CUR_MARGINV/NEXT_MARGINV`。
