#!/usr/bin/env python3

from main import roll, describe_dice, handleRoll, DnD5eKnowledge, SimplifyTransformer, pprint

from absl.testing import absltest
from dialogflow_v2.types import WebhookRequest, WebhookResponse
import unittest
from lark import Tree, Token


class RollTest(absltest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(roll("1+1"), (2, []))
        self.assertEqual(roll("1+2*3"), (7, []))
        self.assertEqual(roll("(1+2)*3"), (9, []))

    def test_weapon(self):
        self.assertEqual(roll("Blowgun"), (1, []))

    def test_spell(self):
        # repeat multiple times to ensure we don't just get lucky
        for _ in range(30):
            outcome, dice = roll("Magic Missile")
            self.assertBetween(outcome, 2, 5)
            self.assertLen(dice, 1)


class DescribeDiceTest(unittest.TestCase):
    def test_one_dice(self):
        self.assertEqual(describe_dice([1]), "")
        self.assertEqual(describe_dice([3]), "")

    def test_two_dice(self):
        self.assertIn("1 and 2", describe_dice([1, 2]))

    def test_four_dice(self):
        self.assertIn("1, 2, 3 and 4", describe_dice([1, 2, 3, 4]))


class HandleRollTest(unittest.TestCase):
    def test_dispatches(self):
        req = WebhookRequest()
        req.query_result.parameters["dice_spec"] = "1+1"
        req.query_result.action = "roll"
        res = WebhookResponse()
        handleRoll(req, res)


class SimplifyTransformerTest(unittest.TestCase):
    def test_collapse_value(self):
        in_tree = Tree('value', [1])
        out_tree = SimplifyTransformer().transform(in_tree)
        self.assertEqual(out_tree, 1)

    def test_combine_roll_one(self):
        in_tree = Tree('sum', [
            Tree('roll_one', [6]),
            Tree('roll_one', [6]),
        ])
        out_tree = SimplifyTransformer().transform(in_tree)
        self.assertEqual(out_tree, Tree('roll_n', [2, 6]))

    def test_combine_roll_one_and_n(self):
        in_tree = Tree('sum', [
            Tree('roll_one', [6]),
            Tree('roll_n', [2,6]),
        ])
        out_tree = SimplifyTransformer().transform(in_tree)
        self.assertEqual(out_tree, Tree('roll_n', [3, 6]))

    def test_combine_roll_n(self):
        in_tree = Tree('sum', [
            Tree('roll_n', [3,6]),
            Tree('roll_n', [2,6]),
        ])
        out_tree = SimplifyTransformer().transform(in_tree)
        self.assertEqual(out_tree, Tree('roll_n', [5, 6]))

    def test_no_combine_different(self):
        in_tree = Tree('sum', [
            Tree('roll_n', [3,4]),
            Tree('roll_n', [2,6]),
        ])
        out_tree = SimplifyTransformer().transform(in_tree)
        self.assertEqual(out_tree, in_tree)


class DnD5eKnowledgeTest(unittest.TestCase):
    def setUp(self):
        self.club_tree = Tree("roll_n", [1, 4])
        self.fireball_tree = Tree("roll_n", [8, 6])
        self.fireball_higher_tree = Tree("roll_n", [1, 6])
        self.fireball_level_five_tree = Tree("roll_n", [10,6])
    
    def assertSimpleTreeEqual(self, a, b):
        if isinstance(a, Tree):
            a = SimplifyTransformer().transform(a)
        if isinstance(b, Tree):
            b = SimplifyTransformer().transform(b)
        self.assertEqual(a, b,
            "Trees are not equal\nTree a:\n%s\nTree b:\n%s" %(pprint(a), pprint(b)))

    def test_dice_weapon(self):
        initial_tree = Tree("value", [Token('WEAPON', 'Club')])
        final_tree = DnD5eKnowledge().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, self.club_tree)

    def test_spell_default(self):
        initial_tree = Tree("spell_default", [Token('SPELL_NAME', 'fireball')])
        final_tree = DnD5eKnowledge().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, self.fireball_tree)

    def test_spell_higher_level(self):
        initial_tree = Tree("spell", [Token('SPELL_NAME', 'fireball'), 5])
        final_tree = DnD5eKnowledge().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, self.fireball_level_five_tree)

    def test_spell_lower_level(self):
        initial_tree = Tree("spell", [Token('SPELL_NAME', 'fireball'), 1])
        with self.assertRaises(Exception):
            DnD5eKnowledge().transform(initial_tree)

    def test_spell_reverse(self):
        initial_tree = Tree("spell_reversed", [5, Token('SPELL_NAME', 'fireball')])
        final_tree = DnD5eKnowledge().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, self.fireball_level_five_tree)

    def test_const_weapon(self):
        initial_tree = Tree("value", [Token('WEAPON', 'Blowgun')])
        final_tree = DnD5eKnowledge().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, 1)

    def test_weapon_wrong_case(self):
        initial_tree = Tree("value", [Token('WEAPON', 'cLuB')])
        final_tree = DnD5eKnowledge().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, self.club_tree)

    def test_unknown_weapon(self):
        initial_tree = Tree("value", [Token('WEAPON', 'sadfsdf')])
        with self.assertRaises(Exception):
            DnD5eKnowledge().transform(initial_tree)

    def test_unknown_spell(self):
        initial_tree = Tree("value", [Token('SPELL_NAME', 'sadfsdf')])
        with self.assertRaises(Exception):
            DnD5eKnowledge().transform(initial_tree)


if __name__ == '__main__':
    absltest.main()
