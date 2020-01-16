#!/usr/bin/env python3

import json
from lark import Lark
import sys
from typing import Iterable

# Lark has recursion issues
if sys.getrecursionlimit() < 5000:
    sys.setrecursionlimit(5000)


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
    "death saving throw": 20,
    "percentile": 100,
    "percent": 100
}


SPELLS = json.load(open("data/spells.json"))
WEAPONS = json.load(open("data/weapons.json"))


def list_to_lark_literal(
        literal_name: str, values: Iterable[str], case_sensitive=False) -> str:
    case_marker = "" if case_sensitive else "i"
    spec = f"\n{literal_name}:"
    spec += ("\n|").join(f"\"{v}\"{case_marker}" for v in values)
    return spec


GRAMMER = '''
start:  sum

%import common.INT
%ignore " "
%ignore ","

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
     | SPELL_NAME "at level"i INT
     | SPELL_NAME "at"? INT _ORDINAL "level"i
     | "level" INT SPELL_NAME -> spell_reversed
     | INT _ORDINAL "level" SPELL_NAME -> spell_reversed
_ORDINAL: "st"i | "nd"i | "rd"i | "th"i
'''
GRAMMER += list_to_lark_literal("NAMED_DICE", NAMED_DICE.keys())
GRAMMER += list_to_lark_literal("WEAPON", (w["name"] for w in WEAPONS))
GRAMMER += list_to_lark_literal("SPELL_NAME", (s["name"] for s in SPELLS))

PARSER = Lark(GRAMMER)
