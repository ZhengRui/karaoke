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
