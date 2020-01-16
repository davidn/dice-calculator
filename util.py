#!/usr/bin/env python3

from lark import Tree, Token
from typing import Any


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
