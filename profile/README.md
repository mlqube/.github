# MlQube

**A Kubernetes-native internal developer platform for ML and AI teams.**

MlQube lets ML engineers and data scientists **build, train, register and serve models** themselves, with no need to become Kubernetes experts. It is built from proven open-source projects and adds a thin layer for multi-tenancy, golden paths and cost visibility.

> **Status:** 🧭 Planning. We are designing the architecture in the open. Nothing here is ready for production yet.

---

## Why MlQube?

ML teams lose a lot of time on infrastructure: GPU quotas, CUDA images, distributed training setup, serving stacks, model promotion and cost tracking. Platform teams end up rebuilding the same tooling again and again.

### Why does an organization need this?

- ⏱️ **Models get stuck before production.** Without standard paths, every deployment is a custom project, and AI initiatives stall after the pilot.
- 💸 **GPUs are expensive and poorly used.** Some sit idle while other teams wait; costs can't be attributed to teams or business units.
- 🔁 **Every team rebuilds the same stack.** Duplicated training, serving and CI tooling leads to inconsistent quality and wasted effort.
- 🛡️ **Governance gaps.** No clear lineage from data to deployed model; shadow infrastructure creates security and compliance risk.
- 🎫 **Platform teams become bottlenecks.** Engineers spend their time on tickets instead of improving the platform.

An ML platform turns infrastructure into **self-service golden paths**. ML teams ship faster, platform teams keep control, and finance can see where the money goes. 👉 [Read the full case](https://github.com/mlqube/.github/blob/main/docs/why-an-ml-idp.md)

MlQube aims to provide:

- 🧑‍💻 **Self-service workspaces.** GPU notebooks and IDEs with sensible images and quotas.
- 🐍 **Write Python, run it as a job.** ML code runs as Argo Workflows jobs and pipelines through a simple Python SDK, with no YAML.
- 🏋️ **Training at scale.** GPU jobs that queue fairly and scale to zero when idle.
- 📦 **Model registry and promotion.** Versioned models that move Dev → Staging → Prod through reviewed, auditable changes.
- 🚀 **Model serving.** Autoscaled endpoints for classic ML and LLMs, with canary rollouts.
- 🏢 **Business units as tenants.** Each business unit gets isolation, quotas and its own cost visibility.
- 🧭 **One front door.** A developer portal with templates, a model catalog and usage dashboards.

## The golden path

```mermaid
flowchart LR
    A[Create project<br/>from template] --> B[Explore in<br/>GPU notebook]
    B --> C[Run training<br/>pipeline]
    C --> D[Register model<br/>in registry]
    D --> E[Promote → GitOps PR]
    E --> F[Serve endpoint<br/>canary → prod]
    F --> G[Observe latency,<br/>GPU use & cost]
```

## Architecture at a glance

[![MlQube: high-level architecture](https://raw.githubusercontent.com/mlqube/.github/main/docs/diagrams/mlqube_1_overview.png)](https://github.com/mlqube/.github/blob/main/docs/architecture.md#enterprise-view)

📐 **Main architecture diagram:** [full enterprise view](https://github.com/mlqube/.github/blob/main/docs/diagrams/mlqube_5_enterprise.png) · [SVG](https://github.com/mlqube/.github/blob/main/docs/diagrams/mlqube_5_enterprise.svg). The [architecture document](https://github.com/mlqube/.github/blob/main/docs/architecture.md#enterprise-view) walks through all five views step by step.

What is planned:

- ☁️ **AWS and Amazon EKS**, built with Terraform: one VPC per environment, private subnets only.
- 🕸️ **Hub-and-spoke clusters.** A **management cluster** runs the platform itself: Argo CD (GitOps hub), Crossplane (platform APIs), Backstage (portal), one shared MLflow and central observability. A **non-prod cluster** runs notebooks, training jobs and staging endpoints. A **prod cluster** serves models with KServe (vLLM for LLMs) and runs scheduled retraining.
- ⚡ **Elastic compute** with Karpenter: CPU, gVisor-sandboxed CPU, GPU dedicated per tenant (spot for training) and GPU inference.
- 🏢 **One tenant per business unit**, e.g. `retail-1042`, isolated with Capsule, quotas, default-deny network policies, Kyverno and a per-tenant IAM role.
- 🔐 **Single sign-on** through AWS IAM Identity Center (fed by the corporate directory in an organization) and groups per tenant (`mlqube-<tenant>-admins`, `-developers`, `-viewers`); workloads never use static cloud keys.
- 🔄 **Model lifecycle:** train on a tenant GPU node → register in MLflow → test on a staging endpoint → promote through a GitOps PR → KServe canary in prod.
- 💰 **Governance and FinOps:** policies in every cluster, audit and lineage, and cost showback / chargeback per business unit with OpenCost.

| View | Shows |
|---|---|
| [1. High-level architecture](https://github.com/mlqube/.github/blob/main/docs/diagrams/mlqube_1_overview.png) | The building blocks and how they relate |
| [2. Identity](https://github.com/mlqube/.github/blob/main/docs/diagrams/mlqube_2_identity.png) | How people are authenticated and authorized, and how workloads get cloud access |
| [3. Management cluster and shared services](https://github.com/mlqube/.github/blob/main/docs/diagrams/mlqube_3_management.png) | What runs in the management cluster and how it uses shared AWS services |
| [4. Training, testing and serving](https://github.com/mlqube/.github/blob/main/docs/diagrams/mlqube_4_ml_lifecycle.png) | One model's path from Python code to a canary in prod |
| [5. Full view](https://github.com/mlqube/.github/blob/main/docs/diagrams/mlqube_5_enterprise.png) | All parts joined together |

## Built on open source

| Area | Projects |
|---|---|
| Cloud & infrastructure | AWS: Amazon EKS, S3, ECR, RDS (first) · Terraform |
| Portal | Backstage |
| GitOps & platform APIs | Argo CD, Crossplane |
| Scheduling & quotas | Kueue, GPU Operator, Karpenter |
| ML jobs & pipelines | Argo Workflows + Hera (Python SDK) |
| Distributed training | Kubeflow Trainer, KubeRay |
| Tracking & registry | MLflow |
| Serving | KServe, vLLM, KEDA |
| Identity, tenancy & policy | AWS IAM Identity Center (SSO through Dex), Capsule, Kyverno, External Secrets, gVisor |
| Observability & cost | Prometheus, Grafana, OpenTelemetry, OpenCost |

## Learn more

- 💡 [Why an organization needs an ML platform](https://github.com/mlqube/.github/blob/main/docs/why-an-ml-idp.md)
- 📖 [Vision](https://github.com/mlqube/.github/blob/main/docs/vision.md)
- 🏗️ [Architecture](https://github.com/mlqube/.github/blob/main/docs/architecture.md)
- 🗺️ [Roadmap](https://github.com/mlqube/.github/blob/main/docs/roadmap.md)
- 📝 [Architecture decision records](https://github.com/mlqube/.github/tree/main/docs/adr)

Ideas and feedback are welcome. Please open an issue in this repository.
