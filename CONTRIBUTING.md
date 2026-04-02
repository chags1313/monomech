# Contributing to monomech

Thanks for contributing.

This guide is written so a new contributor can get from zero to a clean pull request without guessing.

## What to read first

1. [README.md](README.md)
2. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
3. [docs/FAQ.md](docs/FAQ.md)

If your change affects publishing or repository automation, also read:
- [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md)
- [docs/PUBLISHING.md](docs/PUBLISHING.md)
- [docs/RELEASING.md](docs/RELEASING.md)

## Development setup

Create and activate a Python 3.11 or 3.12 environment.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -e ".[dev]"
```

## Branching

Use short topic branches:

- `feature/<name>`
- `fix/<name>`
- `docs/<name>`
- `refactor/<name>`

Examples:

- `feature/opensim-scaling-qc`
- `docs/release-checklist`
- `fix/trc-header-export`

## Making changes

### Code changes
- keep stage APIs modular
- preserve notebook-first ergonomics
- prefer explicit DataFrame outputs over opaque side effects
- add tests when changing behavior
- update docs when public APIs change

### Documentation changes
- update the closest file to the user-facing workflow
- keep examples runnable
- keep filenames and commands copy-paste friendly

## Run checks before opening a PR

```bash
pytest
```

If you changed packaging, also run:

```bash
python -m build
```

## Pull request checklist

Before opening a PR, confirm:

- [ ] tests pass locally
- [ ] documentation was updated if needed
- [ ] any new public API is shown in README or docs
- [ ] notebooks still make sense with the new API
- [ ] outputs remain clear in both native biomechanics files and CSVs

## What makes a good PR

A good PR includes:

- a short summary of the problem
- the reason for the chosen solution
- clear notes about user-visible changes
- any follow-up work that remains

## Reporting bigger design ideas

If the change affects library architecture, open an issue first and describe:

- current pain point
- proposed API
- expected notebook workflow
- expected outputs and artifacts

That helps keep the public API coherent.


## Working on documentation

The repository includes a GitHub Pages docs site powered by MkDocs.

```bash
python -m pip install -r docs/requirements.txt
mkdocs serve
```

Please update docs when you change:
- installation steps
- stage outputs
- file formats
- GitHub, release, or publishing workflows
