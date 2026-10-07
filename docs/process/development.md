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

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

To execute all configured pre-commit checks:

```bash
pre-commit run --all-files
```

## Development workflow

Work through short-lived branches and Pull Requests. See `CONTRIBUTING.md` for naming and commit conventions.

## Adding scientific/ML dependencies

Core scientific dependencies such as PyTorch, PyTorch Geometric, data-processing libraries, API frameworks, or visualization libraries will be added when their corresponding phase begins and compatibility requirements have been evaluated.

This avoids prematurely pinning GPU builds or scientific packages before the team has validated the environment and research requirements.

### Optional `graph` extra (PyTorch and PyTorch Geometric)

The tensor validator (VG-05, `nutrigraphdt.graph.validation.tensors`) and its tests need
PyTorch and PyTorch Geometric. They are declared as the optional `graph` extra, so the data
layer and the record validators keep working without them. Install the CPU build of PyTorch
first; otherwise pip may download the much larger CUDA wheels:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev,graph]"
```

Without the extra, `pytest` skips the tensor tests and reports them as skipped.
Set `NUTRIGRAPHDT_REQUIRE_GRAPH=1` before running `pytest` to make it stop with a usage error
when the extra is missing, so the HeteroData tests can never be skipped silently. Use it when
checking a change that touches graphs or tensors.

`tests/unit/test_heterodata_flow.py` (A35-3, #30) covers the synthetic dataset -> `HeteroData`
flow on the `minimal_synthetic_dataset` fixture from `tests/conftest.py`: one instance with a
few nodes per type and every allowed relation at probability 1. It checks hand-computed node and
edge counts per type, tensor dimensions, and the absence of NaN, including after the JSONL
export and the `.pt` round trip.

The extra requires `torch-geometric>=2.7`, the version cited by the synthetic dataset
contract, and was verified with torch 2.13.0 (CPU) and torch-geometric 2.8.0. The HeteroData
prototype (`nutrigraphdt.graph.heterodata`, #28) uses the same extra; a future constructor that
needs another version must update the extra in the same Pull Request.

`mypy` checks against Python 3.11 (`python_version` in `pyproject.toml`, the minimum supported
version).
On Python 3.12 or newer, pip installs numpy 2.5 or newer, whose type stubs use Python 3.12
syntax that mypy rejects when targeting 3.11. Type-check with Python 3.11, or install
`numpy<2.5` in that environment.

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
