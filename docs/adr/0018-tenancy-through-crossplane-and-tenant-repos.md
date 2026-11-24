# ADR-0018: Tenants through Crossplane, one repository per tenant

- **Status:** Accepted
- **Date:** 2026-11-24
- **Deciders:** platform team
- **Amends:** [ADR-0016](0016-golden-path-v0.md) decisions 1, 6 and 10; [ADR-0004](0004-tenancy-model.md) naming (2026-11-24)

## Context

[ADR-0016](0016-golden-path-v0.md) made golden path v0's first tenant (`retail-1042`, project `churn`) **by hand**: plain YAML in `gitops` plus Terraform, to be replaced by the glue later. That's a shortcut nobody would run in production, and it would be thrown away. Crossplane now runs in mgmt with its providers and their access ([Crossplane](../platform/gitops/crossplane.md)), so v0 can create tenants the real way from the start: through the glue's APIs ([the MlQube glue](../glue.md), [ADR-0006](0006-platform-apis-with-crossplane.md)).

Three questions follow: where the API definitions live, where each tenant's request lives, and how a customer's form in Backstage turns into a tenancy in the workload cluster and in AWS.

## Options considered

**Where the API (XRDs and Compositions) lives**

1. **In `gitops`** (`platform/crossplane/glue/`, the glue page's first plan). One repository fewer, but the API's changes, reviews and tests mix with every add-on change.
2. **Its own repository** (chosen). Own history, reviews, version tags and CI (render tests on every pull request); Argo CD applies it like any other source.

**Where a tenant's request (`Tenant`, `MLProject` objects) lives**

1. **In the cluster only:** Backstage applies the object directly. No record in Git, nothing recreates it after a rebuild, and Backstage needs write access to the cluster.
2. **One shared `tenants` repository:** one folder per tenant. Simple, but every tenant's requests share one history and one set of permissions.
3. **One repository per tenant** (chosen): Backstage creates `tenant-<id>` from the form; Argo CD discovers it. Each tenant has its own record and access list, and it's the natural home of the tenant's projects later.

**How Argo CD treats a tenant repository**

1. **Raw manifests** (namespaces, RBAC, quotas) applied straight to the workload cluster. Can't create the AWS side, and whoever can edit the repository could grant themselves anything.
2. **Only `Tenant` and `MLProject` objects**, applied to mgmt (chosen). The XRD limits what can be asked for; the Composition decides what's built.

## Decision

### 1. Two APIs, group `platform.mlqube.click`, version `v1alpha1`

| API | Scope | Lives in (mgmt) | Fields (v0) |
|---|---|---|---|
| `Tenant` | Cluster-wide | — | `displayName`, `costCenter`, `quota` (`gpu` max 8, `cpu`, `memory`), `groups` (Identity Center group IDs: **optional in v0**) |
| `MLProject` | Namespaced | The tenant's namespace `tenant-<id>`, created by its `Tenant` | `repository` (the project's GitHub repository) |

The tenant ID (the `Tenant`'s name) follows [ADR-0004](0004-tenancy-model.md): lowercase, at most 30 characters, and **can't change**, because it's part of every AWS name. A project belongs to the tenant whose namespace it's in, never to a tenant named in a field.

What they create:

| | `Tenant retail-1042` | `MLProject churn` |
|---|---|---|
| mgmt | Namespace `tenant-retail-1042` | — |
| wl-nonprod | ClusterQueue `retail-1042` (the quota) | Namespace `retail-1042-churn` (label `mlqube/tenant`), LocalQueues `dev` and `main`, ServiceAccounts `workflow` and `ci` with their RBAC, `ci`'s token |
| AWS | Role `mlqube-tenant-retail-1042-nonprod` (within the boundary `mlqube-boundary-tenant`), bucket `mlqube-tenant-retail-1042-nonprod` | ECR repository `mlqube/tenants/retail-1042/churn` (immutable tags, scan on push, `feat-*` expire after 14 days), Pod Identity `workflow` → the tenant role, GitHub CI role `mlqube-tenant-retail-1042-churn-ci` (trusts only the project repository; pushes to its ECR repository, reads its secret), the token in Secrets Manager `mlqube/tenants/retail-1042/churn/argo-ci` |

Not in v0: Capsule, default-deny NetworkPolicies, ResourceQuota and LimitRange, MLflow permissions (Phase 4), `Workspace` and `ModelDeployment`.

### 2. The definitions: repository `mlqube/xrd-tenancy` (private)

XRDs, Compositions, example objects and CI that renders every example with `crossplane render` and validates the output against the schemas on each pull request. Argo CD applies it to mgmt (ApplicationSet in `gitops`, project `platform`). Owned by the platform team.

### 3. The requests: one repository per tenant, `mlqube/tenant-<id>` (private)

```
tenant-retail-1042/
├── tenant.yaml          # the Tenant: the form's values
└── projects/
    └── churn.yaml       # an MLProject (added by Backstage's "New ML project")
```

- **Created by Backstage** from the "New tenant" form ([golden path v0 plan](../golden-path-v0-plan.md), section 6). Until Backstage exists, the platform team creates it with the same files: the same path, without the form.
- **Discovered by Argo CD:** an ApplicationSet with the SCM provider generator scans the `mlqube` organization for repositories named `tenant-*` and creates Applications for each, in a new Argo CD project **`tenants`**: only these repositories, only mgmt, only namespaces `tenant-*`, only the kinds `Tenant` and `MLProject`. There are two Applications per repository: `tenant-<id>` for `tenant.yaml`, and `tenant-<id>-projects` for `projects/`. The projects go into the namespace the `Tenant` creates, and Argo CD refuses a whole sync while a target namespace is missing, so they sync on their own and retry until it exists (implementation note, 2026-11-24).
- **Crossplane builds** everything else, from mgmt, in wl-nonprod and AWS.

### 4. Customers get read access to their repository

Changes go through Backstage forms or a pull request merged by the platform team. The `mlqube` organization is on GitHub's free plan, which has no branch protection for private repositories: write access would let a customer raise their own GPU quota with a commit that Argo CD applies unreviewed.

**Enterprise path:** GitHub Team or Enterprise, with branch protection and a `CODEOWNERS` file that makes the platform team approve every change to `tenant.yaml`; customers may then propose changes themselves.

### 5. GitHub access through GitHub Apps, not deploy keys

Deploy keys are per repository, so every new tenant would need a manual step. Instead:

| GitHub App | Permissions | Used by |
|---|---|---|
| `mlqube-argocd` | Read contents and metadata, all repositories | Argo CD: reading `xrd-tenancy` and every `tenant-*`; the SCM provider generator |
| `mlqube-backstage` | Create repositories; write contents | Backstage (section 6) |

Created by hand in GitHub's settings (it can't be scripted), once. Private keys in SSM Parameter Store, like the other hand-made secrets; Terraform gives Argo CD a credentials template for `https://github.com/mlqube`.

### 6. Data survives a destroy; everything else is rebuilt

- The **S3 bucket and ECR repositories** are kept by Crossplane (no `Delete` in their `managementPolicies`; namespaced managed resources in Crossplane v2 have no `deletionPolicy`): deleting a `Tenant` or `MLProject`, including at destroy, leaves them, and the next build takes them back over by name. Models, data and images stay between sessions (what ADR-0016 wanted from the base layer).
- Roles, policies, secrets, Pod Identity associations and Kubernetes objects are deleted with their `Tenant`/`MLProject` and recreated by the next build.
- **The destroy workflow deletes the tenants first** (the tenant Applications, then waits until every `Tenant` is gone) before it destroys the add-ons layer. Otherwise their AWS resources would be left behind.
- Offboarding a tenant leaves its bucket and repositories for the platform team to remove after the retention period.

### 7. Repository names

`xrd-tenancy` for the definitions; `tenant-<id>` per tenant; project code repositories as before ([the golden path](../golden-path.md)).

## Consequences

- No hand-made tenant: the first tenant already goes the way every later one will.
- The glue's APIs (planned for Phase 2) move into golden path v0, which grows accordingly.
- Two new kinds of repositories and a GitHub App for Argo CD before the next test; the App is a one-time manual step.
- Many repositories over time (one per tenant). Fine at this scale; the SCM generator finds them without configuration.
- A `Tenant`'s AWS names use the prefix `mlqube-tenant-` ([ADR-0004](0004-tenancy-model.md), amended), so Crossplane's role can be fenced to them.
- Tenant changes need the platform team until the organization has branch protection.
