#!/usr/bin/env python3
"""Ziggurat's command line, runnable straight from a checkout.

The implementation lives in `ziggurat.cli` so that an installed console script
and a SPIndlebox plugin can share it verbatim. This file stays because it is
what other projects invoke by path, and because the tool must keep working with
nothing installed at all -- a checkout and a Python is the whole requirement.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ziggurat.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
