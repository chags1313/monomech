# Documentation index

`monomech` now ships with a **GitHub Pages documentation site** powered by MkDocs.

## Local docs preview

```bash
python -m pip install -r docs/requirements.txt
mkdocs serve
```

Then open `http://127.0.0.1:8000/`.

## Published docs site

Once GitHub Pages is enabled for this repository, the site will publish from the included GitHub Actions workflow to:

- `https://your-github-username.github.io/monomech/`

## What lives here

### Site-first pages
These are written to read well as a website:
- [index.md](index.md)
- [getting-started.md](getting-started.md)
- [examples.md](examples.md)
- [outputs.md](outputs.md)
- [gatma-model.md](gatma-model.md)
- [github-pages.md](github-pages.md)
- [stages/index.md](stages/index.md)

### Repository guides
These remain useful both on GitHub and in the docs site:
- [DEVELOPMENT.md](DEVELOPMENT.md)
- [GITHUB_SETUP.md](GITHUB_SETUP.md)
- [PUBLISHING.md](PUBLISHING.md)
- [RELEASING.md](RELEASING.md)
- [FAQ.md](FAQ.md)

## Recommended reading order

### I want to use the package
1. [index.md](index.md)
2. [getting-started.md](getting-started.md)
3. [examples.md](examples.md)
4. [outputs.md](outputs.md)

### I want to understand the pipeline design
1. [stages/index.md](stages/index.md)
2. stage-specific pages in `stages/`
3. [gatma-model.md](gatma-model.md)

### I want to publish and host the repo properly
1. [github-pages.md](github-pages.md)
2. [GITHUB_SETUP.md](GITHUB_SETUP.md)
3. [PUBLISHING.md](PUBLISHING.md)
4. [RELEASING.md](RELEASING.md)
