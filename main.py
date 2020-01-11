#!/usr/bin/env python3

from absl import logging
from dialogflow_v2.types import WebhookRequest, WebhookResponse, Intent
from google.protobuf import json_format
import json
from lark import Lark, Transformer, v_args, Tree, Token
from lark.exceptions import LarkError, VisitError
from random import randint
import re
import sys
from typing import Sequence, Iterable, Tuple, Optional, Mapping, Any, TYPE_CHECKING
from copy import deepcopy

if TYPE_CHECKING:
    import flask


# Lark has recursion issues
if sys.getrecursionlimit() < 5000:
    sys.setrecursionlimit(5000)


class UnfulfillableRequestError(Exception):
    pass


class RecognitionError(UnfulfillableRequestError):
    pass


class ImpossibleSpellError(UnfulfillableRequestError):
    pass


NAMED_DICE = {
    "coin": 2,
    "pyramid": 4,
    "cube": 6,
    "tetrahedron": 8,
    "octahedron": 8,
    "decahedron": 10,
    "dodecahedron": 12,
    "icosahedron": 20,
    "saving throw": 20,
    "skill check": 20,
    "to hit": 20,
    "percentile": 100,
    "percent": 100
}


SPELLS = json.load(open("data/spells.json"))
WEAPONS = json.load(open("data/weapons.json"))


def pprint(obj: Any, depth: int = 0) -> str:
    out = ""
    if isinstance(obj, Tree):
        out = " "*depth + "- " + obj.data + ":\n"
        for child in obj.children:
            out += pprint(child, depth+1)
    elif isinstance(obj, Token):
        out += " "*depth + "- " + obj.type + ": " + obj.value + "\n"
    else:
        out += " "*depth + "- " + repr(obj) + "\n"
    return out


def list_to_lark_literal(literal_name: str, values: Iterable[str], case_sensitive=False) -> str:
    case_marker = "" if case_sensitive else "i"
    spec = f"\n{literal_name}:"
    spec += ("\n|").join(f"\"{v}\"{case_marker}" for v in values)
    return spec


GRAMMER = '''
start:  sum

%import common.INT
%ignore " "

_PLUS: "+"i
     | "plus"i
_MINUS: "-"i
      | "minus"i
_TIMES: "*"i
      | "times"i
      | "multiplied by"i
      | "multiplied with"i

sum: sum _PLUS mul -> add
   | sum _MINUS mul -> sub
   | mul -> value

mul: mul _TIMES value
   | value -> value

value: dice
     | critical
     | advantage
     | "("i sum ")"i
     | INT

critical: "critical"i "to"i? "hit"i? "with"? "a"? _damage
        | _damage -> value

_damage: WEAPON
       | spell

dice: _die -> roll_one
    | value _die -> roll_n

advantage: dice "with advantage"i
         | dice "with disadvantage"i -> disadvantage

_die: "d"i value
   | value "sided"i ("dice"i|"die"i)
   | NAMED_DICE

spell: SPELL_NAME -> spell_default
     | SPELL_NAME "at level" INT
     | "level" INT SPELL_NAME -> spell_reversed
'''
GRAMMER += list_to_lark_literal("NAMED_DICE", NAMED_DICE.keys())
GRAMMER += list_to_lark_literal("WEAPON", (w["name"] for w in WEAPONS))
GRAMMER += list_to_lark_literal("SPELL_NAME", (s["name"] for s in SPELLS))


@v_args(inline=True)
class NumberTransformer(Transformer):
    def __init__(self):
        super().__init__(visit_tokens=True)

    def NAMED_DICE(self, name):
        return NAMED_DICE[name]

    INT=int


@v_args(tree=True)
class SimplifyTransformer(NumberTransformer):
    def value(self, tree):
        return tree.children[0]

    def roll_one(self, tree):
        return Tree('roll_n', [1, tree.children[0]])

    def sum(self, tree):
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

    def find_named_object(self, name: str, l: Iterable[Mapping[Any, Any]]) -> Mapping[Any, Any]:
        try:
            return next(filter(lambda i: i["name"].lower() == name.lower(), l))
        except StopIteration:
            raise RecognitionException(f"Sorry, I don't know what {name} is") from None

    def WEAPON(self, name) -> Tree:
        weapon = self.find_named_object(name, WEAPONS)
        dice_spec = weapon["damage_dice"]
        parser = Lark(GRAMMER)
        tree = parser.parse(dice_spec, start="sum")
        logging.debug("weapon %s has damage dice %s parsed as:\n%s",
                      name, dice_spec, pprint(tree))
        return tree

    def spell(self, spell: Mapping[str, Any], level: int) -> Tree:
        spell_tree = self.spell_default(spell)
        if level < spell["level_int"]:
            raise ImpossibleSpellError("Sorry, %s is level %d, so I can't cast it at level %d" %
            (spell["name"], spell["level_int"], level))
        m = re.search(r"\d+d\d+( + \d+)?", spell["higher_level"])
        if not m:
            raise ImpossibleSpellError("Sorry, I could't determine the additional damage dice for %s" % spell["name"])
        parser = Lark(GRAMMER)
        higher_level_tree = parser.parse(m.group(0), start="sum")
        logging.debug("spell %s has damage dice %s per extra level parsed as:\n%s",
                      spell["name"], m.group(0), pprint(higher_level_tree))
        for level in range(level-spell["level_int"]):
            spell_tree = Tree('sum', [spell_tree, higher_level_tree])
        logging.debug("spell %s has complete parsed as:\n%s",
                      spell["name"], pprint(spell_tree))
        return spell_tree

    def spell_reversed(self, level: int, spell: Mapping[str, Any]) -> Tree:
        return self.spell(spell, level)

    def spell_default(self, spell: Mapping[str, Any]) -> Tree:
        m = re.search(r"\d+d\d+( \+ \d+)?", spell["desc"])
        if not m:
            raise ImpossibleSpellError(f"Sorry, I couldn't find the damage dice for %s" % spell["name"])
        parser = Lark(GRAMMER)
        tree = parser.parse(m.group(0), start="sum")
        logging.debug("spell %s has base damage dice %s parsed as:\n%s",
                      spell["name"], m.group(0), pprint(tree))
        return tree

    def SPELL_NAME(self, name):
        return self.find_named_object(name, SPELLS)


@v_args(tree=True)
class CritTransformer(Transformer):
    def critical(self, tree):
        if tree.data == "roll_n":
            logging.debug("critical is doubling %dd%d", tree.children[0], tree.children[1])
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
        return max(a,b)

    def min(self, a, b):
        return min(a,b)


def roll(dice_spec: str) -> Tuple[int, Sequence[int]]:
        parser = Lark(GRAMMER)
    try:
        tree = parser.parse(dice_spec)
    except LarkError as e:
        raise RecognitionError("Sorry, I couldn't understand your request") from e
    logging.debug("Initial parse tree:\n%s", pprint(tree))
    try:
        tree = NumberTransformer().transform(tree)
        tree = DnD5eKnowledge().transform(tree)
        tree = SimplifyTransformer().transform(tree)
        tree = CritTransformer().transform(tree)
        logging.debug("DnD transformed parse tree:\n%s", pprint(tree))
        transformer = EvalDice()
        tree = transformer.transform(tree)
        tree = SimplifyTransformer().transform(tree)
    except: VisitError as e:
        #  Get our nice exception out of lark's wrapper
        raise e.orig_exc
    return (tree.children[0], transformer.dice_results)



def describe_dice(dice_results: Sequence[int]) -> str:
    if len(dice_results) <= 1:
        return ""
    description = " from "
    description += ", ".join(str(d) for d in dice_results[:-1])
    description += " and " + str(dice_results[-1])
    return description


def add_fulfillment_messages(
        res: WebhookResponse, display_text: str,
        ssml: Optional[str] = None, suggestions: Sequence[str] = None):
    res.fulfillment_messages.add().text.text.append(display_text)

    if ssml:
        fulfillment_message = res.fulfillment_messages.add()
        fulfillment_message.platform = Intent.Message.ACTIONS_ON_GOOGLE
        sr = fulfillment_message.simple_responses.simple_responses.add()
        sr.ssml = ssml
        sr.display_text = display_text

    if suggestions:
        fulfillment_message = res.fulfillment_messages.add()
        fulfillment_message.platform = Intent.Message.ACTIONS_ON_GOOGLE
        for suggestion in suggestions:
            fulfillment_message.suggestions.suggestions.add().title = "Re-roll"


def handleRoll(req: WebhookRequest, res: WebhookResponse):
    dice_spec = req.query_result.parameters["dice_spec"]
    logging.info("Requested roll: %s", dice_spec)
    roll_result, dice_results = roll(dice_spec)
    logging.info("Final result: %s", roll_result)
    dice_description = describe_dice(dice_results)
    add_fulfillment_messages(
        res,
        f"You rolled a total of {roll_result}{dice_description}",
        f"<speak><audio src=\"https://actions.google.com/sounds/v1/impacts/wood_rolling_short.ogg\"/>You rolled a total of {roll_result}</speak>",
        ["Re-roll"]
    )
    context = res.output_contexts.add()
    context.name = req.session + "/contexts/roll-followup"
    context.lifespan_count = 2
    context.parameters["roll_result"] = roll_result
    context.parameters["dice_results"] = dice_results


def handleHttp(request: 'flask.Request') -> str:
    req = WebhookRequest()
    res = WebhookResponse()
    try:
        json_format.Parse(request.data, req, ignore_unknown_fields=True)
        if req.query_result.action == "roll":
            handleRoll(req, res)
    except UnfulfillableRequestError as e:
        logging.exception(e)
        add_fulfillment_messages(res, str(e))
    return json_format.MessageToJson(res)


if __name__ == '__main__':
    print(roll(" ".join(sys.argv[1:]))[0])
