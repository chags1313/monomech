# GitHub setup guide

Use this guide when you first create the GitHub repository.

## 1. Create the repository

Create a new GitHub repository, then push the project:

```bash
git init
git add .
git commit -m "Initial monomech release"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/monomech.git
git push -u origin main
```

## 2. Update repository metadata

Before making the repo public, update:

- `pyproject.toml`
  - author name
  - author email
  - homepage URL
  - repository URL
  - documentation URL
  - issues URL
- `README.md`
  - badges if you want them
  - example install commands if the package name changes

## 3. Configure repository settings

Recommended GitHub settings:

### General
- enable Issues
- enable Discussions if you want design conversations in GitHub
- enable Projects only if you plan to use them

### Branch protection
Protect `main`:
- require pull request before merging
- require status checks to pass
- prevent force pushes

### Actions
Allow GitHub Actions to run the included workflows.

## 4. Secrets and credentials

With Trusted Publishing, you do not need a long-lived PyPI token stored in GitHub.

Still avoid committing:
- API keys
- real credentials
- local paths
- notebooks containing secrets

## 5. Repository health files already included

This project includes:

- `README.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `.github/ISSUE_TEMPLATE/`
- `.github/PULL_REQUEST_TEMPLATE.md`

These make the repository easier to use immediately after publishing.

## 6. First checks after pushing

After the first push, confirm:

- the CI workflow appears in GitHub Actions
- README renders correctly
- issue templates appear when creating an issue
- links in docs point to the right repo name


## Enable the GitHub Pages docs site

After the repository is on GitHub:

1. Go to **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Push to `main`.
4. Confirm `.github/workflows/docs.yml` runs successfully.
5. Open the published site URL shown in the workflow or Pages settings.

## Replace placeholders before going live

Update these placeholders first:

- `your-github-username` in `mkdocs.yml`
- `your-github-username` in `pyproject.toml`
- author name and email in `pyproject.toml`
- optional custom domain settings if you plan to use one later
