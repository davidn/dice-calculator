#!/usr/bin/env python3

from main import roll, describe_dice
import unittest


class RollTest(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(roll("1+1"), 2)
        self.assertEqual(roll("1+2*3"), 7)
        self.assertEqual(roll("(1+2)*3"), 9)


class DescribeDiceTest(unittest.TestCase):
    def test_one_dice(self):
        self.assetEmpty(describe_dice([1]), "")
        self.assertEqual(describe_dice([3]), "")

    def test_two_dice(self):
        self.assertIn("1 and 2", describe_dice([1, 2]))

    def test_four_dice(self):
        self.assertIn("1, 2, 3 and 4", describe_dice([1, 2, 3, 4]))


if __name__ == '__main__':
    unittest.main()
