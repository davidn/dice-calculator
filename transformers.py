#!/usr/bin/env python3

from absl import logging
from lark import Transformer, v_args, Tree
from random import randint
import re
from typing import Iterable, Mapping, Any
from copy import deepcopy
from opencensus.trace import execution_context

from parser import PARSER, SPELLS, WEAPONS, NAMED_DICE
from util import pprint
from exceptions import (ImpossibleSpellError, RecognitionError,
                        ImpossibleDiceError)


@v_args(inline=True)
class NumberTransformer(Transformer):
    def __init__(self):
        super().__init__(visit_tokens=True)

    def NAMED_DICE(self, name):
        return NAMED_DICE[name]

    INT = int


@v_args(tree=True)
class SimplifyTransformer(NumberTransformer):
    def value(self, tree):
        return tree.children[0]

    def roll_one(self, tree):
        return Tree('roll_n', [1, tree.children[0]])

    def add(self, tree):
        # check if we have a sum of dice roll
        if all(isinstance(child, Tree) and child.data == "roll_n"
               for child in tree.children):
            # check if all the dice are the same:
            die_size = tree.children[0].children[-1]
            if all(child.children[-1] == die_size for child in tree.children):
                num_dice = 0
                for roll in tree.children:
                    num_dice += roll.children[0]
                return Tree('roll_n', [num_dice, die_size])
        # no simplification possible
        return tree


@v_args(inline=True)
class DnD5eKnowledge(Transformer):
    def __init__(self):
        super().__init__(visit_tokens=True)

    def find_named_object(self, name: str,
                          l: Iterable[Mapping[Any, Any]]) -> Mapping[Any, Any]:
        try:
            return next(filter(lambda i: i["name"].lower() == name.lower(), l))
        except StopIteration:
            raise RecognitionError(
                f"Sorry, I don't know what {name} is") from None

    def WEAPON(self, name) -> Tree:
        tracer = execution_context.get_opencensus_tracer()
        weapon = self.find_named_object(name, WEAPONS)
        dice_spec = weapon["damage_dice"]
        with tracer.span('parse_weapon'):
            tracer.add_attribute_to_current_span("name", name)
            tracer.add_attribute_to_current_span("dice_spec", dice_spec)
            tree = PARSER.parse(dice_spec, start="sum")
        logging.debug("weapon %s has damage dice %s parsed as:\n%s",
                      name, dice_spec, pprint(tree))
        return tree

    def spell(self, spell: Mapping[str, Any], level: int) -> Tree:
        tracer = execution_context.get_opencensus_tracer()
        spell_tree = self.spell_default(spell)
        if level < spell["level_int"]:
            raise ImpossibleSpellError(
                "Sorry, %s is level %d, so I can't cast it at level %d" %
                (spell["name"], spell["level_int"], level))
        m = re.search(r"\d+d\d+( + \d+)?", spell["higher_level"])
        if not m:
            raise ImpossibleSpellError(
                "Sorry, I could't determine the additional damage dice for %s"
                % spell["name"])
        with tracer.span('parse_spell_additional'):
            tracer.add_attribute_to_current_span("name", spell["name"])
            tracer.add_attribute_to_current_span("dice_spec", m.group(0))
            higher_level_tree = PARSER.parse(m.group(0), start="sum")
        logging.debug(
            "spell %s has damage dice %s per extra level parsed as:\n%s",
            spell["name"], m.group(0), pprint(higher_level_tree))
        for level in range(level-spell["level_int"]):
            spell_tree = Tree('add', [spell_tree, higher_level_tree])
        logging.debug("spell %s has complete parsed as:\n%s",
                      spell["name"], pprint(spell_tree))
        return spell_tree

    def spell_reversed(self, level: int, spell: Mapping[str, Any]) -> Tree:
        return self.spell(spell, level)

    def spell_default(self, spell: Mapping[str, Any]) -> Tree:
        tracer = execution_context.get_opencensus_tracer()
        m = re.search(r"\d+d\d+( \+ \d+)?", spell["desc"])
        if not m:
            raise ImpossibleSpellError(
                f"Sorry, I couldn't find the damage dice for %s"
                % spell["name"])
        with tracer.span('parse_spell'):
            tracer.add_attribute_to_current_span("name", spell["name"])
            tracer.add_attribute_to_current_span("dice_spec", m.group(0))
            tree = PARSER.parse(m.group(0), start="sum")
        logging.debug("spell %s has base damage dice %s parsed as:\n%s",
                      spell["name"], m.group(0), pprint(tree))
        return tree

    def SPELL_NAME(self, name):
        return self.find_named_object(name, SPELLS)


@v_args(tree=True)
class CritTransformer(Transformer):
    def critical(self, tree):
        if tree.data == "roll_n":
            logging.debug("critical is doubling %dd%d",
                          tree.children[0], tree.children[1])
            tree.children[0] *= 2
        for i in range(len(tree.children)):
            if isinstance(tree.children[i], Tree):
                tree.children[i] = self.critical(tree.children[i])
        if tree.data == "critical":
            return tree.children[0]
        return tree

    def disadvantage(self, tree):
        return self.advantage(tree, 'min')

    def advantage(self, tree, operation='max'):
        for i in range(len(tree.children)):
            if isinstance(tree.children[i], Tree):
                tree.children[i] = self.advantage(tree.children[i], operation)
        if tree.data == "roll_n":
            tree = Tree(operation, [tree, deepcopy(tree)])
        if tree.data in ("advantage", "disadvantage"):
            return tree.children[0]
        return tree


@v_args(inline=True)
class EvalDice(Transformer):
    def __init__(self):
        super().__init__(visit_tokens=True)
        self.dice_results = []

    def roll_n(self, count, sides):
        sum = 0
        if count <= 0:
            raise ImpossibleDiceError(
                f"Sorry, I couldn't roll {count} dice.")
        if sides <= 0:
            raise ImpossibleDiceError(
                f"Sorry, I couldn't roll a {sides} sided die.")
        for _ in range(count):
            res = randint(1, sides)
            sum += res
            self.dice_results.append(res)
            logging.debug("Rolled d%d, got %d", sides, res)
        return sum

    def add(self, a, b):
        return a+b

    def sub(self, a, b):
        return a-b

    def mul(self, a, b):
        return a*b

    def max(self, a, b):
        return max(a, b)

    def min(self, a, b):
        return min(a, b)
