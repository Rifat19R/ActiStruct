from __future__ import annotations

"""Compatibility wrapper for the MoS2 direct-grid validation."""

from direct_grid_validation import main


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        sys.argv.extend(["run", "--system", "mos2"])
    main()
