#!/usr/bin/env python3
"""Portable entrypoint for Qing Plans V2."""

import sys

sys.dont_write_bytecode = True

from qing_plan.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
