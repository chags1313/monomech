# Releasing

Use this checklist for every PyPI release.

## Before Tagging

- [ ] version in `pyproject.toml` is updated
- [ ] `CHANGELOG.md` has a release section
- [ ] README examples match the current public API
- [ ] docs build locally with `mkdocs build --strict`
- [ ] tests pass with `pytest`
- [ ] package builds with `python -m build`
- [ ] PyPI Trusted Publisher is configured for `.github/workflows/publish.yml`

## Local Smoke Test

```bash
python -m build
python -m venv .venv-smoke
.venv-smoke\Scripts\python -m pip install dist\monomech-0.15.1-py3-none-any.whl
.venv-smoke\Scripts\python -c "import monomech as mm; print(mm.list_builtin_osim_models())"
```

## Tag the Release

```bash
git checkout main
git pull
git tag v0.15.1
git push origin v0.15.1
```

## Watch GitHub Actions

Confirm:

- the tag-triggered `Publish distributions` run starts
- `Build distributions` succeeds
- `Publish to PyPI` succeeds

## After Publishing

```bash
python -m venv .venv-pypi-check
.venv-pypi-check\Scripts\python -m pip install monomech==0.15.1
.venv-pypi-check\Scripts\python -c "import monomech as mm; print(mm.list_builtin_osim_models())"
```

Then create a GitHub Release using the notes from `CHANGELOG.md`.

## Hotfixes

For release-only fixes:

1. make the smallest safe change
2. bump the patch version
3. update the changelog
4. run tests and build locally
5. push `main`
6. push the new version tag
