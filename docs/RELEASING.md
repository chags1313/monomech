# Release guide

This is the practical release checklist for maintainers.

## Pre-release checklist

- [ ] all intended code is merged into `main`
- [ ] tests pass locally
- [ ] CI passes on GitHub
- [ ] `README.md` matches the current public API
- [ ] notebooks still reflect the current workflow
- [ ] `CHANGELOG.md` is updated
- [ ] version in `pyproject.toml` is updated

## Dry run

Before a real release:

1. push `main`
2. confirm CI passes
3. confirm TestPyPI publish succeeds
4. install from TestPyPI in a fresh environment
5. run a smoke test import

Example:

```bash
python -m venv /tmp/monomech-smoke
source /tmp/monomech-smoke/bin/activate
python -m pip install --upgrade pip
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple monomech
python -c "import monomech; print(monomech.__version__)"
```

## Release steps

```bash
git checkout main
git pull
git tag v0.4.0
git push origin v0.4.0
```

Then:

- watch the publish workflow
- verify the new version on PyPI
- verify `pip install monomech` works

## Post-release checklist

- [ ] create a GitHub Release entry
- [ ] copy the key notes from `CHANGELOG.md`
- [ ] verify installation from PyPI
- [ ] verify documentation links still work

## Hotfix flow

For a packaging-only or release-only fix:

1. make the smallest possible change
2. bump the version
3. update `CHANGELOG.md`
4. tag and release again


## Release checklist for docs

Before tagging a release:

- preview docs locally with `mkdocs serve`
- ensure navigation reflects the current API
- update version references in docs if needed
- confirm the Pages workflow passes on `main`
- confirm the PyPI publish workflow still matches the project metadata
