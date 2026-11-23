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
| [`cert-manager/`](cert-manager.md) | cert-manager: TLS certificates inside the clusters, plus the internal CA (`ClusterIssuer` `mlqube-internal-ca`) from [`platform/cert-manager`](https://github.com/mlqube/gitops/tree/main/platform/cert-manager) | `jetstack/cert-manager` v1.21.3 | `cert-manager` | none |
| [`kyverno/`](kyverno.md) | Kyverno policy engine, plus the Pod Security baseline policies (Kyverno's `kyverno-policies` chart, **Audit** mode) | `kyverno` 3.9.2, `kyverno-policies` 3.9.2 | `kyverno` | none |
| [`external-secrets/`](external-secrets.md) | External Secrets Operator: secrets from AWS Secrets Manager into Kubernetes Secrets, plus the `ClusterSecretStore` `aws-secrets-manager` from [`platform/external-secrets`](https://github.com/mlqube/gitops/tree/main/platform/external-secrets) | `external-secrets` 2.14.0 | `external-secrets` | role for `external-secrets`, read-only, secrets `mlqube/platform/*` only |

## Argo CD projects: what each Application may do

Every Application belongs to an Argo CD **AppProject**, a fence that limits which repositories it may pull from, which clusters and namespaces it may deploy into, and which kinds of objects it may create. Argo CD refuses to sync anything outside it (`... is not permitted in project ...`).

| Project | Defined in | Used by | Allows |
|---|---|---|---|
| `bootstrap` | Terraform, with the root Application ([`main.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/main.tf)) | `root` only | The gitops repository; mgmt's `argocd` namespace; only ApplicationSets, AppProjects and repository Secrets; no cluster-wide kinds |
| `platform` | [`projects/platform.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/projects/platform.yaml) | Every add-on ApplicationSet | The gitops repository and the add-ons' chart repositories; any registered cluster, but only the namespaces `kube-system`, `karpenter`, `external-secrets`, `cert-manager` and `kyverno`; only the cluster-wide kinds the add-ons create (CRDs, ClusterRoles and bindings, webhook configurations, Namespace, IngressClass and IngressClassParams, NodePool, EC2NodeClass, ClusterSecretStore, ClusterIssuer, ValidatingPolicy). `ResourceQuota` and `LimitRange` are forbidden: they belong to the tenancy setup |
| `default` | [`projects/default.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/projects/default.yaml) | Nothing | Nothing. Argo CD's built-in project allows everything and can't be deleted, so it is emptied; an Application left in it by mistake can't deploy. Don't delete the file, or Argo CD recreates `default` wide open |
| `<tenant>` (Phase 2) | Tenant onboarding | That tenant's Applications | The tenant's own repositories, only its `<tenant>-*` namespaces on the workload clusters, no cluster-wide kinds; roles mapped to its Identity Center groups |

The projects sync first (sync wave `-1`), before the ApplicationSets that use them. **A new add-on** adds to `platform`, in the same pull request: its chart repository (`sourceRepos`), its namespace (`destinations`) and any cluster-wide kind not yet listed (`clusterResourceWhitelist`). To find those kinds, render the chart with `helm template --include-crds` and look for kinds without a namespace. An Application whose destination has no namespace (cluster-wide objects only, like the NodePools) still names one that the project allows (`karpenter`).

## Which clusters, and their values

The clusters come from the **cluster secrets** Terraform writes in mgmt's `argocd` namespace ([`argocd_clusters.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/argocd_clusters.tf)), one per cluster in its `clusters` variable. Every ApplicationSet selects `mlqube/addons: "true"` and reads the rest from the secret:

| Cluster | Role | Reached at | `mlqube/vpc-name` (label) | `mlqube/dns-domain` (annotation) |
|---|---|---|---|---|
| `mgmt` | hub | in-cluster (`https://kubernetes.default.svc`) | `mlqube-mgmt` | `mlqube.click` |
| `wl-nonprod` | spoke | its private EKS API, over the VPC peering, signing in as Argo CD's IAM role (Pod Identity; EKS access entry in wl-nonprod) | `mlqube-nonprod` | `nonprod.mlqube.click` |

So today each ApplicationSet creates two Applications, e.g. `mgmt-external-dns` and `wl-nonprod-external-dns`. A new cluster gets every shared add-on as soon as Terraform registers it. Prod (Phase 5) will be registered the same way.

## Conventions

- `projects/`: the Argo CD projects (above).
- One folder per add-on: its ApplicationSet(s) (`applicationset.yaml`), a README with what it does and what it creates, and pictures. `root` applies every YAML file under this folder and ignores READMEs and images.
- Each add-on's AWS role is created **before** Argo CD installs it: Terraform's `addons-mgmt` layer ([`app_pod_identity.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/app_pod_identity.tf)) makes one role per cluster and binds it to the service account name used here. A role and its service account name must match on both sides.
- `<cluster>-karpenter-nodepools`, `<cluster>-external-secrets-stores`, `<cluster>-cert-manager-issuers` and `<cluster>-kyverno-policies` need their add-on's CRDs; on the first sync they retry until the add-on has installed them (sync waves: [mlqube/.github#13](https://github.com/mlqube/.github/issues/13)).
- An add-on only one cluster needs gets a plain `Application` here instead, with that cluster's `server` as its destination.
