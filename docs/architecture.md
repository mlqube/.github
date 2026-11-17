# Architecture

> Draft. Components and choices may change as [ADRs](adr/) are accepted.

## Layered view

```mermaid
flowchart TB
    subgraph Portal["Developer experience"]
        BS[Backstage portal<br/>templates · catalog · cost]
        API[mlqube platform APIs<br/>Tenant · MLProject · Workspace · ModelDeployment]
    end

    subgraph ML["ML capabilities"]
        WS[Workspaces<br/>Notebooks / IDEs]
        TR[Training<br/>Kubeflow Trainer · KubeRay · Pipelines]
        REG[Tracking & registry<br/>MLflow]
        SRV[Serving<br/>KServe · vLLM · KEDA]
    end

    subgraph Core["Platform core"]
        GITOPS[Argo CD · GitOps]
        XP[Crossplane]
        Q[Kueue · GPU quotas]
        SEC[Keycloak · Kyverno · Cilium]
        OBS[Prometheus · Grafana · OTel · OpenCost]
        GW[Gateway API · cert-manager]
    end

    subgraph Infra["Infrastructure"]
        K8S[Managed Kubernetes<br/>EKS / GKE / AKS]
        GPU[GPU node pools<br/>Karpenter · GPU Operator]
        STO[Object storage · OCI registry]
    end

    BS --> API
    API --> WS & TR & REG & SRV
    ML --> Core
    Core --> Infra
```

## Layers

| Layer | Components | Responsibility |
|---|---|---|
| **Infrastructure** | OpenTofu/Terraform, managed Kubernetes, Karpenter or node auto-provisioning, NVIDIA GPU Operator, object storage, OCI registry | Reproducible clusters and elastic GPU capacity |
| **Platform core** | Argo CD, Crossplane, Gateway API (Envoy Gateway / Istio), cert-manager, External Secrets, Kyverno | Declarative delivery, cloud resources, ingress, secrets, policy |
| **Tenancy & identity** | Keycloak or cloud IdP (OIDC), Capsule / vCluster, Cilium network policies, Kueue | Tenant isolation, authentication, RBAC, GPU fair-share |
| **Workspaces** | Kubeflow Notebooks or Coder, curated CUDA/framework images | Self-service development environments |
| **Training** | Kubeflow Trainer, KubeRay, Kubeflow Pipelines or Argo Workflows | Distributed training and ML pipelines |
| **Tracking & registry** | MLflow, per-tenant artifact buckets | Experiments, model versions, stage promotion |
| **Serving** | KServe (vLLM, Triton, sklearn/xgboost runtimes), KEDA / Knative | Autoscaled inference endpoints, canary rollouts |
| **CI/CD** | GitHub Actions or Tekton, Argo CD, Argo Rollouts | Image builds, model promotion through GitOps |
| **Portal** | Backstage | Templates, model & endpoint catalog, usage and cost views |
| **Observability & cost** | Prometheus, Grafana, Loki, OpenTelemetry, DCGM exporter, OpenCost | Metrics, logs, traces, GPU telemetry, cost allocation |

## Platform APIs (the glue layer)

mlqube adds a small set of high-level resources, implemented as Crossplane Compositions or KRO definitions:

| Resource | Expands into |
|---|---|
| `Tenant` | Namespaces, quotas, Kueue queues, network policies, IdP group, artifact bucket, MLflow access |
| `MLProject` | Git repo from template, CI pipeline, project namespace, MLflow experiment |
| `Workspace` | Notebook/IDE instance with GPU limits and storage |
| `ModelDeployment` | KServe InferenceService, route, autoscaling, canary policy, dashboards |

Users normally create these through Backstage. Advanced users can apply them directly through Git.

## Multi-tenancy model (proposed)

| Tier | Isolation | Use case |
|---|---|---|
| **Standard** | Shared cluster; namespace per tenant (Capsule), network policies, Kueue quotas, optional sandboxed runtime (gVisor/Kata) | Cost-efficient default |
| **Premium** | Virtual cluster per tenant (vCluster) on shared nodes or dedicated node pools | Teams that need their own control plane |
| **Enterprise** | Dedicated cluster per tenant | Strict compliance or data residency |

Key isolation concerns: shared GPU nodes, secrets, MLflow authorization, egress control and untrusted code in notebooks and training jobs.

## Model lifecycle flow

```mermaid
sequenceDiagram
    participant Dev as ML engineer
    participant NB as Workspace
    participant TR as Training
    participant ML as MLflow registry
    participant Git as GitOps repo
    participant CD as Argo CD
    participant KS as KServe

    Dev->>NB: Explore & prototype
    Dev->>TR: Submit training pipeline
    TR->>ML: Log runs, register model v3
    Dev->>ML: Promote v3 to Staging
    ML->>Git: Open PR (ModelDeployment v3)
    Git->>CD: Merge triggers sync
    CD->>KS: Deploy canary
    Dev->>Git: Approve promotion to Prod
```

## Open questions

These will be settled as ADRs:

1. Which cloud provider comes first?
2. Final tenancy tiers and default isolation for the shared tier
3. Kubeflow Pipelines vs Argo Workflows
4. MLflow multi-tenancy: an instance per tenant or shared behind an authorization proxy
5. Crossplane Compositions vs KRO for the platform APIs
6. Whether sandboxed runtimes are required for the shared tier
