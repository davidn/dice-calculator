#!/usr/bin/env python3

from dice_calculator import roll, describe_dice
from absl.testing import absltest
import unittest


class RollTest(absltest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(roll("1+1"), (2, []))
        self.assertEqual(roll("1+2*3"), (7, []))
        self.assertEqual(roll("(1+2)*3"), (9, []))

    def test_weapon(self):
        self.assertEqual(roll("Blowgun"), (1, []))

    def test_crit(self):
        _, dice = roll("critical longsword")
        self.assertLen(dice, 2)

    def test_advantage(self):
        final, dice = roll("to hit with advantage")
        self.assertLen(dice, 2)
        self.assertEqual(final, max(dice))

    def test_disadvantage(self):
        final, dice = roll("to hit with disadvantage")
        self.assertLen(dice, 2)
        self.assertEqual(final, min(dice))

    def test_spell(self):
        # repeat multiple times to ensure we don't just get lucky
        for _ in range(30):
            outcome, dice = roll("Magic Missile")
            self.assertBetween(outcome, 2, 5)
            self.assertLen(dice, 1)

    def test_spell_level(self):
        outcome, dice = roll("disintegrate at 7th level")
        self.assertBetween(outcome, 53, 118)
        self.assertLen(dice, 13)


class DescribeDiceTest(unittest.TestCase):
    def test_one_dice(self):
        self.assertEqual(describe_dice([1]), "")
        self.assertEqual(describe_dice([3]), "")

    def test_two_dice(self):
        self.assertIn("1 and 2", describe_dice([1, 2]))

    def test_four_dice(self):
        self.assertIn("1, 2, 3 and 4", describe_dice([1, 2, 3, 4]))


if __name__ == '__main__':
    absltest.main()
