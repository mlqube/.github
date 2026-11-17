# ADR-0007: One shared MLflow for all tenants (PostgreSQL + S3)

- **Status:** Accepted
- **Date:** 2026-11-17

## Context

MLflow provides experiment tracking and the model registry. MLflow stores two kinds of data:

- **Backend store:** experiments, runs, parameters, metrics, tags and registered model versions
- **Artifact store:** model files, checkpoints, plots and other files

We want **one MLflow service shared by all tenants**, to keep operations simple and costs low. MLflow has no built-in concept of a tenant, so MlQube must make sure tenants can't see or change each other's experiments, models or artifacts.

## Options considered

1. **One MLflow instance per tenant.** Strong isolation by design, but many instances to run and upgrade. *Rejected: operational overhead.*
2. **One shared MLflow; isolation through permissions, naming and S3 access control.** One service to operate; isolation is enforced by MlQube's glue layer.

## Decision

Run **one shared, highly available MLflow tracking server** for all tenants:

| Concern | Decision |
|---|---|
| **Backend store** | **Amazon RDS for PostgreSQL** (Multi-AZ), one shared database |
| **Artifact store** | **Amazon S3**, one platform bucket with a **prefix per tenant**: `s3://<mlflow-bucket>/tenants/<tenant>/...` |
| **Where it runs** | In the management cluster as a shared platform service, reachable privately from the workload clusters |
| **Authentication** | SSO with OIDC (the platform identity provider), through an MLflow OIDC auth plugin or an authenticating proxy |
| **Authorization** | MLflow permissions on experiments and registered models, granted per tenant group by the `Tenant` / `MLProject` APIs ([ADR-0006](0006-platform-apis-with-crossplane.md)) |
| **Naming conventions** | Experiments: `/<tenant>/<project>/<name>`; registered models: `<tenant>.<project>.<model>`. Kyverno and the glue layer reject names outside the tenant's prefix |
| **Artifact access** | Workflow pods read and write artifacts directly in S3 using the **tenant's IAM role** (EKS Pod Identity), limited to that tenant's prefix by IAM policy |
| **Serving** | KServe in the prod cluster loads model artifacts from the tenant's S3 prefix using the tenant's IAM role |

Isolation is enforced at three levels:

1. **Identity:** every request is authenticated through SSO and mapped to the tenant's groups.
2. **Metadata:** MLflow permissions restrict experiments and models to the owning tenant's groups.
3. **Data:** IAM policies restrict each tenant's S3 access to its own prefix, even if MLflow permissions are misconfigured.

## Consequences

- One MLflow to operate, upgrade and back up; the cost doesn't grow with each tenant.
- All tenants share one PostgreSQL database, so a database outage affects everyone. Multi-AZ RDS, backups and connection pooling (e.g. PgBouncer) are required.
- Isolation of metadata depends on correctly configured MLflow permissions. The glue layer must grant them automatically and test them, and naming rules must be enforced.
- MLflow's built-in auth is basic. We need an OIDC-capable auth plugin or proxy and must check that it supports group-based permissions.
- **To check:** if the MLflow version we adopt offers built-in workspace/namespace isolation, we should use it instead of relying on naming conventions.
- If a tenant later needs strong isolation (enterprise tier), a dedicated MLflow can still be deployed for that tenant as an exception.
