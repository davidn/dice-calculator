#!/bin/sh
PATH="$PATH:$HOME/.local/bin" python3 -m pytype main.py util.py transformers.py parser.py exceptions.py dice_calculator.py
