# ADR-0004: Tenancy model: business units as tenants, single tier

- **Status:** Accepted
- **Date:** 2026-11-17

## Context

MlQube serves **one organization**. Its **business units (BUs)** are the tenants. BUs share the platform but must not see each other's code, data, experiments, models or endpoints, and each BU's costs must be reported separately (showback/chargeback).

Because all tenants belong to the same organization, we don't need the separate cost/isolation levels a commercial multi-customer product would sell (virtual clusters or dedicated clusters per customer).

## Options considered

1. **A single tier: every BU is a tenant on the shared clusters.** One operating model; isolation through namespaces, policy, quotas and IAM.
2. **Several isolation tiers (shared namespaces, vCluster, dedicated cluster).** Flexible, but adds complexity that a single organization doesn't need. *Rejected.*

## Decision

**Single tier.** Every business unit is a tenant on the shared workload clusters ([ADR-0003](0003-cluster-topology.md)), isolated with a Capsule tenant.

### Tenant ID

Each tenant is identified by:

```
<businessunit_name>-<businessunitid>
```

Examples: `retail-1042`, `risk-analytics-2001`

| Rule | Why |
|---|---|
| `<businessunit_name>`: lowercase letters, digits and hyphens; must start with a letter | Valid as a Kubernetes name (DNS-1123), S3 name and IAM name |
| `<businessunitid>`: **numeric only** (digits), and always the segment after the **last** hyphen | The BU name may contain hyphens and the ID can still be parsed without ambiguity |
| Validation pattern: `^[a-z][a-z0-9-]*-[0-9]+$` | Enforced by the `Tenant` API and Kyverno |
| **30 characters or fewer** | Leaves room for prefixes and suffixes within the 63-character limits of Kubernetes names and S3 buckets and the 64-character limit of IAM role names |
| **Immutable once created** | Renaming a BU must not break namespaces, buckets, IAM roles or MLflow names. The display name is stored separately as an annotation |

### Where the tenant ID is used

| Resource | Naming pattern | Example |
|---|---|---|
| Capsule tenant | `<tenant>` | `retail-1042` |
| Namespaces | `<tenant>` and `<tenant>-<project>` | `retail-1042-churn` |
| Label on every resource | `mlqube/tenant: <tenant>` | `mlqube/tenant: retail-1042` |
| Kueue queue | `<tenant>` | `retail-1042` |
| Identity provider groups | `mlqube-<tenant>-admins` / `-developers` / `-viewers` | `mlqube-retail-1042-developers` |
| IAM role (Pod Identity) | `mlqube-<tenant>-<env>` | `mlqube-retail-1042-nonprod` |
| S3 data bucket | `<org-prefix>-<tenant>-<env>` | `acme-mlqube-retail-1042-nonprod` |
| MLflow artifact prefix | `s3://<mlflow-bucket>/tenants/<tenant>/` | `.../tenants/retail-1042/` |
| MLflow experiments / models | `/<tenant>/<project>/<name>` and `<tenant>.<project>.<model>` | `/retail-1042/churn/baseline` |
| Cost reports (OpenCost) | Grouped by the `mlqube/tenant` label | Spend per BU |

### Isolation controls for every tenant

- **Compute:** ResourceQuota and LimitRange, plus a Kueue ClusterQueue per tenant for fair sharing of GPUs (BUs can borrow idle capacity from each other).
- **Network:** default-deny NetworkPolicies, with egress only to allowed destinations.
- **Policy:** Pod Security Standards (`restricted`) and Kyverno policies (approved registries, no privileged pods, a required `mlqube/tenant` label, names must use the tenant's prefix).
- **Identity:** SSO through IAM Identity Center ([ADR-0015](0015-iam-identity-center-identity-hub.md)); Identity Center groups per tenant mapped to RBAC in the tenant's namespaces.
- **Data:** an S3 bucket per tenant and per environment, accessible only through the tenant's IAM role; shared MLflow with per-tenant permissions and S3 prefixes ([ADR-0007](0007-mlflow-multi-tenancy.md)).
- **Runtime:** sandboxing and GPU node isolation per [ADR-0008](0008-workload-sandboxing.md).
- **Cost:** showback/chargeback per BU, based on the tenant label.

## Consequences

- One simple operating model, with no vCluster or per-tenant clusters to run.
- The same tenant ID appears in every system, which makes ownership, access reviews and cost reports straightforward.
- Isolation depends on configuring namespaces, policies and IAM correctly, so it needs automated tests (e.g. "tenant A cannot read tenant B's bucket").
- The `Tenant` API ([ADR-0006](0006-platform-apis-with-crossplane.md)) validates the ID format and creates all of the resources above.
- If a BU later needs stronger isolation (e.g. for regulatory reasons), dedicated node pools or a separate workload cluster can be added as an exception without changing the tenant model.
