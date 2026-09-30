# AI Engineering CI/CD Pipeline

This document describes the CI/CD pipeline and the RAG quality gates for the DocAnalyser platform.

## Pipeline Architecture

The pipeline consists of four dependent workflows that enforce quality before deployment:

1. **Java CI** (`java-ci.yml`) - Compiles Spring Boot and runs JUnit tests.
2. **Python CI** (`python-ci.yml`) - Lints with Ruff and runs pytest.
3. **RAG Evaluation** (`rag-evaluation.yml`) - Runs quality evaluations for the RAG pipeline.
4. **Docker Build** (`docker.yml`) - Builds backend, frontend, and RAG service Docker images.
5. **Deployment** (`deploy.yml`) - Deploys to production if all previous stages pass.

```
Push / Pull Request
       |
       +--> [Java CI]
       |
       +--> [Python CI]
       |
       v
[RAG Evaluation (Quality Gate)]
       |
       v
[Docker Build & Tag]
       |
       v
[Production Deployment]
```

## Workflows

### 1. Java CI (`.github/workflows/java-ci.yml`)
- Uses **Java 21 (Temurin)**.
- Runs `mvnw verify` using the `test` profile with an in-memory H2 database.
- Caches Maven dependencies automatically.
- Fails the pipeline on compilation or test failures.
- Uploads JUnit XML and Surefire HTML reports as artifacts.

### 2. Python CI (`.github/workflows/python-ci.yml`)
- Uses **Python 3.12**.
- Installs dependencies from `rag-service/requirements.txt`.
- Runs `ruff check` and `ruff format --check`.
- Runs `pytest` on unit tests (excluding `@pytest.mark.integration`).
- Generates pytest coverage and JUnit reports.

### 3. RAG Evaluation (`.github/workflows/rag-evaluation.yml`)
- Triggered after Java and Python CI.
- Runs the reproducible evaluation dataset (`rag-service/evals/data/eval_dataset.jsonl`).
- Computes **Recall@K**, **MRR**, **Answer Correctness**, **Faithfulness**, and **Citation Accuracy**.
- Compares candidate metrics against a baseline (`baseline_metrics.json`).
- Uses threshold values (`quality_gate_thresholds.json`) to determine regressions.
- Fails the workflow explicitly if a metric regression exceeds its critical threshold.

### 4. Docker Build (`.github/workflows/docker.yml`)
- Builds the `spring-boot-service`, `rag-service`, and `frontend` images.
- Tags images with the commit SHA and `latest`.
- Uses GitHub Actions caching (`docker/setup-buildx-action`) to speed up subsequent builds.

### 5. Deployment (`.github/workflows/deploy.yml`)
- A protected stage requiring the previous workflows to succeed.
- Deploys the images to the production environment using Docker Compose.
- Includes a post-deployment health check.

## Required Secrets & Variables

To configure the pipeline in GitHub, add the following secrets:

- `OPENAI_API_KEY`: Required for live LLM evaluations. If missing, the evaluation runs in **mock mode** (deterministic stubs).
- `DEPLOY_SSH_KEY`: Private SSH key to access the deployment server. If missing, deployment is safely bypassed.

## Quality Gate & Baselines

The quality gate is enforced by `scripts/quality_gate.py` which takes the results from the evaluation run and compares them against `baseline_metrics.json`.

**Example Thresholds:**
| Metric | Threshold Type | Limit |
|--------|----------------|-------|
| Recall@K | Relative | <= 5% drop |
| MRR | Relative | <= 5% drop |
| Citation Accuracy | Absolute | <= 2% drop |
| Answer Correctness | Absolute | <= 5% drop |

### Updating the Baseline

To update the baseline locally and commit it, run:
```bash
# Ensure your OPENAI_API_KEY is exported
python rag-service/scripts/run_evaluation.py --output-dir rag-service/evals/data/ --update-baseline
```

## Local Execution Commands

### Java
```bash
cd backend/spring-boot-service
./mvnw clean verify -Dspring.profiles.active=test
```

### Python Linting & Testing
```bash
cd rag-service
ruff check .
pytest tests/ -m "not integration"
```

### RAG Evaluation
```bash
cd rag-service
python scripts/run_evaluation.py --dataset evals/data/eval_dataset.jsonl --baseline evals/data/baseline_metrics.json --output-dir eval-results/
python scripts/quality_gate.py --candidate eval-results/evaluation_summary.json --baseline evals/data/baseline_metrics.json --thresholds evals/data/quality_gate_thresholds.json
```
