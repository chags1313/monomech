# GitHub Setup Guide

This repository is already configured for GitHub, GitHub Actions, GitHub Pages, and PyPI Trusted Publishing. Use this page as the maintenance checklist for repository settings.

## Repository

Repository:

```text
https://github.com/chags1313/monomech
```

Recommended settings:

- Issues enabled
- Actions enabled
- Pages source set to GitHub Actions
- branch protection on `main` once the release flow is stable

## Branch Protection

For `main`, consider requiring:

- CI
- Publish distributions build job
- Docs build once documentation is ready to gate releases
- pull request review before merge

Avoid force pushes to `main`. Force-updating release tags should be reserved for cases where the tag workflow failed before publishing any artifact.

## GitHub Pages

The docs workflow publishes the MkDocs site to:

```text
https://chags1313.github.io/monomech/
```

To enable it:

1. Go to **Settings > Pages**.
2. Set **Source** to **GitHub Actions**.
3. Push to `main`.
4. Confirm the Docs workflow succeeds.

## PyPI Trusted Publishing

PyPI publishing uses OpenID Connect through GitHub Actions. No long-lived PyPI token is required.

Configure the PyPI project with:

- owner: `chags1313`
- repository: `monomech`
- workflow filename: `publish.yml`
- environment: blank, unless the workflow is changed to use one

## Repository Health Files

The repository includes:

- `README.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `CHANGELOG.md`
- `.github/workflows/`

Keep these files current as the package API and release process evolve.
