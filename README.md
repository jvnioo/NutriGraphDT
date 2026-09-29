# NutriGraphDT

**Graph-Based Nutritional Digital Twin for In Silico Simulation of the Animal Gut Microbiome**

NutriGraphDT is the software and research framework developed within the academic project **Microbioma Digital (PIA 302)**. The project investigates the feasibility of a nutritional digital twin of the animal gastrointestinal tract using heterogeneous graphs, Graph Neural Networks (GNNs), scientifically informed biochemical constraints, simulation, and explainability.

> **Status:** early research and technical foundation. This repository intentionally establishes documentation and architectural boundaries before model implementation.

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

## Repository principles

- **Research first:** implementation decisions must remain traceable to scientific and technical evidence.
- **Reproducibility:** experiments, configurations, datasets, and results should be documented and versionable where licensing permits.
- **Progressive architecture:** modules are introduced according to project phases rather than implemented prematurely.
- **Testing:** transformations and computational components will gain automated tests as they are introduced.
- **Zero-cost baseline:** local environments and free/open-source software are the default. Paid SaaS, cloud compute, proprietary experiment tracking, or services requiring billing are not baseline dependencies.
- **Scientific caution:** synthetic data, assumptions, limitations, and externally sourced biological relationships must be explicitly identified.

## Planned architecture

```text
NutriGraphDT/
├── .github/                 # Contribution and issue templates
├── configs/                 # Versioned experiment/data/model configuration
├── docs/                    # Architecture, development and research documentation
├── scripts/                 # Reproducible utility/experiment entry points
├── src/
│   └── nutrigraphdt/
│       ├── data/            # Ingestion, preprocessing and data contracts
│       ├── graph/           # Heterogeneous graph construction and validation
│       ├── models/          # Baselines and GNN models
│       ├── constraints/     # Biochemical/scientific constraints
│       ├── simulation/      # Scenario engine and uncertainty
│       ├── explainability/  # Graph explanations and importance analysis
│       └── api/             # Experimental API layer
└── tests/
    ├── unit/
    └── integration/
```

These directories describe planned technical boundaries. Their implementation will be introduced only when the corresponding phase and scientific inputs are ready.

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
pip install -e ".[dev]"
pre-commit install
```

The tensor validator needs PyTorch and PyTorch Geometric through the optional `graph` extra;
see [`docs/development.md`](docs/development.md#optional-graph-extra-pytorch-and-pytorch-geometric).

Run local quality checks with:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/development.md`](docs/development.md) before contributing.

## Cost policy

The project baseline must not depend on paid infrastructure. See [`docs/cost-policy.md`](docs/cost-policy.md).

## License and data usage

No software license has been assigned yet. This is intentional while the academic team reviews ownership, publication, dataset licensing, and potential intellectual-property considerations. Third-party datasets and scientific resources must retain their original attribution and licensing conditions.

## Academic context

NutriGraphDT is an academic proof-of-concept targeting technical validation of a graph-based nutritional digital twin. Its scope is intentionally limited and expected to evolve as validated scientific definitions, data contracts, and biochemical constraints become available.
