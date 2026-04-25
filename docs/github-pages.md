# GitHub Pages Documentation Site

This repository publishes its documentation with MkDocs and GitHub Pages.

## Files Involved

- `mkdocs.yml` - site configuration and navigation
- `docs/requirements.txt` - documentation build dependencies
- `.github/workflows/docs.yml` - build and deploy workflow
- `docs/` - Markdown source files

## Local Preview

```bash
python -m pip install -r docs/requirements.txt
mkdocs serve
```

Then open `http://127.0.0.1:8000/`.

## Strict Build

The GitHub workflow uses strict mode. Run the same check locally:

```bash
mkdocs build --strict
```

Strict mode fails on broken links, missing navigation targets, and other documentation warnings.

## Production Publish Flow

1. In GitHub, go to **Settings > Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Push to `main`.
4. The Docs workflow builds and deploys the site.

## Site URL

The configured site URL is:

```text
https://chags1313.github.io/monomech/
```

## Notes

- Pull requests build the docs for validation.
- Pushes to `main` build and deploy the site.
- Keep `mkdocs.yml` navigation in sync whenever files are added, moved, or removed.
