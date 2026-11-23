# Platform documentation

How the MlQube platform is built, run and debugged: every operational document for the code repositories lives here, next to the [vision](../vision.md), [architecture](../architecture.md), [roadmap](../roadmap.md) and [ADRs](../adr/README.md). The code itself stays in its own (private) repositories:

| Repository | Holds |
|---|---|
| [`mlqube/infrastructure`](https://github.com/mlqube/infrastructure) | Terraform for AWS (network, EKS clusters, Argo CD bootstrap and the add-ons' AWS roles), the bootstrap stack, the GitHub Actions workflows that create and destroy the platform |
| [`mlqube/gitops`](https://github.com/mlqube/gitops) | The desired state of the clusters: Argo CD ApplicationSets and add-on settings, applied by Argo CD |

Account-specific identifiers are written as placeholders: `<account-id>` (AWS account), `<org-id>` and `<repo-id>` (GitHub's immutable IDs for the organization and the `infrastructure` repository). Look them up with `aws sts get-caller-identity --query Account`, `gh api orgs/mlqube -q .id` and `gh api repos/mlqube/infrastructure -q .id`. No secret values are stored in any document: only where each secret lives.

## Start here

| Document | Read it when |
|---|---|
| [Setup](setup.md) | Setting up from zero: tools, sign-in, bootstrap, domain, certificate, Tailscale, keys, single sign-on, first build (ordered checklist) |
| [Secrets and trust](secrets.md) | Looking for a secret or trust relationship: where it lives, who uses it, **when it expires**, how to rotate it, what to do if it leaks |
| [Troubleshooting](troubleshooting.md) | Something failed: symptoms, causes and fixes for the problems met so far |

## Infrastructure (`mlqube/infrastructure`)

| Document | Covers | Code |
|---|---|---|
| [Overview](infrastructure/README.md) | Repository layout, the workflows (`platform`, `terraform-plan`, `terraform-layer`), the layers and their cost, a typical test session, Makefile helpers, checks | [repo root](https://github.com/mlqube/infrastructure) |
| [Bootstrap stack](infrastructure/bootstrap.md) | The one hand-deployed CloudFormation stack: GitHub OIDC, state bucket, plan and apply roles | [`bootstrap/`](https://github.com/mlqube/infrastructure/tree/main/bootstrap) |
| [`base` layer](infrastructure/base.md) | The permanent ACM certificate and split-horizon DNS | [`live/base/`](https://github.com/mlqube/infrastructure/tree/main/live/base) |
| [`network` layer](infrastructure/network.md) | VPCs, subnets, NAT, peering, private zone, Tailscale router | [`live/platform/network/`](https://github.com/mlqube/infrastructure/tree/main/live/platform/network) |
| [`mgmt` cluster](infrastructure/eks-mgmt.md) | The management EKS cluster, with a component diagram | [`live/platform/eks/mgmt/`](https://github.com/mlqube/infrastructure/tree/main/live/platform/eks/mgmt) |
| [`wl-nonprod` cluster](infrastructure/eks-wl-nonprod.md) | The non-prod workload EKS cluster, with a component diagram | [`live/platform/eks/wl-nonprod/`](https://github.com/mlqube/infrastructure/tree/main/live/platform/eks/wl-nonprod) |
| [`addons-mgmt` layer](infrastructure/addons-mgmt.md) | Argo CD bootstrap, hub and spoke registration, add-on roles, internal ALB, single sign-on, destroy cleanup | [`live/platform/addons/mgmt/`](https://github.com/mlqube/infrastructure/tree/main/live/platform/addons/mgmt) |
| [`eks-cluster` module](infrastructure/module-eks-cluster.md) | The shared EKS cluster module | [`modules/eks-cluster/`](https://github.com/mlqube/infrastructure/tree/main/modules/eks-cluster) |
| [`tailscale-router` module](infrastructure/module-tailscale-router.md) | The Tailscale subnet router, how it's created, and how you reach the clusters and URLs | [`modules/tailscale-router/`](https://github.com/mlqube/infrastructure/tree/main/modules/tailscale-router) |

## GitOps (`mlqube/gitops`)

| Document | Covers | Code |
|---|---|---|
| [Overview](gitops/README.md) | Repository layout, the app of apps, adding and changing add-ons | [repo root](https://github.com/mlqube/gitops) |
| [`clusters/mgmt`](gitops/clusters-mgmt.md) | What the hub Argo CD manages: ApplicationSets, which clusters and their values, conventions | [`clusters/mgmt/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt) |
| [AWS Load Balancer Controller](gitops/aws-load-balancer-controller.md) | Ingress → internal ALB, with the ingress flow diagram | [`clusters/mgmt/aws-load-balancer-controller/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/aws-load-balancer-controller) |
| [ExternalDNS](gitops/external-dns.md) | Private DNS records, with the DNS lookup diagram | [`clusters/mgmt/external-dns/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/external-dns) |
| [cert-manager](gitops/cert-manager.md) | TLS certificates inside the clusters; the internal CA | [`clusters/mgmt/cert-manager/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/cert-manager) |
| [Kyverno](gitops/kyverno.md) | Policy engine; Pod Security baseline policies in Audit mode; moving to Enforce | [`clusters/mgmt/kyverno/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/kyverno) |
| [metrics-server](gitops/metrics-server.md) | CPU and memory use for `kubectl top` and autoscaling | [`clusters/mgmt/metrics-server/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/metrics-server) |
| [External Secrets](gitops/external-secrets.md) | Secrets from AWS Secrets Manager into Kubernetes Secrets; who may read what | [`clusters/mgmt/external-secrets/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/external-secrets) |
| [Karpenter](gitops/karpenter.md) | Nodes on demand, with the Karpenter flow diagram | [`clusters/mgmt/karpenter/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/karpenter) |

## Diagrams

All pictures are in [`images/`](images/) and generated from Python scripts in [`docs/diagrams/platform/`](../diagrams/platform/) (Python with `diagrams`, and Graphviz), using the shared icons in [`docs/diagrams/icons/`](../diagrams/icons/). From the root of this repository:

| Picture | Script | Used in |
|---|---|---|
| `eks-mgmt-components.png`, `eks-wl-nonprod-components.png` | `python docs/diagrams/platform/cluster_diagrams.py` | [mgmt](infrastructure/eks-mgmt.md), [wl-nonprod](infrastructure/eks-wl-nonprod.md) |
| `tailscale-access.png` | `python docs/diagrams/platform/access_diagram.py` | [tailscale-router](infrastructure/module-tailscale-router.md) |
| `app-of-apps.png` | `python docs/diagrams/platform/app_of_apps.py` | [GitOps overview](gitops/README.md) |
| `karpenter-flow.png`, `ingress-flow.png`, `dns-lookup.png` | `python docs/diagrams/platform/addon_diagrams.py` | [Karpenter](gitops/karpenter.md), [load balancer controller](gitops/aws-load-balancer-controller.md), [ExternalDNS](gitops/external-dns.md) |

The architecture views (1–6) are in [`docs/diagrams/`](../diagrams/) and described in [architecture.md](../architecture.md).
