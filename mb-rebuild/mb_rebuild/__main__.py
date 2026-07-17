"""Enable `python -m mb_rebuild`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
