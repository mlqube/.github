# External Secrets Operator (every cluster)

> Describes the code in [mlqube/gitops · `clusters/mgmt/external-secrets/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/external-secrets) and [`platform/external-secrets/`](https://github.com/mlqube/gitops/tree/main/platform/external-secrets). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

Secrets never live in Git. They live in **AWS Secrets Manager**, and the External Secrets Operator copies each one the platform needs into a Kubernetes **Secret**, then keeps the copy up to date. A pod uses that Secret as usual; nobody pastes secret values into manifests or the cluster.

## How it works

| Step | What happens |
|---|---|
| 1 | Someone stores the value in Secrets Manager under `mlqube/platform/<add-on>/<name>` (console or CLI; never in Git). |
| 2 | An **`ExternalSecret`** in Git (next to the add-on that needs it) says: take secret `mlqube/platform/<add-on>/<name>` from the store `aws-secrets-manager`, and make a Kubernetes Secret called `<x>` in this namespace. It names the secret; it holds no value. |
| 3 | The operator reads the value with its own AWS role (EKS Pod Identity, no keys) and creates or updates the Kubernetes Secret. |
| 4 | It checks again every refresh interval (one hour by default, per `ExternalSecret`), so a value changed in Secrets Manager reaches the cluster without a commit. |

Example: an add-on's `ExternalSecret` (this one is illustrative; real ones come with the add-ons that need them, e.g. Grafana's admin password with observability):

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: grafana-admin
  namespace: monitoring
spec:
  secretStoreRef:
    kind: ClusterSecretStore
    name: aws-secrets-manager
  target:
    name: grafana-admin # the Kubernetes Secret it creates
  data:
    - secretKey: admin-password
      remoteRef:
        key: mlqube/platform/grafana/admin # the Secrets Manager secret's name
        property: password # a key inside its JSON value
```

## Who may read what

| Layer | Limit |
|---|---|
| **IAM role** `<cluster>-external-secrets` (Terraform) | Read-only (`GetSecretValue`, `DescribeSecret`, ...) and only secrets named **`mlqube/platform/*`**. It can't create, change or delete secrets, and can't read anything else in the account (e.g. a future tenant's secrets) |
| **`ClusterSecretStore` `aws-secrets-manager`** | Usable from every namespace **except tenant namespaces** (namespaces labelled `mlqube/tenant`). Tenants get stores and roles of their own in Phase 2, limited to their own path |
| **Argo CD project `platform`** | The add-on may deploy only into `external-secrets`, plus the cluster-wide kinds it needs, the `ClusterSecretStore` among them ([projects](clusters-mgmt.md#argo-cd-projects-what-each-application-may-do)) |

## What exists, and who creates it

| Created by | What |
|---|---|
| **Terraform** (`addons-mgmt` layer) | IAM role + **Pod Identity association** `external-secrets/external-secrets`, **one per cluster** ([`app_pod_identity.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/app_pod_identity.tf)) |
| **Argo CD**, [`applicationset.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/external-secrets/applicationset.yaml) | The operator: Helm chart **2.14.0** (External Secrets Operator v2.14.0), namespace `external-secrets`, one Application per cluster (`<cluster>-external-secrets`). Three deployments: the controller, its admission webhook and the webhook's certificate controller |
| **Argo CD**, [`stores-applicationset.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/external-secrets/stores-applicationset.yaml) | [`platform/external-secrets/`](https://github.com/mlqube/gitops/tree/main/platform/external-secrets) on every cluster (`<cluster>-external-secrets-stores`): the `ClusterSecretStore` `aws-secrets-manager` (Secrets Manager, us-west-2). It has no `auth` block, so the operator uses its own Pod Identity role |
| **You** (console or CLI) | The secrets themselves, in Secrets Manager under `mlqube/platform/` |
| **The operator, at runtime** | The Kubernetes Secrets named by `ExternalSecret`s |

The stores Application needs the operator's CRDs. On the first sync it retries until `<cluster>-external-secrets` has installed them (as with Karpenter's NodePools; sync waves: [mlqube/.github#13](https://github.com/mlqube/.github/issues/13)).

## Settings

| Value | Why |
|---|---|
| `installCRDs: true` | The chart installs its CRDs (`ExternalSecret`, `ClusterSecretStore`, ...); with `ServerSideApply=true`, because they are too large for client-side apply |
| `serviceAccount.name: external-secrets` | Fixed name, so it matches the Pod Identity association Terraform creates (otherwise the name would come from the Application name) |
| `replicaCount: 1` (controller, webhook, cert controller) | Reference build; two each in production |

## Cost

Secrets Manager charges about **$0.40 per secret per month** plus $0.05 per 10,000 API calls. Secrets stay when the platform is destroyed, so they count toward the permanent cost. The operator reads through the NAT gateway; a Secrets Manager VPC endpoint exists in the network module but is off by default.

## Checking it (once the platform runs)

```bash
kubectl get clustersecretstore aws-secrets-manager   # STATUS Valid, READY True
kubectl get externalsecrets -A                       # STATUS SecretSynced
```

A quick end-to-end test: create a secret `mlqube/platform/test` in Secrets Manager with the value `{"hello":"world"}`, apply an `ExternalSecret` for it in any non-tenant namespace, and check that the Kubernetes Secret appears. Then delete both.
