# Publishing

`monomech` publishes through GitHub Actions. The workflow builds distributions on pushes to `main` and publishes to PyPI only when a version tag is pushed.

## Workflow

The publishing workflow lives at:

```text
.github/workflows/publish.yml
```

It has two jobs:

- `build`: builds the wheel and source distribution
- `publish-pypi`: publishes to PyPI when `github.ref` starts with `refs/tags/v`

## Trusted Publishing

PyPI must trust this GitHub workflow before releases can publish.

Configure the PyPI project with:

- owner: `chags1313`
- repository: `monomech`
- workflow filename: `publish.yml`
- environment: `pypi`

If PyPI reports `invalid-pending-publisher` for an existing project, configure the Trusted Publisher on the existing PyPI project rather than creating a pending publisher for a new project.

## Release Command

After `main` is ready:

```bash
git tag v0.15.1
git push origin v0.15.1
```

GitHub Actions will build distributions from that tag and upload them to PyPI.

## Verify

```bash
python -m venv .venv-smoke
.venv-smoke\Scripts\python -m pip install --upgrade pip
.venv-smoke\Scripts\python -m pip install monomech
.venv-smoke\Scripts\python -c "import monomech as mm; print(mm.list_builtin_osim_models())"
```

On macOS/Linux, activate the environment with `source .venv-smoke/bin/activate` or call `.venv-smoke/bin/python`.

## Common Failures

| Failure | Meaning | Fix |
| --- | --- | --- |
| `invalid-pending-publisher` | PyPI project does not trust this workflow | Add or update the Trusted Publisher on PyPI |
| `invalid-publisher` with `environment: MISSING` | PyPI expects a GitHub environment claim | Keep `environment: pypi` on the publish job and configure the PyPI publisher with environment `pypi` |
| file already exists | version was already uploaded | bump `pyproject.toml` and tag a new version |
| metadata validation failed | package metadata is invalid | run `python -m build` locally and inspect output |
| build succeeds but publish does not run | push was not a `v*` tag | create and push a version tag |
