# FAQ and troubleshooting

## Can I just push to GitHub and have it publish to PyPI?

Not immediately.

You first need to configure TestPyPI and PyPI to trust the GitHub Actions workflow described in [PUBLISHING.md](PUBLISHING.md). After that, pushes to `main` can go to TestPyPI and version tags can go to PyPI.

## Do I need a PyPI token in GitHub secrets?

Not for Trusted Publishing. The included workflow is designed to use GitHub's OIDC flow instead.

## Why does the release fail with "version already exists"?

PyPI does not allow overwriting an existing file for the same version. Bump the version in `pyproject.toml`, rebuild, and publish again.

## Why does TestPyPI install fail?

Common reasons:

- the package was not actually published
- the Python version is unsupported
- a required dependency is not available in the target environment
- you forgot to include the real PyPI index as an extra index URL

## Why are there both `.trc`/`.mot`/`.sto` files and CSVs?

The OpenSim-native files are needed for biomechanics tools and reproducible OpenSim runs. The CSV companions make inspection, debugging, and notebook analysis easier.

## What should I edit before making the repo public?

At minimum:

- `pyproject.toml` metadata
- repository URLs
- author information
- package version
- any placeholder names in docs

## Where should users start?

Point them to:

1. `README.md`
2. `examples/monomech_modular_pipeline.ipynb`
3. `examples/monomech_gatma_exact_model.ipynb`


## Why both GitHub Markdown docs and a docs site?

Because they serve slightly different use cases:

- GitHub repository visitors often land on `README.md`
- maintainers need durable Markdown guides in `docs/`
- users benefit from a searchable, navigable documentation website

This repository keeps the source in Markdown and uses MkDocs to publish it as a site.
