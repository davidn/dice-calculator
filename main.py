from dialogflow_v2.types import WebhookRequest, WebhookResponse
from google.protobuf import json_format
from lark import Lark, Transformer, v_args
import logging
from random import randint
import sys

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
NAMED_DICE: "coin"i
          | "pyramid"i
          | "tetrahedron"i
          | "octahedron"i
          | "cube"i
          | "decahedron"i
          | "dodecahedron"i
          | "icosahedron"i
          | "to hit"i
          | "saving throw"i
          | "skill check"i
          | "percentile"i
          | "percent"i

die: "d"i value
    | value "sided"i ("dice"i|"die"i)
    | NAMED_DICE

dice: die -> roll_one
    | value die -> roll_n

value: dice
     | "("i value ")"i
     | INT
     | sum

sum: sum _PLUS mul -> add
    | sum _MINUS mul -> sub
    | mul -> value

mul: mul _TIMES value
   | value -> value
'''

@v_args(inline=True)
class EvalDice(Transformer):
  
  def __init__(self):
    super().__init__(visit_tokens=True)
    self.dice_results = []
    
  INT=int

  def value(self, x):
    return x
  
  die=value

  def roll_one(self, sides):
    res = randint(1,sides)
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


def roll(dice_spec):
    l = Lark(GRAMMER)
    tree =  l.parse(dice_spec)
    transformer = EvalDice()
    logging.debug("Parse tree: %r", tree)
    transformed_tree = transformer.transform(tree)
    return (transformed_tree.children[0], transformer.dice_results)

def handleRoll(req, res):
    dice_spec = req.query_result.parameters["dice_spec"]
    logging.info("Requested roll: %s", dice_spec)
    roll_result, dice_results = roll(dice_spec)
    logging.info("Final result: %s", roll_result)
    res.fulfillment_text = "Result {dice_results} for a total of {roll_result}".format(
        roll_result=roll_result,
        dice_results=", ".join(str(d) for d in dice_results)
    )
    context = res.output_contexts.add()
    context.name = req.session + "/contexts/roll-followup"
    context.lifespan = 2
    context.parameters["dice_results"] = dice_results
    res.payload["google"] = {
        "expectUserResponse": False,
        "richResponse": {
            "items": [
                {
                     "simpleResponse": {
                         "textToSpeech": f"<speak><audio src=\"https://actions.google.com/sounds/v1/impacts/wood_rolling_short.ogg\"/>You rolled {roll_result}</speak>",
                         "displayText": res.fulfillment_text
                     }
                }
            ],
            "suggestions": [
              {
                  "title": "Re-roll"
              }
            ]
        }
    }

def handleHttp(request):
    req = WebhookRequest()
    res = WebhookResponse()
    json_format.Parse(request.data, req)
    if req.query_result.action == "roll":
        handleRoll(req, res)

    return json_format.MessageToJson(res)
