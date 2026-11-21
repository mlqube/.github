# Architecture

> Decisions are recorded in [ADRs](adr/); open items are listed at the end of this page.

## Key decisions

| Area | Decision | ADR | Status |
|---|---|---|---|
| Approach | Assemble open-source components plus a thin MlQube glue layer | [0001](adr/0001-assemble-open-source-components.md) | Accepted |
| Cloud | AWS / Amazon EKS first | [0002](adr/0002-aws-eks-as-first-cloud.md) | Accepted |
| Topology | Management cluster plus workload clusters (non-prod, prod) | [0003](adr/0003-cluster-topology.md) | Accepted |
| Tenancy | Single tier: each business unit is a tenant (`<businessunit_name>-<businessunitid>`) on the shared clusters | [0004](adr/0004-tenancy-model.md) | Accepted |
| ML jobs & pipelines | Argo Workflows with the Hera Python SDK | [0005](adr/0005-argo-workflows-with-hera-for-ml-jobs.md) | Accepted |
| Platform APIs | Crossplane | [0006](adr/0006-platform-apis-with-crossplane.md) | Accepted |
| Tracking & registry | One shared MLflow (RDS PostgreSQL + S3), isolated by permissions and S3 prefixes | [0007](adr/0007-mlflow-multi-tenancy.md) | Accepted |
| Untrusted code | gVisor for CPU workloads, tenant-dedicated GPU nodes | [0008](adr/0008-workload-sandboxing.md) | Accepted |
| Identity | Corporate IdP over OIDC for all people; groups per tenant; EKS Pod Identity for workloads | [0009](adr/0009-identity-provider.md) | Accepted |
| Ingress | Internal ALBs (AWS Load Balancer Controller), ACM, Route 53 private zone; KServe networking decided in Phase 5 | [0010](adr/0010-ingress.md) | Accepted |
| Private access (reference build) | Tailscale subnet router in the mgmt VPC with split DNS; EKS API endpoint limited to the owner's IP | [0011](adr/0011-private-access-reference-build.md) | Accepted |
| Pod networking | AWS VPC CNI with prefix delegation; it also enforces the default-deny network policies; Calico possible later in policy-only mode | [0013](adr/0013-cni-and-network-policy.md) | Accepted |

## Enterprise view

The architecture is shown in six views: the first five from the big picture down to the details, and view 6 for how changes reach the clusters. Every view reads left to right and uses the same swimlane colours. Click an image for the scalable SVG. The sources are in [`diagrams/`](diagrams/) (Python `diagrams` library + Graphviz); `python docs/diagrams/render_all.py` re-renders all of them.

### 1. High-level architecture

[![MlQube: high-level architecture](diagrams/mlqube_1_overview.png)](diagrams/mlqube_1_overview.svg)

Business units (tenants) sign in through the corporate IdP and push Python (Hera) code to GitHub. The **management cluster** is the platform's control plane: it deploys and provisions everything through GitOps. ML work happens in the **non-prod workload cluster**; promoted models are served from the **prod workload cluster** to business applications. All clusters use the shared AWS services, and the platform reports policy, audit and cost per business unit.

### 2. Identity, authentication and authorization

[![MlQube: identity, authentication and authorization](diagrams/mlqube_2_identity.png)](diagrams/mlqube_2_identity.svg)

1. Users reach the portals over the corporate network / VPN, through a private ALB with TLS certificates from ACM.
2. Each tool (Backstage, MLflow, Grafana, Argo CD, Argo Workflows) signs the user in with the corporate IdP (OIDC + MFA). The ID token carries the user's groups: `mlqube-<tenant>-admins`, `-developers`, `-viewers`.
3. Each tool maps those groups to roles in the user's own tenant only: Backstage ownership, MLflow permissions on the tenant's experiments and models, Grafana teams, Argo Workflows SSO RBAC.
4. `kubectl` uses the same OIDC token against the EKS API; Kubernetes RBAC and Capsule limit users to their tenant's namespaces.
5. Kyverno and Capsule check every object at admission (tenant labels, quotas, allowed images).
6. Workloads never hold static cloud keys: a tenant pod's ServiceAccount gets temporary credentials for the tenant's IAM role through EKS Pod Identity, which can reach only that tenant's S3 bucket, ECR repositories and secrets.

### 3. Management cluster and shared services

[![MlQube: management cluster and shared services](diagrams/mlqube_3_management.png)](diagrams/mlqube_3_management.svg)

The management cluster runs the platform itself; tenant workloads never run there. It contains: **Argo CD** (GitOps hub), **Backstage** (portal: templates, catalog, cost views), **Crossplane** with the MlQube APIs (`Tenant`, `MLProject`, `Workspace`, `ModelDeployment`), the one shared **MLflow**, **central observability** (OpenTelemetry Collector, Prometheus, Loki, Grafana, OpenCost) and the add-ons every cluster has (External Secrets Operator, AWS Load Balancer Controller, Kyverno).

1. Terraform builds the foundation (VPCs, the three EKS clusters, RDS, base IAM) and bootstraps Argo CD.
2. Argo CD syncs platform add-ons and configuration from Git to the management and workload clusters.
3. A new tenant or project is requested in Backstage; the template opens a PR with a `Tenant` / `MLProject` claim, which Argo CD applies.
4. Crossplane turns the claim into AWS and Kubernetes resources: S3 bucket, IAM role, ECR repository, namespaces, quotas and Kueue queues.
5. MLflow keeps metadata in RDS PostgreSQL (Multi-AZ) and artifacts in S3 under a prefix per tenant.
6. External Secrets copies secrets (e.g. the RDS password) from Secrets Manager into the clusters.
7. All clusters send metrics, logs and traces to central observability; OpenCost reports cost per business unit.

### 4. Training, testing and serving

[![MlQube: training, testing and serving](diagrams/mlqube_4_ml_lifecycle.png)](diagrams/mlqube_4_ml_lifecycle.svg)

1. **Develop:** explore data in a notebook and write the pipeline in Python with the Hera SDK.
2. **Build:** push to GitHub; GitHub Actions runs tests and pushes training and serving images to ECR.
3. **Submit:** the Hera code submits a workflow (golden template `train-evaluate-register`) to Argo Workflows in the tenant's namespace.
4. **Schedule:** Kueue admits it to the tenant's GPU queue; Karpenter starts a tenant-dedicated spot GPU node.
5. **Train and track:** the job reads data from the tenant's S3 bucket, logs runs and registers the model version in MLflow.
6. **Test:** an evaluate step compares the model against the baseline, then the candidate is deployed to a staging endpoint (KServe) for integration and load tests.
7. **Promote:** the model owner promotes the version in MLflow; MlQube opens a GitOps PR with a `ModelDeployment`.
8. **Deploy:** after approval and merge, Argo CD rolls out a KServe canary in prod (vLLM for LLMs) on GPU inference nodes.
9. **Serve:** business applications call the endpoint through the internal ALB.
10. **Retrain:** CronWorkflows retrain on a schedule and register a new version, which goes back to step 6.

### 5. Full view

[![MlQube: Enterprise ML Platform on AWS, full view](diagrams/mlqube_5_enterprise.png)](diagrams/mlqube_5_enterprise.svg)

All parts joined together: **people and business units** (tenants such as `retail-1042`, `risk-analytics-2001` and `marketing-3007`, plus the platform team and Finance/FinOps), the **corporate edge and identity** (corporate IdP, VPN, GitHub org, Terraform), the **AWS account** (management cluster, non-prod and prod workload clusters, shared AWS services), and **governance and FinOps**.

Numbered flows:

1. **Job submission:** an ML engineer writes Python with the Hera SDK and submits it to Argo Workflows; Kueue admits it to the tenant's GPU queue and Karpenter launches a tenant-dedicated GPU node (spot for training).
2. **Tracking and registry:** the job logs runs and registers the model in the shared MLflow; metadata goes to RDS PostgreSQL (Multi-AZ), artifacts to the tenant's S3 prefix (`s3://<bucket>/tenants/<tenant>/`).
3. **Model promotion:** promoting a model in MLflow opens a GitOps PR in GitHub; on merge, Argo CD deploys a KServe canary (vLLM for LLMs) in the prod cluster.
4. **GitOps:** Argo CD in the management cluster syncs both workload clusters.
5. **Provisioning:** Crossplane creates each tenant's S3 bucket, IAM role (EKS Pod Identity) and namespaces.
6. **SSO:** the corporate IdP (OIDC) signs users in to Backstage, the Argo Workflows UI and MLflow, using the groups `mlqube-<tenant>-admins`, `-developers` and `-viewers`.
7. **Metrics and cost:** all clusters send metrics and logs to central observability (OpenTelemetry, Prometheus, Loki, Grafana); OpenCost turns them into a showback/chargeback report per BU.

### 6. GitOps hub and spoke

[![MlQube: GitOps hub and spoke, one Argo CD for every cluster](diagrams/mlqube_6_gitops_hub.png)](diagrams/mlqube_6_gitops_hub.svg)

How changes reach the clusters. There is **one Argo CD, in the management cluster** (the hub). The workload clusters (the spokes) **run no Argo CD**: they are registered as destinations, and the hub deploys into them ([ADR-0003](adr/0003-cluster-topology.md), [ADR-0014](adr/0014-ci-access-to-private-clusters.md)).

| | Management cluster (hub) | Workload clusters (spokes: non-prod, later prod) |
|---|---|---|
| Runs Argo CD | **Yes**: the single control point | **No** |
| Role | Decides what runs everywhere: reads Git, compares it with every cluster, applies the differences | Receives what Argo CD sends; runs the ML workloads (jobs, pipelines, endpoints) |
| Holds | Argo CD and its read-only Git key, the platform tools (later Backstage, MLflow, Crossplane, Grafana) | Only workloads and the add-ons they need; no Git credentials, no deployment tooling |

Numbered flows:

1. **Bootstrap and registration:** on every platform build, Terraform installs Argo CD in the hub (through the private API, ADR-0014) and **registers each workload cluster**: a *cluster secret* in Argo CD (the spoke's API endpoint, CA certificate and "authenticate with AWS as Argo CD's role"), and an **EKS access entry** in the spoke that makes Argo CD's IAM role cluster-admin there.
2. **Desired state:** Argo CD pulls the GitOps repository with a read-only deploy key. `clusters/<cluster>/` says what runs in each cluster; `platform/` holds add-on settings; `tenants/` (Phase 2) the tenant claims.
3. **One Application per cluster:** an **ApplicationSet** with a *cluster generator* turns one template per add-on (load balancer controller, ExternalDNS, Karpenter, ...) into one Application per registered cluster, each with that cluster's values (cluster name, VPC, DNS domain, node pools). A new cluster gets every shared add-on as soon as it is registered.
4. **The hub itself:** Argo CD applies the hub's own add-ons and platform tools in-cluster. The entry point is a single root Application ("app of apps").
5. **The spokes:** Argo CD's pods get AWS credentials through **EKS Pod Identity**, reach the spoke's **private** API over **VPC peering** (port 443, allowed from the hub's address range), and the spoke's access entry authorizes them. Nothing goes over the internet, and the spokes never call back into the hub.
6. **Prod (later):** registered the same way. In an enterprise setup prod lives in a separate AWS account; registration then uses a cross-account IAM role instead of a same-account access entry.
7. **One UI:** the platform team sees and operates every cluster's applications in one Argo CD UI, on a private URL (`argocd.<domain>` behind an internal load balancer), with single sign-on later (ADR-0009).

**Why one hub instead of an Argo CD per cluster:**

- **One place** for the UI, permissions, audit and upgrades.
- **Lean, safer spokes:** workload clusters hold no Git credentials; a compromised workload cluster can't change what is deployed elsewhere.
- **Failure mode:** if the hub is down, the spokes **keep running**; only *changes* pause until it is back.
- **Trade-off:** the hub needs network and IAM access to every spoke. An Argo CD per cluster would avoid that, but makes sense mainly when clusters belong to separate, isolated owners or their networks can't connect.

## Cluster topology on AWS

```mermaid
flowchart TB
    subgraph MGMT["Management cluster (EKS)"]
        ARGOCD[Argo CD hub]
        XP[Crossplane + AWS provider]
        BS[Backstage portal]
        OBS[Central observability]
        MLFLOW[Shared MLflow<br/>tracking · registry]
    end

    IDP[Corporate IdP · OIDC SSO]

    subgraph NONPROD["Workload cluster: non-prod (EKS)"]
        NS1[Tenant namespaces]
        AW[Argo Workflows · Kueue]
        NB[Notebooks]
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

    IDP -- SSO --> MGMT
    ARGOCD -- GitOps --> NONPROD
    ARGOCD -- GitOps --> PROD
    XP -- provisions --> AWS
    NONPROD --- AWS
    PROD --- AWS
```

- **Management cluster:** runs the platform itself. Tenant workloads never run here.
- **Non-prod workload cluster:** experimentation, jobs, notebooks, MLflow and staging endpoints.
- **Prod workload cluster:** production endpoints and production pipelines.
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
        GW[AWS LB Controller · internal ALBs<br/>ACM · Route 53 · ExternalDNS]
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
| **Platform core** | Argo CD (hub in mgmt cluster), Crossplane (AWS + Kubernetes providers), AWS Load Balancer Controller (internal ALBs), ACM, ExternalDNS, cert-manager (in-cluster certificates only), External Secrets (Secrets Manager), Kyverno | Declarative delivery, cloud resources, ingress, secrets, policy |
| **Tenancy & identity** | Corporate IdP over OIDC ([ADR-0009](adr/0009-identity-provider.md)), Capsule, NetworkPolicies, Kueue, EKS Pod Identity | Tenant isolation, authentication, RBAC, GPU fair-share, IAM without static keys |
| **Workspaces** | Kubeflow Notebooks or Coder, curated CUDA/framework images | Self-service development environments |
| **Jobs & pipelines** | **Argo Workflows + Hera**, golden-path ClusterWorkflowTemplates, CronWorkflows, Kubeflow Trainer / KubeRay for distributed training | Run Python ML code as jobs and pipelines |
| **Tracking & registry** | One shared MLflow: RDS PostgreSQL backend store, S3 artifact store with a prefix per tenant, OIDC SSO, per-tenant permissions | Experiments, model versions, stage promotion |
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
    POD --> MLF[(Shared MLflow<br/>tenant-scoped)]
```

- **Golden-path templates:** `train-evaluate-register`, `batch-inference`, `hyperparameter-sweep`.
- **Distributed training:** a step creates a Kubeflow `TrainJob` or Ray job and waits for it.
- **Scheduled jobs:** CronWorkflows, e.g. nightly retraining.

## Platform APIs (the glue layer)

MlQube adds a small set of high-level resources, implemented with Crossplane ([ADR-0006](adr/0006-platform-apis-with-crossplane.md)):

| Resource | Expands into |
|---|---|
| `Tenant` | Capsule tenant, quotas, Kueue queue, network policies, S3 bucket, IAM role, MLflow permissions and S3 artifact prefix |
| `MLProject` | Project namespace, ECR repository, CI configuration, MLflow experiment, starter WorkflowTemplates |
| `Workspace` | Notebook/IDE instance with GPU limits and storage |
| `ModelDeployment` | KServe InferenceService, route, autoscaling, canary policy, dashboards |

Users normally create these through Backstage. Advanced users can apply them directly through Git.

## Multi-tenancy model

MlQube serves one organization, and **each business unit (BU) is a tenant**. All tenants share the same clusters in a single tier.

- **Tenant ID:** `<businessunit_name>-<businessunitid>`, e.g. `retail-1042`. The BU ID is numeric. Lowercase, at most 30 characters, and immutable once created.
- **Used everywhere:** Capsule tenant, namespaces (`retail-1042-churn`), the `mlqube/tenant` label, Kueue queue, IdP groups, IAM role, S3 bucket, MLflow names and prefixes, and cost reports.
- **Isolation:** Capsule namespaces, quotas, Kueue fair-share, default-deny network policies, Kyverno, IAM per tenant, gVisor for CPU workloads and tenant-dedicated GPU nodes.
- **Cost:** showback/chargeback per BU, based on the tenant label.

See [ADR-0004](adr/0004-tenancy-model.md) and [ADR-0008](adr/0008-workload-sandboxing.md).

## Model lifecycle flow

```mermaid
sequenceDiagram
    participant Dev as ML engineer
    participant AW as Argo Workflows (non-prod)
    participant ML as MLflow (shared)
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

1. Observability: self-hosted, or Amazon Managed Prometheus/Grafana
2. Kueue with Argo Workflow pods: to be checked in a Phase 1 spike
3. Workspaces: Kubeflow Notebooks or Coder
4. KServe networking for canary rollouts (Knative, or Gateway API with Envoy Gateway): to be decided in Phase 5 ([ADR-0010](adr/0010-ingress.md))

Answered earlier questions: identity provider in [ADR-0009](adr/0009-identity-provider.md), ingress in [ADR-0010](adr/0010-ingress.md).
