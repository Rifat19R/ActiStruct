from __future__ import annotations

"""Compatibility wrapper for the production-matched LiCoO2 grid validation."""

from direct_grid_validation import main


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        sys.argv.extend(["run", "--system", "bulk_licoo2_matched"])
    main()
