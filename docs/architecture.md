# Architecture

> Draft. Decisions are recorded in [ADRs](adr/); open items are listed at the end of this page.

## Key decisions

| Area | Decision | ADR | Status |
|---|---|---|---|
| Approach | Assemble open-source components plus a thin MlQube glue layer | [0001](adr/0001-assemble-open-source-components.md) | Accepted |
| Cloud | AWS / Amazon EKS first | [0002](adr/0002-aws-eks-as-first-cloud.md) | Accepted |
| Topology | Management cluster plus workload clusters (non-prod, prod) | [0003](adr/0003-cluster-topology.md) | Accepted |
| Tenancy | Tiers: Capsule namespaces, then vCluster, then dedicated cluster | [0004](adr/0004-tenancy-model.md) | Proposed |
| ML jobs & pipelines | Argo Workflows with the Hera Python SDK | [0005](adr/0005-argo-workflows-with-hera-for-ml-jobs.md) | Accepted |
| Platform APIs | Crossplane | [0006](adr/0006-platform-apis-with-crossplane.md) | Proposed |
| Tracking & registry | One MLflow instance per tenant | [0007](adr/0007-mlflow-multi-tenancy.md) | Proposed |
| Untrusted code | gVisor for CPU workloads, tenant-dedicated GPU nodes | [0008](adr/0008-workload-sandboxing.md) | Proposed |

## Cluster topology on AWS

```mermaid
flowchart TB
    subgraph MGMT["Management cluster (EKS)"]
        ARGOCD[Argo CD hub]
        XP[Crossplane + AWS provider]
        BS[Backstage portal]
        IDP[Identity provider · OIDC]
        OBS[Central observability]
    end

    subgraph NONPROD["Workload cluster: non-prod (EKS)"]
        NS1[Tenant namespaces]
        AW[Argo Workflows · Kueue]
        NB[Notebooks · MLflow per tenant]
        NP1[Karpenter NodePools<br/>CPU · GPU · spot-GPU · gVisor]
    end

    subgraph PROD["Workload cluster: prod (EKS)"]
        NS2[Tenant namespaces]
        KS[KServe endpoints]
        CRON[Production pipelines<br/>scheduled retraining]
        NP2[Karpenter NodePools<br/>CPU · GPU inference]
    end

    subgraph AWS["Shared AWS services"]
        S3[S3 · bucket per tenant]
        ECR[ECR]
        RDS[RDS PostgreSQL]
        SM[Secrets Manager]
        PI[EKS Pod Identity · IAM]
    end

    ARGOCD -- GitOps --> NONPROD
    ARGOCD -- GitOps --> PROD
    XP -- provisions --> AWS
    NONPROD --- AWS
    PROD --- AWS
```

- **Management cluster:** runs the platform itself. Tenant workloads never run here.
- **Non-prod workload cluster:** experimentation, jobs, notebooks, MLflow and staging endpoints.
- **Prod workload cluster:** production endpoints and production pipelines.
- **Enterprise tenants** get their own workload cluster, added as another spoke.
- **Local development:** a single kind cluster plays all roles.

## Layered view

```mermaid
flowchart TB
    subgraph Portal["Developer experience"]
        UI[Backstage portal<br/>templates · catalog · cost]
        SDK[Python SDK · Hera]
        API[MlQube platform APIs<br/>Tenant · MLProject · Workspace · ModelDeployment]
    end

    subgraph ML["ML capabilities"]
        WS[Workspaces<br/>Notebooks / IDEs]
        JOBS[Jobs & pipelines<br/>Argo Workflows · Kubeflow Trainer · KubeRay]
        REG[Tracking & registry<br/>MLflow]
        SRV[Serving<br/>KServe · vLLM · KEDA]
    end

    subgraph Core["Platform core"]
        GITOPS[Argo CD · GitOps]
        XPC[Crossplane]
        Q[Kueue · GPU quotas]
        SEC[IdP · Kyverno · Capsule · NetworkPolicies]
        OBSC[Prometheus · Grafana · OTel · OpenCost]
        GW[AWS LB Controller · Gateway API · cert-manager]
    end

    subgraph Infra["AWS infrastructure"]
        EKS[Amazon EKS]
        KARP[Karpenter · NVIDIA GPU Operator]
        STO[S3 · ECR · RDS · Secrets Manager]
    end

    UI --> API
    SDK --> JOBS
    API --> WS & JOBS & REG & SRV
    ML --> Core
    Core --> Infra
```

## Layers

| Layer | Components | Responsibility |
|---|---|---|
| **Infrastructure** | Terraform, Amazon EKS, VPC per environment, Karpenter NodePools (CPU, GPU, spot-GPU, inference, gVisor), NVIDIA GPU Operator, S3, ECR, RDS | Reproducible clusters and elastic GPU capacity |
| **Platform core** | Argo CD (hub in mgmt cluster), Crossplane (AWS + Kubernetes providers), AWS Load Balancer Controller / Gateway API, cert-manager, External Secrets (Secrets Manager), Kyverno | Declarative delivery, cloud resources, ingress, secrets, policy |
| **Tenancy & identity** | OIDC identity provider (Keycloak or corporate IdP), Capsule / vCluster, NetworkPolicies, Kueue, EKS Pod Identity | Tenant isolation, authentication, RBAC, GPU fair-share, IAM without static keys |
| **Workspaces** | Kubeflow Notebooks or Coder, curated CUDA/framework images | Self-service development environments |
| **Jobs & pipelines** | **Argo Workflows + Hera**, golden-path ClusterWorkflowTemplates, CronWorkflows, Kubeflow Trainer / KubeRay for distributed training | Run Python ML code as jobs and pipelines |
| **Tracking & registry** | MLflow per tenant (RDS PostgreSQL metadata, S3 artifacts) | Experiments, model versions, stage promotion |
| **Serving** | KServe (vLLM, Triton, sklearn/xgboost runtimes), KEDA / Knative | Autoscaled inference endpoints, canary rollouts |
| **CI/CD** | GitHub Actions → ECR, Argo CD, Argo Rollouts | Image builds, model promotion through GitOps |
| **Portal** | Backstage | Templates, model & endpoint catalog, usage and cost views |
| **Observability & cost** | Prometheus, Grafana, Loki, OpenTelemetry, DCGM exporter, OpenCost (AWS pricing) | Metrics, logs, traces, GPU telemetry, cost allocation |

## How ML engineers run code

ML engineers write **Python** and submit it as an **Argo Workflow** using the Hera SDK ([ADR-0005](adr/0005-argo-workflows-with-hera-for-ml-jobs.md)):

```python
from hera.workflows import Workflow, script, Resources

@script(image="mlqube/pytorch:cuda", resources=Resources(gpus=1, memory="32Gi"))
def train(lr: float):
    ...  # regular PyTorch / scikit-learn code, logging to MLflow

with Workflow(generate_name="train-", entrypoint="train", namespace="team-a") as w:
    train(arguments={"lr": 0.001})
w.create()
```

```mermaid
flowchart LR
    PY[Python code<br/>+ Hera] --> AS[Argo Server<br/>SSO · tenant RBAC]
    AS --> WF[Workflow in<br/>tenant namespace]
    WF --> KQ[Kueue<br/>tenant GPU queue]
    KQ --> KP[Karpenter<br/>launches GPU node]
    KP --> POD[Step pods run]
    POD --> S3[(Tenant S3<br/>artifacts)]
    POD --> MLF[(Tenant MLflow<br/>metrics · models)]
```

- **Golden-path templates:** `train-evaluate-register`, `batch-inference`, `hyperparameter-sweep`.
- **Distributed training:** a step creates a Kubeflow `TrainJob` or Ray job and waits for it.
- **Scheduled jobs:** CronWorkflows, e.g. nightly retraining.

## Platform APIs (the glue layer)

MlQube adds a small set of high-level resources, implemented with Crossplane ([ADR-0006](adr/0006-platform-apis-with-crossplane.md)):

| Resource | Expands into |
|---|---|
| `Tenant` | Capsule tenant or vCluster, quotas, Kueue queue, network policies, S3 bucket, IAM role, MLflow instance |
| `MLProject` | Project namespace, ECR repository, CI configuration, MLflow experiment, starter WorkflowTemplates |
| `Workspace` | Notebook/IDE instance with GPU limits and storage |
| `ModelDeployment` | KServe InferenceService, route, autoscaling, canary policy, dashboards |

Users normally create these through Backstage. Advanced users can apply them directly through Git.

## Multi-tenancy model

| Tier | Isolation | Use case |
|---|---|---|
| **Standard** | Capsule tenant on shared workload clusters; quotas, Kueue, default-deny network policies, gVisor for CPU, tenant-dedicated GPU nodes | Cost-efficient default |
| **Premium** | vCluster per tenant, optionally with dedicated Karpenter NodePools | Teams that need their own control plane |
| **Enterprise** | Dedicated workload cluster | Strict compliance or data residency |

See [ADR-0004](adr/0004-tenancy-model.md) and [ADR-0008](adr/0008-workload-sandboxing.md).

## Model lifecycle flow

```mermaid
sequenceDiagram
    participant Dev as ML engineer
    participant AW as Argo Workflows (non-prod)
    participant ML as MLflow (tenant)
    participant Git as GitOps repo
    participant CD as Argo CD (mgmt)
    participant KS as KServe (prod)

    Dev->>AW: Submit training workflow (Python / Hera)
    AW->>ML: Log runs, register model v3
    Dev->>ML: Promote v3 to Staging
    ML->>Git: Open PR (ModelDeployment v3)
    Git->>CD: Merge triggers sync
    CD->>KS: Deploy canary in prod cluster
    Dev->>Git: Approve full rollout
```

## Open questions

1. Identity provider: self-hosted Keycloak, Amazon Cognito, or the customer's own IdP through federation
2. Ingress: AWS Load Balancer Controller only, or Gateway API with Envoy Gateway / Istio
3. Observability: self-hosted, or Amazon Managed Prometheus/Grafana
4. Kueue with Argo Workflow pods: to be checked in a Phase 1 spike
5. Workspaces: Kubeflow Notebooks or Coder
