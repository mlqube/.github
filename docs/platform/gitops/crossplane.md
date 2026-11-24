# Crossplane (mgmt)

> Describes the code in [mlqube/gitops · `clusters/mgmt/crossplane/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/crossplane) and [`platform/crossplane/providers/`](https://github.com/mlqube/gitops/tree/main/platform/crossplane/providers), and its access in [mlqube/infrastructure · `crossplane.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/crossplane.tf). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

> **Status:** 🕓 written (the engine, its providers and their access); first test at the next build. The glue's own APIs (`Tenant`, `MLProject`) come next.

**Crossplane is the engine behind [the MlQube glue](../../glue.md).** It lets the platform define its own Kubernetes APIs, such as a `Tenant`, and turns each object of such an API into everything it implies: namespaces, queues and permissions in the workload clusters, and IAM roles, S3 buckets, ECR repositories and secrets in AWS. It keeps them in that state, like Argo CD does for Git.

It runs in **mgmt only**, as an Argo CD app like the other add-ons, and reaches the workload clusters from there.

## The pieces

| Piece | What it is | MlQube |
|---|---|---|
| **Core** | The engine: package manager, composition engine | Helm chart, Application `mgmt-crossplane` |
| **Providers** | Plug-ins that manage one kind of external system, each object a *managed resource* | provider-kubernetes; provider-aws-iam, -s3, -ecr, -secretsmanager, -eks (with provider-family-aws) |
| **Functions** | Steps a Composition runs to render its resources | function-go-templating, function-auto-ready |
| **ClusterProviderConfigs** | How a provider signs in | `default` (AWS, Pod Identity); `wl-nonprod` (provider-kubernetes) |
| **XRDs and Compositions** | Our APIs and their logic | Next step: repository `mlqube/xrd-tenancy`; the requests in one `tenant-<id>` repository per tenant ([ADR-0018](../../adr/0018-tenancy-through-crossplane-and-tenant-repos.md)) |

## What exists, and who creates it

| What | Created by | Where |
|---|---|---|
| Namespace `crossplane-system` | Terraform, `addons-mgmt` [`crossplane.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/crossplane.tf) | mgmt |
| Crossplane core and RBAC manager (Crossplane creates its own CRDs at start) | Argo CD, ApplicationSet `crossplane` (`mgmt-crossplane`) | mgmt |
| Providers, functions, DeploymentRuntimeConfigs, ClusterProviderConfigs | Argo CD, ApplicationSet `crossplane-providers` (`mgmt-crossplane-providers`), from `platform/crossplane/providers/` | mgmt |
| IAM role `mgmt-crossplane-aws` + permissions boundary `mlqube-boundary-tenant` | Terraform, same file | AWS |
| IAM role `mgmt-crossplane-k8s` (no AWS permissions) + EKS access entry in each workload cluster | Terraform, same file | AWS, wl-nonprod |
| Secret `crossplane-system/wl-nonprod-kubeconfig` (address and CA only) | Terraform, same file, rewritten on every build | mgmt |

Both ApplicationSets have a one-element list generator (`cluster: mgmt`), the convention for single-cluster add-ons ([`clusters/mgmt`](clusters-mgmt.md)).

## How the providers sign in

```
provider-aws-* pods (crossplane-system) ──Pod Identity──► role mgmt-crossplane-aws ──► AWS APIs
                                                           (tenant-named resources only)

provider-kubernetes pod ──Pod Identity──► role mgmt-crossplane-k8s
      │   EKS token signed for "wl-nonprod"
      └──► wl-nonprod private API (VPC peering) ──► access entry ──► cluster-admin
```

Each provider runs as a service account with a fixed name (a `DeploymentRuntimeConfig` per provider), which Terraform binds to its role before the pods start. No keys anywhere. provider-kubernetes gets the workload cluster's address and CA from the Secret above; the token comes from its own AWS identity, the same way Argo CD reaches the spokes.

## What Crossplane may do in AWS

The AWS providers' role is fenced to **tenant-named resources**, so a mistake in a Composition (or a compromised provider) can't touch the platform itself:

| Resource | Allowed names | Notes |
|---|---|---|
| IAM roles | `mlqube-tenant-*` | Only created **with the boundary `mlqube-boundary-tenant`**; only `mlqube-tenant-*` policies can be attached |
| IAM policies | `mlqube-tenant-*` | The boundary itself is named differently, so Crossplane can't change it |
| Passing roles | `mlqube-tenant-*`, only to EKS Pod Identity | |
| Pod Identity associations | In the workload clusters only | |
| S3 buckets | `mlqube-tenant-*` | Bucket settings; not the objects inside |
| ECR repositories | `mlqube/tenants/*` | Repository settings; not the images |
| Secrets Manager | `mlqube/tenants/*` | |

**The boundary** `mlqube-boundary-tenant` is the most any tenant role can ever do: its tenant buckets, pull and push to tenant repositories, read tenant secrets. Each tenant's own policy (written by the glue) narrows that to the tenant itself. MLflow's bucket prefix joins the boundary with MLflow (golden path v0, section 4).

In the workload clusters, provider-kubernetes is **cluster-admin**, like Argo CD: the glue creates namespaces, cluster-wide ClusterQueues and RBAC, and in Kubernetes you can only grant rights you hold. A dedicated, narrower ClusterRole is a later hardening step.

## Settings

| Setting | Value | Why |
|---|---|---|
| Chart | `crossplane-stable/crossplane` **2.4.3** (released 2026-10-22) | At least two weeks old when chosen |
| Providers | provider-aws-* and provider-family-aws **v2.9.0**, provider-kubernetes **v1.4.1**, from `xpkg.crossplane.io/crossplane-contrib` | Same rule |
| Functions | function-go-templating **v0.13.2**, function-auto-ready **v0.7.3** | Same rule |
| Managed resource activation | Only the namespaced (`.m.`) kinds of IAM, S3, ECR, Secrets Manager, EKS and Kubernetes | An AWS provider otherwise brings a CRD for every kind of its service |
| provider-family-aws | Listed explicitly, under the name Crossplane gives a dependency (`crossplane-contrib-provider-family-aws`) | So Crossplane doesn't install a second, unpinned copy |
| Replicas | 1 core, 1 RBAC manager | Reference build |

## Checking it (next build)

```bash
kubectl --context mgmt -n crossplane-system get pods
kubectl --context mgmt get providers,functions          # INSTALLED and HEALTHY: True
kubectl --context mgmt get clusterproviderconfigs.aws.m.upbound.io,clusterproviderconfigs.kubernetes.m.crossplane.io
kubectl --context mgmt get managedresourcedefinitions | grep -c Active   # only the activated kinds
```

- [ ] Apps `mgmt-crossplane` and `mgmt-crossplane-providers` Healthy
- [ ] Every provider and function `HEALTHY: True`; only one provider-family-aws
- [ ] AWS sign-in works: a test `Bucket` named `mlqube-tenant-test-<random>` is created, and one named anything else is refused (`AccessDenied`); then deleted
- [ ] wl-nonprod sign-in works: a test `Object` (a ConfigMap in `default`) appears in wl-nonprod; then deleted

| Symptom | Likely cause | Check |
|---|---|---|
| AWS managed resource: `no EC2 IMDS role found` or `AccessDenied` for the provider's own identity | The Pod Identity association is missing, or the pod started before it existed | `aws eks list-pod-identity-associations --cluster-name mgmt --namespace crossplane-system`; restart the provider's pod |
| provider-kubernetes: `Unauthorized` from wl-nonprod | Access entry missing, or the kubeconfig's cluster name isn't the EKS cluster name | `aws eks list-access-entries --cluster-name wl-nonprod`; the Secret's `current-context` cluster |
| provider-kubernetes: timeout to wl-nonprod | The API isn't reachable from mgmt's pods | Argo CD reaches it the same way: compare with `argocd cluster list` |
| Two provider-family-aws | The family Provider's name changed | It must be `crossplane-contrib-provider-family-aws` |

## Destroy

Nothing in this step creates AWS resources. Once the glue creates tenants, the destroy workflow deletes the tenant Applications and waits until no `Tenant` is left **before** it destroys the add-ons layer; otherwise their AWS resources would stay behind. Buckets and ECR repositories are kept on purpose (`deletionPolicy: Orphan`) and taken back over by the next build ([ADR-0018](../../adr/0018-tenancy-through-crossplane-and-tenant-repos.md)).

## Related

- [The MlQube glue](../../glue.md) · [External Secrets](external-secrets.md) · [`clusters/mgmt`](clusters-mgmt.md)
- [Golden path v0 plan](../../golden-path-v0-plan.md) · [ADR-0016](../../adr/0016-golden-path-v0.md)
