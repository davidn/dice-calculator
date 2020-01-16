#!/usr/bin/env python3

from absl import logging
from lark.exceptions import LarkError, VisitError
import sys
from typing import Sequence, Tuple
from opencensus.trace import execution_context

from parser import PARSER
from util import pprint
from exceptions import RecognitionError
from transformers import (
    NumberTransformer, SimplifyTransformer, DnD5eKnowledge, CritTransformer,
    EvalDice)


def roll(dice_spec: str) -> Tuple[int, Sequence[int]]:
    tracer = execution_context.get_opencensus_tracer()
    try:
        with tracer.span('initial_parse'):
            tracer.add_attribute_to_current_span("dice_spec", dice_spec)
            tree = PARSER.parse(dice_spec)
    except LarkError as e:
        raise RecognitionError(
            "Sorry, I couldn't understand your request") from e
    logging.debug("Initial parse tree:\n%s", pprint(tree))
    try:
        tree = NumberTransformer().transform(tree)
        with tracer.span('dnd_knowledge'):
            tree = DnD5eKnowledge().transform(tree)
        tree = SimplifyTransformer().transform(tree)
        with tracer.span('crit_transform'):
            tree = CritTransformer().transform(tree)
        logging.debug("DnD transformed parse tree:\n%s", pprint(tree))
        with tracer.span('final_eval'):
            transformer = EvalDice()
            tree = transformer.transform(tree)
        tree = SimplifyTransformer().transform(tree)
    except VisitError as e:
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


if __name__ == '__main__':
    print(roll(" ".join(sys.argv[1:]))[0])
