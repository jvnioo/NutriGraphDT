# NutriGraphDT

**Graph-Based Nutritional Digital Twin for In Silico Simulation of the Animal Gut Microbiome**

NutriGraphDT is the software and research framework developed within the academic project **Microbioma Digital (PIA 302)**. The project investigates the feasibility of a nutritional digital twin of the animal gastrointestinal tract using heterogeneous graphs, Graph Neural Networks (GNNs), scientifically informed biochemical constraints, simulation, and explainability.

> **Status:** delivery stage (F9). The full pipeline is implemented and reproducible: data
> contracts, heterogeneous graph construction and validation, baselines and GNNs, biochemical
> constraints, scenario simulation with uncertainty, explainability, a versioned API, and an
> experimental Streamlit web app. The platform and the delivery run on **synthetic data**; see
> [Data scope](#data-scope).

## Quick start

From a fresh clone to the web app, with measured times and troubleshooting, in the
[reproducibility guide](docs/process/reproducibility-guide.md) (in Spanish). In short:

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev,graph,baselines,demo]"
python -m pytest -m e2e -q                              # end-to-end suite of the web app
python scripts/run_delivery.py                          # synthetic pipeline → reports/delivery/
streamlit run scripts/demo_app.py                       # web app at http://localhost:8501
```

On Windows, clone into a short path (for example `C:\Users\<user>\NutriGraphDT`): PyTorch fails
to install under deep folders.

## Research objective

Develop and validate an academic prototype capable of representing a reduced gastrointestinal ecosystem as a heterogeneous graph and exploring *in silico* nutritional scenarios.

The planned pipeline progressively covers:

1. data contracts and heterogeneous graph schema;
2. data ingestion and graph construction;
3. baseline predictive models and GNN architectures;
4. biochemical or metabolic constraints;
5. scenario simulation and uncertainty;
6. graph-based explainability;
7. API and experimental web interface;
8. technical and scientific validation.

The prototype is intended for computational feasibility studies and hypothesis generation. It is **not** a replacement for *in vivo* or *in vitro* experimentation and must not be interpreted as a commercial nutritional recommendation system.

## Data scope

The publicly available data cannot rebuild the full graph flow. The real source D1 (HoloFood,
chicken) supports only 3 of the 11 relations of the graph schema: it has neither the
`diet → substrate → taxon` path nor any additive edge, so it cannot simulate a diet or additive
change through the microbiome. The synthetic dataset covers all 8 node types and 11 relations.

Therefore the web platform, scenario simulation, system validation, and final delivery use
**synthetic data**, and every output is labelled as such. Synthetic targets do not depend on diet
or additives, so these results show that the pipeline works end to end, not any biological effect.
The work on D1 is kept as exploratory results. The decision, its rationale, and the remaining
activities are documented in [`docs/process/final-scope.md`](docs/process/final-scope.md).

## Repository principles

- **Research first:** implementation decisions must remain traceable to scientific and technical evidence.
- **Reproducibility:** experiments, configurations, datasets, and results should be documented and versionable where licensing permits.
- **Progressive architecture:** modules are introduced according to project phases rather than implemented prematurely.
- **Testing:** transformations and computational components will gain automated tests as they are introduced.
- **Zero-cost baseline:** local environments and free/open-source software are the default. Paid SaaS, cloud compute, proprietary experiment tracking, or services requiring billing are not baseline dependencies.
- **Scientific caution:** synthetic data, assumptions, limitations, and externally sourced biological relationships must be explicitly identified.

## Repository structure

```text
NutriGraphDT/
├── .github/                 # Contribution and issue templates
├── configs/                 # Versioned experiment/data/model configuration
├── docs/                    # Documentation (index: docs/README.md)
│   ├── process/             # Reproducibility guide, delivery, workflow, development setup
│   ├── architecture/        # Modules and public API, API contract, data pipeline design
│   ├── synthetic-dataset/   # Synthetic dataset contract, dictionary and usage
│   ├── data-sources/        # Real data source D1 HoloFood (exploratory results)
│   ├── graph/               # Graph schema, integrity rules, builder and validation reports
│   ├── models/              # Models, constraints, uncertainty, simulation, explainability
│   └── research/            # Research documents (general scheme, bibliometrics, datasets)
├── reports/                 # Versioned reports generated by the scripts
├── scripts/                 # Reproducible entry points (delivery, app, experiments)
├── src/
│   └── nutrigraphdt/
│       ├── data/            # Ingestion, preprocessing and data contracts
│       ├── graph/           # Heterogeneous graph construction and validation
│       ├── models/          # Baselines and GNN models
│       ├── constraints/     # Biochemical/scientific constraints (D-06)
│       ├── scenarios/       # Empirical support of scenario predictions
│       ├── simulation/      # Scenario catalogue and basal/intervened comparison
│       ├── explainability/  # Graph explanations and importance analysis
│       ├── api/             # Versioned contract and scenario engine (public API)
│       ├── demo/            # Streamlit web app
│       └── delivery.py      # End-to-end synthetic delivery pipeline
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

What each module receives, returns, and its limits: [`docs/architecture/modules.md`](docs/architecture/modules.md).
The full documentation index is [`docs/README.md`](docs/README.md).

## Development phases

| Phase | Focus |
|---|---|
| F0 | Technical training and initial reconnaissance |
| F1 | Base infrastructure and development environment |
| F2 | Data contracts and heterogeneous graph schema |
| F3 | Ingestion pipeline and graph construction |
| F4 | Baselines and GNN architecture |
| F5 | Biochemical constraint module |
| F6 | Simulation and scenario comparison |
| F7 | Explainability |
| F8 | API and experimental web platform |
| F9 | Integration, validation and closure |

## Development setup

The baseline repository is designed to work without paid services.

```bash
git clone https://github.com/jvnioo/NutriGraphDT.git
cd NutriGraphDT
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"   # core + tooling; add graph,baselines,demo for models and app
pre-commit install
```

The models, the delivery, and the web app need the optional `graph`, `baselines`, and `demo` extras;
see the [reproducibility guide](docs/process/reproducibility-guide.md) and
[`docs/process/development.md`](docs/process/development.md#optional-graph-extra-pytorch-and-pytorch-geometric).

Run local quality checks with:

```bash
ruff check .
ruff format --check .
mypy src
python -m pytest
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/process/development.md`](docs/process/development.md) before contributing.

## Cost policy

The project baseline must not depend on paid infrastructure. See [`docs/process/cost-policy.md`](docs/process/cost-policy.md).

## License and data usage

No software license has been assigned yet. This is intentional while the academic team reviews ownership, publication, dataset licensing, and potential intellectual-property considerations. Third-party datasets and scientific resources must retain their original attribution and licensing conditions.

## Academic context

NutriGraphDT is an academic proof-of-concept targeting technical validation of a graph-based nutritional digital twin. Its scope is intentionally limited and expected to evolve as validated scientific definitions, data contracts, and biochemical constraints become available.
