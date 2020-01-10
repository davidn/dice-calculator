#!/usr/bin/env python3

from absl import logging
from dialogflow_v2.types import WebhookRequest, WebhookResponse, Intent
from google.protobuf import json_format
import json
from lark import Lark, Transformer, v_args, Tree
from random import randint
from typing import Sequence, Iterable, Tuple, Optional, Mapping, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import flask

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


def list_to_lark_literal(literal_name: str, values: Iterable[str], case_sensitive=False) -> str:
    case_marker = "" if case_sensitive else "i"
    spec = f"\n{literal_name}:"
    spec += ("\n|").join(f"\"{v}\"{case_marker}" for v in values)
    return spec


GRAMMER = '''
start:  value

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

die: "d"i value
   | value "sided"i ("dice"i|"die"i)
   | NAMED_DICE

dice: die -> roll_one
    | value die -> roll_n

value: dice
     | WEAPON
     | "("i value ")"i
     | INT
     | sum

sum: sum _PLUS mul -> add
   | sum _MINUS mul -> sub
   | mul -> value

mul: mul _TIMES value
   | value -> value
'''
GRAMMER += list_to_lark_literal("NAMED_DICE", NAMED_DICE.keys())
GRAMMER += list_to_lark_literal("WEAPON", (w["name"] for w in WEAPONS))
# GRAMMER += list_to_lark_literal("SPELL", (s["name"] for s in SPELLS))


@v_args(inline=True)
class DnD5eKnowledge(Transformer):
    def __init__(self):
        super().__init__(visit_tokens=True)

    def find_named_object(self, name: str, l: Iterable[Mapping[Any, Any]]) -> Mapping[Any, Any]:
        return next(filter(lambda i: i["name"].lower() == name.lower(), l))

    def WEAPON(self, name):
        weapon = self.find_named_object(name, WEAPONS)
        dice_spec = weapon["damage_dice"]
        logging.debug("parsing damage dice %s for weapon %s", dice_spec, name)
        parser = Lark(GRAMMER)
        return parser.parse(dice_spec, start="value")


@v_args(inline=True)
class EvalDice(Transformer):
    def __init__(self):
        super().__init__(visit_tokens=True)
        self.dice_results = []

    INT = int

    def value(self, x):
        return x

    die = value

    def roll_one(self, sides):
        res = randint(1, sides)
        self.dice_results.append(res)
        logging.debug("Rolled d%d, got %d", sides, res)
        return res

    def roll_n(self, count, sides):
        return sum(self.roll_one(sides) for x in range(count))

    def NAMED_DICE(self, name):
        return NAMED_DICE[name]

    def add(self, a, b):
        return a+b

    def sub(self, a, b):
        return a-b

    def mul(self, a, b):
        return a*b


def roll(dice_spec: str) -> Tuple[int, Sequence[int]]:
    parser = Lark(GRAMMER)
    tree1 = parser.parse(dice_spec)
    logging.debug("Initial parse tree: %r", tree1)
    tree2 = DnD5eKnowledge().transform(tree1)
    logging.debug("DnD transformed parse tree: %r", tree2)
    transformer = EvalDice()
    tree3 = transformer.transform(tree2)
    return (tree3.children[0], transformer.dice_results)


def describe_dice(dice_results: Sequence[int]) -> str:
    if len(dice_results) <= 1:
        return ""
    description = " from "
    description += ", ".join(str(d) for d in dice_results[:-1])
    description += " and " + str(dice_results[-1])
    return description


def add_fulfillment_messages(res: WebhookResponse, display_text: Optional[str], ssml: Optional[str], suggestions: Sequence[str]):
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
    json_format.Parse(request.data, req, ignore_unknown_fields=True)
    if req.query_result.action == "roll":
        handleRoll(req, res)

    return json_format.MessageToJson(res)
