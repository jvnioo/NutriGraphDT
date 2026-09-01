# Development Guide

## Requirements

- Git
- Python 3.11 or newer
- A local virtual environment

GPU/CUDA support is **not required** for the repository foundation. Hardware-specific setup will be documented only when model training requirements are known.

## Setup

```bash
git clone https://github.com/jvnioo/NutriGraphDT.git
cd NutriGraphDT
python -m venv .venv
```

Activate the environment:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install development tools:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
pre-commit install
```

## Quality checks

The authoritative baseline is local and requires no hosted or billable runner.

Run the checks directly:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

Or use the convenience script:

```bash
# Linux/macOS
bash scripts/check.sh

# Windows PowerShell
.\scripts\check.ps1
```

To execute all configured pre-commit checks:

```bash
pre-commit run --all-files
```

A hosted CI service is not required for ordinary development or for reproducing the project's quality checks. This keeps validation compatible with the project's zero-cost baseline. If automation is evaluated later, it must have a guaranteed no-billing path and a complete local fallback.

## Development workflow

Work through short-lived branches and Pull Requests. See `CONTRIBUTING.md` for naming and commit conventions.

AI-assisted contributors should also read `AGENTS.md` and `docs/ai/README.md`.

## Adding scientific/ML dependencies

Core scientific dependencies such as PyTorch, PyTorch Geometric, data-processing libraries, API frameworks, or visualization libraries will be added when their corresponding phase begins and compatibility requirements have been evaluated.

This avoids prematurely pinning GPU builds or scientific packages before the team has validated the environment and research requirements.

## Experiment tracking

The default experiment-tracking approach must remain free and reproducible. Structured JSON/CSV files and versioned configuration are valid baseline mechanisms. An open-source locally hosted tracker may be evaluated later if the project needs one.

A hosted commercial experiment tracker must never be required to run or reproduce the project.

## Data

Do not commit large raw datasets directly to Git. Dataset acquisition and preprocessing scripts should eventually provide enough information to reproduce the local data layout when licensing permits.

Each external dataset should record at least:

- source;
- version or retrieval date;
- license/terms;
- checksum where practical;
- preprocessing steps;
- whether the data are real, synthetic, or simulated.
