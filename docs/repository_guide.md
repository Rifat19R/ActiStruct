# Repository Guide

## Track in Git

- source scripts,
- tests,
- documentation,
- requirements,
- citation metadata,
- license.

## Ignore in Git

- `.venv/`,
- QE working directories,
- generated plots,
- generated reports,
- pickle caches,
- spreadsheet scratch files,
- `__pycache__/`.

## First Commit

```bash
cd /mnt/d/Rifat_kh/inverse_active
git status
git add .
git commit -m "Initial active learning inverse design workflows"
```

## GitHub Remote

```bash
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

## Before arXiv

- Freeze software versions.
- Export final plots.
- Record QE version.
- Record pseudopotential checksums.
- Decide final benchmark budgets.
- Rerun all workflows from clean caches.
- Update `CITATION.cff` with final author metadata.
