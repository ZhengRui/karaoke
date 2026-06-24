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
