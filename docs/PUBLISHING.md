# Publishing monomech with GitHub Actions and Trusted Publishing

This repository is set up so that:

- pushes to `main` can publish to **TestPyPI**
- pushes of version tags like `v0.4.0` can publish to **PyPI**

## How publishing works

There are two workflows involved:

1. the CI workflow validates the project
2. the publish workflow builds the distributions and publishes them through GitHub Actions

Publishing is not automatic just because the code is on GitHub. You must first configure TestPyPI and PyPI to trust this repository's workflow.

## 1. Put the project on GitHub

Follow [GITHUB_SETUP.md](GITHUB_SETUP.md) first.

## 2. Replace metadata placeholders

Before publishing, update these values in `pyproject.toml`:

- author name
- author email
- homepage URL
- repository URL
- documentation URL
- issues URL
- version

## 3. Confirm the package name

Check whether `monomech` is available on both PyPI and TestPyPI.

If it is taken, change the project name before your first release.

## 4. Configure Trusted Publishers

### TestPyPI publisher

On TestPyPI, add a pending publisher with:

- owner: your GitHub user or org
- repository: your repository name
- workflow filename: `publish.yml`
- environment: `testpypi`
- project name: `monomech`

### PyPI publisher

On PyPI, add a pending publisher with:

- owner: your GitHub user or org
- repository: your repository name
- workflow filename: `publish.yml`
- environment: `pypi`
- project name: `monomech`

## 5. First test publish

Push to `main` or manually trigger the workflow.

That should build the package and publish it to TestPyPI.

Then verify:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple monomech
python -c "import monomech; print(monomech.__version__)"
```

## 6. Real release to PyPI

When the TestPyPI release looks good:

```bash
git tag v0.4.0
git push origin v0.4.0
```

That tag should trigger the PyPI publish job.

## 7. If publishing fails

Check, in order:

1. the GitHub Actions logs
2. the version number in `pyproject.toml`
3. that the package name matches the publisher configuration
4. that the repository owner, repo name, and workflow filename match exactly
5. that the PyPI project is not already using a different publisher


## Docs site deployment is separate from PyPI publishing

The repository includes two independent GitHub Actions flows:

- `.github/workflows/docs.yml` publishes the documentation site to GitHub Pages
- `.github/workflows/publish.yml` publishes package distributions to TestPyPI or PyPI

That separation is intentional. It keeps documentation failures from blocking local development, and it keeps release publishing explicit and auditable.
