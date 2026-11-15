# Phase 1 — GitHub Repository & Development Environment Setup

## Confirmed baseline

- GitHub account: `AnderCruz`
- Repository name: `customer-churn-prediction-clv`
- Python: 3.12
- Development style: local-first
- Project package: `nowa_customer_intelligence`
- Default branch: `main`
- Integration branch: `develop` (optional; use if preferred workflow requires it)

## A. Create the GitHub repository

The connected GitHub capability can inspect and modify files in accessible repositories, but it does not expose a repository-creation operation in this workspace. Create the empty repository in GitHub:

1. Open GitHub and choose **New repository**.
2. Repository name: `customer-churn-prediction-clv`.
3. Description: `Predictive customer intelligence for churn, CLV and customer segmentation.`
4. Visibility: **Private** is recommended during development.
5. Do not initialise with README, `.gitignore`, or licence because this scaffold already contains them.
6. Create the repository.

## B. Prepare the local environment (Ubuntu 24.04)

From the directory where you keep your projects:

```bash
mkdir -p ~/projects
cd ~/projects
```

Extract the supplied project scaffold ZIP into `~/projects/`. Then:

```bash
cd ~/projects/customer-churn-prediction-clv

python3.12 --version
git --version

python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If `python3.12` is not installed, install it using the supported Ubuntu package/repository method for your machine. Do not change the project Python target without updating `pyproject.toml` and CI.

## C. Validate the scaffold

```bash
ruff check .
ruff format --check .
pytest --cov=nowa_customer_intelligence --cov-report=term-missing
```

Expected initial test result: one test passes. The test suite will grow as modules are implemented.

## D. Initialise Git and connect the remote

Replace `<YOUR_GITHUB_USERNAME>` only if the authenticated account is not `AnderCruz`.

```bash
git init
git branch -M main
git add .
git status
git commit -m "chore: initialise Nowa Customer Intelligence project"

git remote add origin https://github.com/AnderCruz/customer-churn-prediction-clv.git
git push -u origin main
```

If Git is already configured for SSH, use the SSH remote instead:

```bash
git remote add origin git@github.com:AnderCruz/customer-churn-prediction-clv.git
```

Do not commit `.venv`, `.env`, raw client data, model artefacts, or credentials.

## E. Verify GitHub Actions

After the first push:
1. Open the repository's **Actions** tab.
2. Confirm the CI workflow starts.
3. Confirm lint, formatting, and tests pass.
4. If the workflow fails, inspect the failing step before changing configuration.

## F. Phase 1 completion checklist

- [ ] Empty private GitHub repository created.
- [ ] Scaffold extracted into the local projects directory.
- [ ] Python 3.12 virtual environment created.
- [ ] Project installed in editable mode.
- [ ] Ruff checks pass.
- [ ] Pytest passes.
- [ ] Git initialised and first commit created.
- [ ] Remote configured and `main` pushed.
- [ ] GitHub Actions CI passes.
- [ ] No private data, credentials, or local artefacts committed.

## G. Completion evidence to report

Send back:
- Output of `python --version`.
- Output of `git status`.
- Output of `pytest`.
- GitHub repository URL.
- GitHub Actions status.

Do not paste access tokens, passwords, private keys, or `.env` contents.
