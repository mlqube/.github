# cert-manager (every cluster)

> Describes the code in [mlqube/gitops · `clusters/mgmt/cert-manager/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/cert-manager) and [`platform/cert-manager/`](https://github.com/mlqube/gitops/tree/main/platform/cert-manager). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

Issues and renews **TLS certificates for traffic inside the clusters**: one service calling another over HTTPS, admission webhooks of later add-ons, and so on. You ask for a certificate with a `Certificate` object; cert-manager creates its key and certificate in a Kubernetes Secret and renews it before it expires.

**What it doesn't do:** browser traffic. Portals such as `https://argocd.mlqube.click` are reached through the internal ALB, which presents the **ACM** certificate for `*.mlqube.click` ([ADR-0010](../../adr/0010-ingress.md)). Nobody outside a cluster ever sees a cert-manager certificate.

## The internal CA

Each cluster has its own small certificate authority, made by cert-manager itself in three steps ([`issuers.yaml`](https://github.com/mlqube/gitops/blob/main/platform/cert-manager/issuers.yaml)):

| Step | Object | What it is |
|---|---|---|
| 1 | `ClusterIssuer` **`selfsigned-bootstrap`** | A self-signed issuer, used only to create the CA in step 2 |
| 2 | `Certificate` **`mlqube-internal-ca`** (namespace `cert-manager`) | The CA: an ECDSA P-256 key and certificate, valid one year, in Secret `cert-manager/mlqube-internal-ca`. Each cluster makes its own; every build makes a new one |
| 3 | `ClusterIssuer` **`mlqube-internal-ca`** | The issuer every in-cluster certificate uses. It signs with the CA from step 2 |

A workload trusts certificates from this CA through the `ca.crt` key that cert-manager puts in every certificate Secret it issues. If many workloads need that CA certificate, trust-manager can later copy it into each namespace.

Asking for a certificate (example):

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: my-service-tls
  namespace: my-namespace
spec:
  secretName: my-service-tls # Secret with tls.crt, tls.key and ca.crt
  dnsNames:
    - my-service.my-namespace.svc
    - my-service.my-namespace.svc.cluster.local
  issuerRef:
    kind: ClusterIssuer
    name: mlqube-internal-ca
```

## What exists, and who creates it

| Created by | What |
|---|---|
| **Argo CD**, [`applicationset.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/cert-manager/applicationset.yaml) | cert-manager: Helm chart **v1.21.3**, namespace `cert-manager`, one Application per cluster (`<cluster>-cert-manager`). Three deployments: the controller, its admission webhook and the CA injector (which puts CA certificates into webhook configurations) |
| **Argo CD**, [`issuers-applicationset.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/cert-manager/issuers-applicationset.yaml) | [`platform/cert-manager/`](https://github.com/mlqube/gitops/tree/main/platform/cert-manager) on every cluster (`<cluster>-cert-manager-issuers`): the two ClusterIssuers and the CA certificate |
| **cert-manager, at runtime** | The CA Secret, and a Secret for every `Certificate` anyone asks for |
| **Terraform** | Nothing: cert-manager needs no AWS permissions (no public certificates, no Route 53) |

The issuers Application needs cert-manager's CRDs. On the first sync it retries until `<cluster>-cert-manager` has installed them (sync waves: [mlqube/.github#13](https://github.com/mlqube/.github/issues/13)).

## Settings

| Value | Why |
|---|---|
| `crds.enabled: true`, `crds.keep: true` | The chart installs the CRDs, and keeps them if the add-on is removed, so removing it never deletes every `Certificate` in the cluster. `ServerSideApply=true`, because the CRDs are large |
| `global.leaderElection.namespace: cert-manager` | The chart puts its leader-election lock in `kube-system` by default; this keeps everything in its own namespace |
| `startupapicheck.enabled: false` | A Helm post-install test job. Argo CD would rerun it after every sync, and its health checks already show whether cert-manager is up |
| `fullnameOverride: cert-manager` | Plain object names (`cert-manager`, `cert-manager-webhook`, ...) instead of names derived from the Application name |
| `replicaCount: 1` (controller, webhook, CA injector) | Reference build; two each in production |

## Checking it (once the platform runs)

```bash
kubectl get clusterissuer                              # selfsigned-bootstrap and mlqube-internal-ca, READY True
kubectl -n cert-manager get certificate mlqube-internal-ca   # READY True
```

A quick end-to-end test: apply a `Certificate` like the example above in any namespace, check that it becomes `READY True` and that its Secret holds `tls.crt`, `tls.key` and `ca.crt`. Then delete it.
