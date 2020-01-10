#!/usr/bin/env python3

from main import roll, describe_dice, handleRoll, DnD5eKnowledge

from absl.testing import absltest
from dialogflow_v2.types import WebhookRequest, WebhookResponse
import unittest
from lark import Tree, Token


class RollTest(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(roll("1+1"), (2, []))
        self.assertEqual(roll("1+2*3"), (7, []))
        self.assertEqual(roll("(1+2)*3"), (9, []))

    def test_weapon(self):
        self.assertEqual(roll("Blowgun"), (1, []))


class DescribeDiceTest(unittest.TestCase):
    def test_one_dice(self):
        self.assertEqual(describe_dice([1]), "")
        self.assertEqual(describe_dice([3]), "")

    def test_two_dice(self):
        self.assertIn("1 and 2", describe_dice([1, 2]))

    def test_four_dice(self):
        self.assertIn("1, 2, 3 and 4", describe_dice([1, 2, 3, 4]))


class TestHandleRoll(unittest.TestCase):
    def test_dispatches(self):
        req = WebhookRequest()
        req.query_result.parameters["dice_spec"] = "1+1"
        req.query_result.action = "roll"
        res = WebhookResponse()
        handleRoll(req, res)


class TestDnD5eKnowledge(unittest.TestCase):
    def setUp(self):
        self.club_tree = Tree("value", [
            Tree("value", [
                Tree("roll_n", [
                    Tree("value", [Token("INT", '1')]),
                    Tree("die", [Tree("value", [Token("INT", '4')])])
                ])
            ])
        ])
        self.blowgun_tree = Tree("value", [
            Tree("value", [Token("INT", '1')])
        ])

    def test_dice_weapon(self):
        initial_tree = Tree("value", [Token('WEAPON', 'Club')])
        final_tree = DnD5eKnowledge().transform(initial_tree)
        self.assertEqual(final_tree, self.club_tree)

    def test_const_weapon(self):
        initial_tree = Tree("value", [Token('WEAPON', 'Blowgun')])
        final_tree = DnD5eKnowledge().transform(initial_tree)
        self.assertEqual(final_tree, self.blowgun_tree)

    def test_weapon_wrong_case(self):
        initial_tree = Tree("value", [Token('WEAPON', 'cLuB')])
        final_tree = DnD5eKnowledge().transform(initial_tree)
        self.assertEqual(final_tree, self.club_tree)


if __name__ == '__main__':
    absltest.main()
