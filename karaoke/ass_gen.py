"""滚动歌词 ASS 生成。

效果(用户确认):任意时刻显示两句——中间"当前句"大号金黄,下方"下句"小号白色。
切句时在 ~0.3s 内快速完成:当前句原地淡出消失(不上飘,且在下句到位前消失),
下句升到中间、放大、变金黄成为当前句,下下句升入下方淡入成为新的下句。

实现:每句一个 Dialogue 事件,横跨它从"下句"到"当前句"再到淡出的整段生命:
  - \\move 控制位置:下句槽位 -> 静止 -> 当前槽位 -> 静止(\\move 自带前后保持)
  - \\t 动画:淡入到下句透明度;升句时同步放大+变色+变全不透明;末尾原地淡出
"""

WHITE = "&HFFFFFF&"

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Roll,{font},{base_size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,3,5,40,40,0,1

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
              base_size=84, next_scale=0.62,
              x=960, y_cur=860, y_next=934,
              gold="&H4AD2FF&", next_alpha="&H60&",
              rise_ms=300, out_ms=220, fadein_ms=200,
              intro_lead=1.6, tail=0.25) -> str:
    """生成滚动歌词 ASS。

    lines: 已按时间排序的 LyricLine 列表。
    audio_end: 末句的结束时间(秒)。
    每句 i:在中间被唱的区间是 [t_i, t_{i+1}];它作为"下句"出现于上一句开始时
    (第一句则提前 intro_lead 秒淡入)。
    """
    header = _HEADER.format(font=font, base_size=base_size)
    ns = int(round(next_scale * 100))
    events = []
    n = len(lines)
    for i, ln in enumerate(lines):
        t_cur = ln.time
        t_switch = lines[i + 1].time if i + 1 < n else audio_end
        # 事件起点:作为"下句"开始出现的时刻
        start = (lines[i - 1].time if i >= 1 else t_cur - intro_lead)
        end = (t_switch + tail) if i + 1 < n else audio_end

        # 各动画窗口(相对事件起点的毫秒)
        rise_center = (t_cur - start) * 1000.0
        t1 = int(round(rise_center - rise_ms / 2))
        t2 = int(round(rise_center + rise_ms / 2))
        t1 = max(t1, fadein_ms)          # 升句不早于淡入完成
        t2 = max(t2, t1 + 60)

        out_end = int(round((t_switch - start) * 1000.0))
        out_start = out_end - out_ms
        out_start = max(out_start, t2 + 50)  # 淡出在升句完成之后
        out_end = max(out_end, out_start + 60)

        ov = (
            f"{{\\an5\\move({x},{y_next},{x},{y_cur},{t1},{t2})"
            f"\\fscx{ns}\\fscy{ns}\\c{WHITE}\\alpha&HFF&"
            f"\\t(0,{fadein_ms},\\alpha{next_alpha})"
            f"\\t({t1},{t2},\\fscx100\\fscy100\\c{gold}\\alpha&H00&)"
            f"\\t({out_start},{out_end},\\alpha&HFF&)}}"
        )
        events.append(
            f"Dialogue: 0,{fmt_time(start)},{fmt_time(end)},Roll,0,0,,,{ov}{ln.text}")
    return header + "\n".join(events) + "\n"
