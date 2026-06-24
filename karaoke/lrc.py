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
