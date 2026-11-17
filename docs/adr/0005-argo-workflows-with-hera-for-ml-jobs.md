# ADR-0005: Argo Workflows with the Hera Python SDK for ML jobs and pipelines

- **Status:** Accepted
- **Date:** 2026-11-17

## Context

ML engineers want to **write Python and run it on the platform as a job**: single training runs, hyperparameter sweeps, and multi-step pipelines (prepare → train → evaluate → register). They shouldn't have to write Kubernetes YAML. The orchestrator must support GPUs, retries, artifacts in S3, scheduling, and per-tenant isolation.

## Options considered

1. **Kubeflow Pipelines (KFP).** Built for ML, with a Python SDK. Heavier to run, and its multi-user model is tied to the Kubeflow profile system.
2. **Argo Workflows with YAML.** Kubernetes-native and battle-tested, but writing YAML is a poor experience for ML engineers.
3. **Argo Workflows with Hera (Python SDK).** Same engine as option 2, but workflows are written as normal Python functions.
4. **Airflow, Flyte or Metaflow.** Capable, but they add another platform with its own runtime and operating model.

## Decision

Use **Argo Workflows** as the job and pipeline engine, with **Hera** as the developer-facing Python SDK.

- **Developer experience.** Engineers write Python functions, mark them as steps with Hera, and submit them to their tenant namespace.
  ```python
  from hera.workflows import Workflow, script, Resources

  @script(image="mlqube/pytorch:cuda", resources=Resources(gpus=1, memory="32Gi"))
  def train(lr: float):
      ...  # regular PyTorch / scikit-learn code, logging to MLflow

  with Workflow(generate_name="train-", entrypoint="train", namespace="team-a") as w:
      train(arguments={"lr": 0.001})
  w.create()
  ```
- **Golden paths.** The platform provides ClusterWorkflowTemplates (e.g. `train-evaluate-register`, `batch-inference`, `hyperparameter-sweep`) that come with curated images, S3 artifact access and MLflow integration already set up.
- **Compute.** Steps request CPU or GPU resources. Karpenter provisions the matching nodes (spot for interruptible training) and scales them to zero afterwards.
- **Queueing.** Kueue queues GPU workloads per tenant and enforces fair share.
- **Distributed training.** For multi-node jobs, a workflow step creates a Kubeflow `TrainJob` (or a Ray job) and waits for it to finish. Argo stays the orchestrator; the operator handles distributed coordination.
- **Artifacts.** Stored in the tenant's S3 bucket, accessed through EKS Pod Identity.
- **Multi-tenancy.** One Argo Workflows controller per workload cluster, a namespace per tenant, and Argo Server SSO (OIDC) with RBAC scoped to each tenant's namespaces.
- **Scheduling.** CronWorkflows for recurring retraining and batch jobs.

## Consequences

- One Argo toolset (Argo CD, Argo Workflows, Argo Rollouts) across the platform; operators learn one set of concepts.
- ML engineers stay in Python; YAML is still available for advanced users.
- Argo Workflows isn't specific to ML, so MlQube must supply the ML conveniences itself: MLflow tracking, lineage between runs and models, step caching (memoization), and curated GPU images.
- **To check early:** Kueue support for Argo Workflow pods is newer than its support for training-job resources. A spike in Phase 1 must confirm that per-tenant GPU queueing works for workflow steps.
- Kubeflow Pipelines is no longer planned.
