# Development guide

This guide is for working on the repository locally.

## Recommended environment

Use Python 3.11 or 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -e ".[dev]"
```

## Useful commands

Run tests:

```bash
pytest
```

Build the distributions:

```bash
python -m build
```

## Project layout

- `src/monomech/` — package source
- `tests/` — tests
- `examples/` — notebooks and examples
- `docs/` — repository and release docs
- `.github/workflows/` — CI and publishing automation

## Development expectations

- keep each stage modular
- preserve DataFrame-first outputs
- keep notebook workflows explicit and inspectable
- keep exports available in both biomechanics-native and CSV formats when applicable

## When changing stage outputs

If you change stage tables or artifacts:

1. update the relevant result object
2. update tests
3. update README output lists
4. update any example notebook cells that mention those outputs

## When changing publishing or GitHub automation

Update all of these together:

- `pyproject.toml`
- `.github/workflows/*.yml`
- `docs/GITHUB_SETUP.md`
- `docs/PUBLISHING.md`
- `docs/RELEASING.md`


## Docs development

Use the docs site locally while editing:

```bash
python -m pip install -r docs/requirements.txt
mkdocs serve
```

The docs site is the best place to keep installation, stage behavior, outputs, and release instructions in sync.
