import unittest
from karaoke.lrc import LyricLine
from karaoke.ass_gen import build_ass, fmt_time


class TestAss(unittest.TestCase):
    def test_fmt_time(self):
        self.assertEqual(fmt_time(21.23), "0:00:21.23")
        self.assertEqual(fmt_time(3661.5), "1:01:01.50")

    def test_one_event_per_line(self):
        lines = [LyricLine(21.23, "A"), LyricLine(24.0, "B")]
        ass = build_ass(lines, audio_end=300.0)
        self.assertEqual(ass.count("Dialogue:"), 2)

    def test_no_extra_comma_before_override(self):
        lines = [LyricLine(21.23, "A")]
        ass = build_ass(lines, audio_end=300.0)
        # Style 后正好 MarginL,MarginR,Effect,Name 四字段,随即是 {override}
        self.assertIn("Roll,0,0,,,{", ass)
        self.assertNotIn("Roll,0,0,,,,", ass)

    def test_text_follows_override_block(self):
        lines = [LyricLine(21.23, "命运")]
        ass = build_ass(lines, audio_end=300.0)
        self.assertIn("}命运", ass)        # 文本紧跟在 } 之后,无前导逗号

    def test_has_scroll_and_color_animation(self):
        lines = [LyricLine(10.0, "A"), LyricLine(13.0, "B")]
        ass = build_ass(lines, audio_end=20.0, gold="&H4AD2FF&")
        self.assertIn(r"\move(", ass)
        self.assertIn(r"\t(", ass)
        self.assertIn("4AD2FF", ass)       # 变色目标:金黄
        self.assertIn(r"\fscx100\fscy100", ass)  # 放大目标

    def test_first_line_starts_intro_lead_before(self):
        lines = [LyricLine(21.6, "A"), LyricLine(25.0, "B")]
        ass = build_ass(lines, audio_end=40.0, intro_lead=1.6)
        # 第一句事件起点 = 21.6 - 1.6 = 20.0
        self.assertIn("Dialogue: 0,0:00:20.00,", ass)

    def test_second_line_starts_at_prev_line_time(self):
        lines = [LyricLine(21.0, "A"), LyricLine(25.0, "B")]
        ass = build_ass(lines, audio_end=40.0)
        # 第二句作为"下句"出现于上一句开始 21.0
        self.assertIn("Dialogue: 0,0:00:21.00,", ass)

    def test_last_line_ends_at_audio_end(self):
        lines = [LyricLine(21.0, "A"), LyricLine(25.0, "B")]
        ass = build_ass(lines, audio_end=40.0)
        self.assertIn(",0:00:40.00,Roll", ass)

    def test_style_present(self):
        ass = build_ass([LyricLine(1.0, "x")], audio_end=5.0, font="Heiti SC")
        self.assertIn("Style: Roll,Heiti SC", ass)


if __name__ == "__main__":
    unittest.main()
