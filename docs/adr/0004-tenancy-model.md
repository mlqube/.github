# ADR-0004: Tenancy model: tiered isolation

- **Status:** Proposed
- **Date:** 2026-11-17

## Context

MlQube is a multi-tenant product. Tenants run untrusted code on shared infrastructure, store proprietary data and models, and expect their costs to be attributed correctly. Different customers will accept different trade-offs between cost and isolation.

## Options considered

1. **Namespace per tenant on shared clusters.** Cheapest and densest; isolation relies on policy, network rules and quotas.
2. **Virtual cluster per tenant (vCluster).** Each tenant gets its own Kubernetes API and can install their own resources; workloads still run on shared nodes.
3. **Dedicated cluster per tenant.** Strongest isolation, highest cost.
4. **A tiered combination of the above.**

## Decision

Offer **tiers**, with the shared tier as the default:

| Tier | Isolation mechanism |
|---|---|
| **Standard** | A Capsule tenant (one or more namespaces) on the shared workload clusters |
| **Premium** | A vCluster per tenant, optionally with dedicated Karpenter NodePools |
| **Enterprise** | A dedicated workload cluster per tenant ([ADR-0003](0003-cluster-topology.md)) |

Baseline controls for every tenant in the shared tier:

- **Compute:** ResourceQuota and LimitRange, plus a Kueue ClusterQueue per tenant for GPU fair-share.
- **Network:** default-deny NetworkPolicies, with egress only to allowed destinations.
- **Policy:** Pod Security Standards (`restricted`) and Kyverno policies (approved image registries, no privileged pods, required labels).
- **Identity:** OIDC groups mapped to tenant RBAC; per-tenant IAM roles through EKS Pod Identity.
- **Data:** an S3 bucket per tenant, accessible only through that tenant's IAM role; a shared MLflow with per-tenant permissions and S3 prefixes ([ADR-0007](0007-mlflow-multi-tenancy.md)).
- **Runtime:** sandboxing and GPU node isolation per [ADR-0008](0008-workload-sandboxing.md).
- **Cost:** tenant labels on every resource, used by OpenCost for chargeback.

## Consequences

- One shared operating model serves most tenants cheaply. Higher tiers are upsells that reuse the same building blocks.
- Shared-tier isolation depends on configuring policy correctly, so it needs a threat model and regular testing.
- The platform's `Tenant` API ([ADR-0006](0006-platform-apis-with-crossplane.md)) has to express the tier and provision the right resources for it.
