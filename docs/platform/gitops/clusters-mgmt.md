# clusters/mgmt

> Describes the code in [mlqube/gitops · `clusters/mgmt/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

What the **hub** Argo CD manages. Argo CD runs only in the `mgmt` cluster; its **root Application** (`root`, created by Terraform in [`infrastructure/live/platform/addons/mgmt`](../infrastructure/addons-mgmt.md)) applies every Kubernetes manifest in this folder and its subfolders **to mgmt's `argocd` namespace**, and keeps it in sync (automated sync, prune, self-heal). The workload clusters run no Argo CD (hub and spoke, see the [architecture, view 6](../../architecture.md#6-gitops-hub-and-spoke)).

## Shared add-ons: one ApplicationSet each

Each shared add-on is an **ApplicationSet** with a *cluster generator*: it creates one Application per registered cluster, named `<cluster>-<add-on>`, and deploys it to that cluster with that cluster's values.

| Folder | Installs | Chart (pinned) | Namespace | AWS permissions per cluster (EKS Pod Identity, from Terraform) |
|---|---|---|---|---|
| [`aws-load-balancer-controller/`](aws-load-balancer-controller.md) | AWS Load Balancer Controller: Ingress → internal ALB (ADR-0010) | `eks-charts/aws-load-balancer-controller` 3.6.2 | `kube-system` | role for `aws-load-balancer-controller` |
| [`external-dns/`](external-dns.md) | ExternalDNS: each cluster's names in the **private** zone | `external-dns` 1.23.0 | `kube-system` | role for `external-dns`, private zone only |
| [`karpenter/`](karpenter.md) | Karpenter: starts and stops nodes on demand, plus each cluster's NodePools from [`platform/karpenter/<cluster>`](https://github.com/mlqube/gitops/tree/main/platform/karpenter) | `public.ecr.aws/karpenter/karpenter` 1.14.3 (OCI) | `karpenter` | role for `karpenter`, node role `karpenter-node-<cluster>`, interruption queue `karpenter-<cluster>` |

## Which clusters, and their values

The clusters come from the **cluster secrets** Terraform writes in mgmt's `argocd` namespace ([`argocd_clusters.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/argocd_clusters.tf)), one per cluster in its `clusters` variable. Every ApplicationSet selects `mlqube/addons: "true"` and reads the rest from the secret:

| Cluster | Role | Reached at | `mlqube/vpc-name` (label) | `mlqube/dns-domain` (annotation) |
|---|---|---|---|---|
| `mgmt` | hub | in-cluster (`https://kubernetes.default.svc`) | `mlqube-mgmt` | `mlqube.click` |
| `wl-nonprod` | spoke | its private EKS API, over the VPC peering, signing in as Argo CD's IAM role (Pod Identity; EKS access entry in wl-nonprod) | `mlqube-nonprod` | `nonprod.mlqube.click` |

So today each ApplicationSet creates two Applications, e.g. `mgmt-external-dns` and `wl-nonprod-external-dns`. A new cluster gets every shared add-on as soon as Terraform registers it. Prod (Phase 5) will be registered the same way.

## Conventions

- One folder per add-on: its ApplicationSet(s) (`applicationset.yaml`), a README with what it does and what it creates, and pictures. `root` applies every YAML file under this folder and ignores READMEs and images.
- Each add-on's AWS role is created **before** Argo CD installs it: Terraform's `addons-mgmt` layer ([`app_pod_identity.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/app_pod_identity.tf)) makes one role per cluster and binds it to the service account name used here. A role and its service account name must match on both sides.
- `<cluster>-karpenter-nodepools` needs Karpenter's CRDs; on the first sync it retries until `<cluster>-karpenter` has installed them (sync waves: [mlqube/.github#13](https://github.com/mlqube/.github/issues/13)).
- An add-on only one cluster needs gets a plain `Application` here instead, with that cluster's `server` as its destination.
