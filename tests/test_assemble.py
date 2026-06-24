import unittest
from karaoke.assemble import build_xfade_filter, clips_needed


class TestXfade(unittest.TestCase):
    def test_clips_needed_covers_audio(self):
        n = clips_needed(285.373, dur=6.5, fade=1.0)
        total = 6.5 + (n - 1) * 5.5
        self.assertGreaterEqual(total, 285.373)
        self.assertLess(6.5 + (n - 2) * 5.5, 285.373)

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
