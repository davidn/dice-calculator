#!/usr/bin/env python3

import sys
from pytype.tools.analyze_project.main import main

sys.argv = ["pytype", "main.py"]
sys.exit(main())
