# ADR-0007: One MLflow instance per tenant

- **Status:** Proposed
- **Date:** 2026-11-17

## Context

MLflow provides experiment tracking and the model registry. Its built-in authentication and authorization are basic and not designed for strict multi-tenant isolation, yet tenants' experiments, metrics and models are confidential.

## Options considered

1. **A shared MLflow with built-in authentication.** Cheapest, but its permission model is too coarse for multi-tenant use.
2. **A shared MLflow behind a custom authorization proxy.** Efficient, but we would have to build and maintain the proxy, and data still sits in a shared database.
3. **One MLflow instance per tenant.** Simple, strong isolation, but more instances to run.

## Decision

Run **one MLflow tracking server per tenant**, provisioned by the `Tenant` API ([ADR-0006](0006-platform-apis-with-crossplane.md)):

- Deployed in the tenant's namespace on the non-prod workload cluster
- Metadata stored in **a database per tenant** on a shared Amazon RDS for PostgreSQL instance (or Aurora Serverless)
- Artifacts and models stored in the **tenant's S3 bucket**, accessed through EKS Pod Identity
- Access through SSO (an OIDC proxy), limited to the tenant's members
- Workflows ([ADR-0005](0005-argo-workflows-with-hera-for-ml-jobs.md)) and endpoints use the tenant's MLflow automatically

## Consequences

- Tenant data is isolated by design, with no custom authorization code.
- Each tenant adds a small fixed cost (a pod and a database); this is acceptable at early scale.
- Upgrades must roll out across many instances, which GitOps handles.
- We will revisit a shared, proxy-protected MLflow if the number of tenants makes the per-instance overhead significant.
