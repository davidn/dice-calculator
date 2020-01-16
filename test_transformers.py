#!/usr/bin/env python3

from transformers import (
    EvalDice, DnD5eKnowledge, SimplifyTransformer, CritTransformer)
from util import pprint
from exceptions import UnfulfillableRequestError
from absl.testing import absltest
from unittest import mock
from lark import Tree, Token
from lark.exceptions import VisitError


class TransformerTestCase(absltest.TestCase):
    def assertTreeEqual(self, a, b):
        self.assertEqual(
            a, b,
            "Trees are not equal\n"
            "Tree a:\n%s\nTree b:\n%s" % (pprint(a), pprint(b)))

    def assertSimpleTreeEqual(self, a, b):
        if isinstance(a, Tree):
            a = SimplifyTransformer().transform(a)
        if isinstance(b, Tree):
            b = SimplifyTransformer().transform(b)
        self.assertTreeEqual(a, b)


class CritTransformerTest(TransformerTestCase):
    def test_int(self):
        in_tree = Tree('critical', [
            1
        ])
        out_tree = CritTransformer().transform(in_tree)
        self.assertTreeEqual(out_tree, 1)

    def test_dice(self):
        in_tree = Tree('critical', [
            Tree('roll_n', [3, 4])
        ])
        out_tree = CritTransformer().transform(in_tree)
        self.assertTreeEqual(out_tree, Tree('roll_n', [6, 4]))

    def test_sum_dice(self):
        in_tree = Tree('critical', [
            Tree('add', [Tree('roll_n', [3, 4]), 2])
        ])
        out_tree = CritTransformer().transform(in_tree)
        self.assertTreeEqual(out_tree,
                             Tree('add', [Tree('roll_n', [6, 4]), 2]))


class SimplifyTransformerTest(TransformerTestCase):
    def test_collapse_value(self):
        in_tree = Tree('value', [1])
        out_tree = SimplifyTransformer().transform(in_tree)
        self.assertTreeEqual(out_tree, 1)

    def test_combine_roll_one(self):
        in_tree = Tree('add', [
            Tree('roll_one', [6]),
            Tree('roll_one', [6]),
        ])
        out_tree = SimplifyTransformer().transform(in_tree)
        self.assertTreeEqual(out_tree, Tree('roll_n', [2, 6]))

    def test_combine_roll_one_and_n(self):
        in_tree = Tree('add', [
            Tree('roll_one', [6]),
            Tree('roll_n', [2, 6]),
        ])
        out_tree = SimplifyTransformer().transform(in_tree)
        self.assertTreeEqual(out_tree, Tree('roll_n', [3, 6]))

    def test_combine_roll_n(self):
        in_tree = Tree('add', [
            Tree('roll_n', [3, 6]),
            Tree('roll_n', [2, 6]),
        ])
        out_tree = SimplifyTransformer().transform(in_tree)
        self.assertTreeEqual(out_tree, Tree('roll_n', [5, 6]))

    def test_no_combine_different(self):
        in_tree = Tree('add', [
            Tree('roll_n', [3, 4]),
            Tree('roll_n', [2, 6]),
        ])
        out_tree = SimplifyTransformer().transform(in_tree)
        self.assertTreeEqual(out_tree, in_tree)


class DnD5eKnowledgeTest(TransformerTestCase):
    def setUp(self):
        self.club_tree = Tree("roll_n", [1, 4])
        self.fireball_tree = Tree("roll_n", [8, 6])
        self.fireball_higher_tree = Tree("roll_n", [1, 6])
        self.fireball_level_five_tree = Tree("roll_n", [10, 6])

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
        initial_tree = Tree("spell_reversed",
                            [5, Token('SPELL_NAME', 'fireball')])
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


class DiceEvalTest(TransformerTestCase):
    def test_add(self):
        initial_tree = Tree("add", [2, 3])
        final_tree = EvalDice().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, 5)

    def test_sub(self):
        initial_tree = Tree("sub", [2, 3])
        final_tree = EvalDice().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, -1)

    def test_mul(self):
        initial_tree = Tree("mul", [2, 3])
        final_tree = EvalDice().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, 6)

    def test_max(self):
        initial_tree = Tree("max", [2, 3])
        final_tree = EvalDice().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, 3)

    def test_min(self):
        initial_tree = Tree("min", [2, 3])
        final_tree = EvalDice().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, 2)

    @mock.patch('transformers.randint')
    def test_roll_n(self, mock_randint):
        mock_randint.side_effect = range(1, 3)
        initial_tree = Tree("roll_n", [2, 3])
        final_tree = EvalDice().transform(initial_tree)
        self.assertSimpleTreeEqual(final_tree, 3)
        mock_randint.assert_has_calls([mock.call(1, 3)]*2)

    def test_roll_n_zero_sides(self):
        initial_tree = Tree("roll_n", [2, 0])
        with self.assertRaises(UnfulfillableRequestError):
            try:
                EvalDice().transform(initial_tree)
            except VisitError as e:
                raise e.orig_exc

    def test_roll_n_negative_count(self):
        initial_tree = Tree("roll_n", [-1, 3])
        with self.assertRaises(UnfulfillableRequestError):
            try:
                EvalDice().transform(initial_tree)
            except VisitError as e:
                raise e.orig_exc


if __name__ == '__main__':
    absltest.main()
