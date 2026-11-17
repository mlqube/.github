# ADR-0003: Cluster topology: a management cluster plus workload clusters

- **Status:** Accepted
- **Date:** 2026-11-17

## Context

MlQube hosts the platform itself (GitOps, portal, provisioning, identity, observability) and tenants' ML workloads (jobs, notebooks, model endpoints). These have different risk profiles:

- Experimental tenant code and large GPU jobs shouldn't affect production endpoints.
- The platform's own control plane must survive problems in workload clusters.
- Upgrades to Kubernetes and platform components need a safe place to be tested before production.
- Enterprise customers may require a dedicated cluster.

## Options considered

1. **Single cluster for everything.** Cheapest and simplest, but one bad upgrade or runaway workload affects everyone, and prod and experimental code share the same cluster.
2. **A management cluster plus workload clusters per environment (hub and spoke).** Separates platform from workloads and non-prod from prod; enterprise clusters are simply more spokes.
3. **Separate clusters for training and serving.** Clean separation, but too many clusters for the current scale.
4. **A cluster per tenant for everyone.** Strongest isolation, but cost and operational overhead are too high for a default.

## Decision

Use **hub and spoke**:

| Cluster | Runs |
|---|---|
| **Management** (`mgmt`) | Argo CD (hub), Crossplane, Backstage, identity provider, central observability, shared MLflow ([ADR-0007](0007-mlflow-multi-tenancy.md)) |
| **Workload: non-prod** (`wl-nonprod`) | Tenant namespaces for experimentation: Argo Workflows jobs, notebooks, staging endpoints |
| **Workload: prod** (`wl-prod`) | Production KServe endpoints and production pipelines (e.g. scheduled retraining) |
| **Dedicated workload** (later) | One cluster per enterprise tenant ([ADR-0004](0004-tenancy-model.md)) |

- Training and serving share a workload cluster, separated by **Karpenter NodePools** (CPU, GPU, spot-GPU, inference) with taints and tolerations.
- Argo CD in the management cluster deploys to all workload clusters from Git.
- For **local development**, a single kind cluster plays all roles.

## Consequences

- Smaller blast radius, safer upgrades (non-prod first), and a clean path to dedicated enterprise clusters.
- At least three EKS control planes to pay for and operate from the start.
- Argo CD has to manage several clusters, which needs cross-cluster credentials, cluster registration and per-cluster configuration.
- Metrics and logs from all clusters must be collected centrally.
- We will revisit splitting training and serving into separate clusters, or adding regions, when load or customers require it.
