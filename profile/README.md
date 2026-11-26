# MlQube

**An internal developer platform for ML and AI teams on Amazon EKS: self-service GPU training, a model registry and serving, one tenant per business unit.**

Designed and built end to end by **[Dilip Kumar Samanta](https://www.linkedin.com/in/dilipsamanta/)**: architecture, Terraform, GitOps, identity, tenancy and docs.

![Phase 1](https://img.shields.io/badge/Phase%201-tested%20live%20Nov%202026-2ea44f) ![Next](https://img.shields.io/badge/next-golden%20path%20v0-0969da) ![ADRs](https://img.shields.io/badge/architecture%20decisions-17-6f42c1) ![AWS](https://img.shields.io/badge/AWS-EKS-ff9900) ![IaC](https://img.shields.io/badge/IaC-Terraform-7b42bc) ![GitOps](https://img.shields.io/badge/GitOps-Argo%20CD-ef7b4d)

**[Architecture](https://github.com/mlqube/.github/blob/main/docs/architecture.md)** · **[Decisions](https://github.com/mlqube/.github/blob/main/docs/adr/README.md)** · **[What runs today](https://github.com/mlqube/.github/blob/main/README.md#what-runs-in-the-clusters)** · **[Roadmap](https://github.com/mlqube/.github/blob/main/docs/roadmap.md)** · **[Platform docs](https://github.com/mlqube/.github/blob/main/docs/platform/README.md)**

---

## What runs today

Phase 1 was built and tested live in November 2026. The whole platform is created from code for each working session and destroyed afterwards.

- **Two private EKS clusters**, management and non-prod, in their own VPCs with no public subnets. They are built and destroyed **only from GitHub Actions**, never from a laptop.
- **One Argo CD in the management cluster** deploys about a dozen add-ons to both clusters from Git. The workload clusters run no Argo CD of their own.
- **Nodes on demand with Karpenter:** a spot CPU node in about 40 s. **NVIDIA L4 GPU nodes** come up in about 60 s and are removed once the work is done.
- **Single sign-on** for people through AWS IAM Identity Center and Dex. Workloads use EKS Pod Identity. **No static cloud keys** anywhere.
- **CI reaches the private cluster APIs** over Tailscale with workload identity federation, so no secret is stored for it.
- **Platform services:** internal load balancers with private DNS and TLS, secrets from AWS Secrets Manager, and Kyverno policies.

[![MlQube: high-level architecture](https://raw.githubusercontent.com/mlqube/.github/main/docs/diagrams/mlqube_1_overview.png)](https://github.com/mlqube/.github/blob/main/docs/architecture.md)

<sub>The [architecture document](https://github.com/mlqube/.github/blob/main/docs/architecture.md) walks through six views: identity, the management cluster, a model's path from code to a canary in prod, and GitOps hub and spoke.</sub>

## Engineering highlights

The parts that took the most thought, each with its write-up:

| | |
|---|---|
| **A platform that exists only when needed** | GPUs and EKS cost money even when idle, so the platform is rebuilt for each session. Build and destroy run in dependency order, with guard rails that refuse to destroy a layer something still depends on. Before the clusters go, anything the add-ons created in AWS is removed: nodes, load balancers and tenants. [Platform workflow](https://github.com/mlqube/.github/blob/main/docs/platform/README.md) |
| **Private by default, and CI can still deploy** | The cluster APIs aren't public. GitHub Actions joins the tailnet as a short-lived device with workload identity federation and deploys over private routes. [ADR-0011](https://github.com/mlqube/.github/blob/main/docs/adr/0011-private-access-reference-build.md) · [ADR-0014](https://github.com/mlqube/.github/blob/main/docs/adr/0014-ci-access-to-private-clusters.md) |
| **GitOps hub and spoke** | One Argo CD deploys to every cluster. Argo CD projects fence what each set of Applications may touch: which repositories, which namespaces, and which cluster-wide kinds. [GitOps hub](https://github.com/mlqube/.github/blob/main/docs/architecture.md#6-gitops-hub-and-spoke) |
| **One identity hub** | People sign in through IAM Identity Center (SAML), and Dex hands every tool an OIDC login with the user's groups. [ADR-0015](https://github.com/mlqube/.github/blob/main/docs/adr/0015-iam-identity-center-identity-hub.md) · [sign-in flow](https://github.com/mlqube/.github/blob/main/docs/platform/gitops/dex.md) |
| **Tenancy as an API** | A business unit is a `Tenant`; its ML projects are `MLProject`s. Crossplane turns them into namespaces, Kueue GPU quotas, IAM roles, S3 buckets, ECR repositories and CI roles. Its AWS permissions are fenced to tenant-named resources under a permissions boundary. Each tenant's request lives in its own Git repository, which Argo CD discovers automatically. Written and render-tested in CI; first live test with golden path v0. [The glue](https://github.com/mlqube/.github/blob/main/docs/glue.md) · [ADR-0018](https://github.com/mlqube/.github/blob/main/docs/adr/0018-tenancy-through-crossplane-and-tenant-repos.md) |
| **Fair GPU sharing** | Kueue queues jobs per tenant within its GPU quota. Runs from `main` preempt feature-branch runs, and idle quota is lent to other tenants. Written; first live test with golden path v0. [Kueue](https://github.com/mlqube/.github/blob/main/docs/platform/gitops/kueue.md) |

## How it's built

- **Decisions are written down first:** 17 [architecture decision records](https://github.com/mlqube/.github/blob/main/docs/adr/README.md), each with the options considered and the consequences.
- **Everything as code:** Terraform for AWS, Argo CD for Kubernetes, Crossplane Compositions with render tests in CI, and diagrams generated from Python.
- **Safety nets:** every change goes through a pull request, with pre-commit checks, secret scanning (gitleaks), Terraform plans in CI, and every chart and provider version pinned.
- **Docs an operator can follow:** [setup](https://github.com/mlqube/.github/blob/main/docs/platform/setup.md), [secrets and rotation](https://github.com/mlqube/.github/blob/main/docs/platform/secrets.md), [troubleshooting](https://github.com/mlqube/.github/blob/main/docs/platform/troubleshooting.md), and one page per Terraform layer and add-on.

## Where it's going

| | |
|---|---|
| ✅ **Done** | Phase 1, the AWS foundation: clusters, GitOps, nodes on demand (CPU and GPU), single sign-on, secrets, policies |
| 🔨 **Now** | [Golden path v0](https://github.com/mlqube/.github/blob/main/docs/golden-path-v0-plan.md): tenants through Crossplane, then an ML engineer goes from a feature branch to a GPU training run to a registered model in MLflow ([how it works](https://github.com/mlqube/.github/blob/main/docs/golden-path.md)) |
| 🗺️ **Next** | Model serving with KServe and vLLM, promotion through GitOps, the Backstage portal, and cost per business unit with OpenCost ([roadmap](https://github.com/mlqube/.github/blob/main/docs/roadmap.md)) |

<details>
<summary><b>Why an ML platform at all?</b></summary>

ML teams lose time on infrastructure: GPU quotas, CUDA images, training setup, serving stacks, model promotion and cost tracking. Without standard paths every deployment is a custom project, GPUs sit idle while other teams wait, and costs can't be traced to a business unit. MlQube turns that into **self-service golden paths**: ML teams ship faster, the platform team keeps control, and finance sees where the money goes. [The full case](https://github.com/mlqube/.github/blob/main/docs/why-an-ml-idp.md) · [vision](https://github.com/mlqube/.github/blob/main/docs/vision.md)

</details>

<details>
<summary><b>Built on open source</b></summary>

Amazon EKS · Terraform · Argo CD · Karpenter · Kueue · Crossplane · Dex · Kyverno · External Secrets · cert-manager · AWS Load Balancer Controller · ExternalDNS · Argo Workflows + Hera. Planned: MLflow · KServe · vLLM · Backstage · Capsule · Prometheus · Grafana · OpenCost. Status of each one: [what runs in the clusters](https://github.com/mlqube/.github/blob/main/README.md#what-runs-in-the-clusters).

</details>

## About

I design and build platforms on Kubernetes and AWS. MlQube is my reference build: every decision, diagram and runbook is public here. The Terraform and GitOps code is in private repositories; I'm happy to walk through it.

**[Connect on LinkedIn](https://www.linkedin.com/in/dilipsamanta/)** · questions and feedback: [open an issue](https://github.com/mlqube/.github/issues)
