# GitHub Pages documentation site

This repository is configured to publish a documentation website with **MkDocs** and a **GitHub Actions Pages workflow**.

## Files involved

- `mkdocs.yml` — site configuration and navigation
- `docs/requirements.txt` — docs-site Python dependencies
- `.github/workflows/docs.yml` — build and deploy workflow
- `docs/` — Markdown source for the site

## Local preview

```bash
python -m pip install -r docs/requirements.txt
mkdocs serve
```

Then open `http://127.0.0.1:8000/`.

## Production publish flow

1. Push the repository to GitHub.
2. In **Settings → Pages**, set **Source** to **GitHub Actions**.
3. Push to `main`.
4. GitHub Actions builds the site and deploys it to Pages.

## Expected docs URL

For a repository named `monomech` under your personal account, the site URL is typically:

- `https://your-github-username.github.io/monomech/`

## Notes

- The workflow builds docs on pull requests for validation.
- It only deploys on non-PR events.
- Update the placeholder GitHub username in `mkdocs.yml` and `pyproject.toml` before publishing.
