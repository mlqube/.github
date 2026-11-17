# ADR-0006: Build the platform APIs with Crossplane

- **Status:** Accepted
- **Date:** 2026-11-17

## Context

MlQube exposes a small set of high-level resources (`Tenant`, `MLProject`, `Workspace`, `ModelDeployment`). Each one expands into many lower-level objects: Kubernetes resources (namespaces, quotas, policies, Argo and KServe objects) **and** AWS resources (S3 buckets, IAM roles, RDS databases, ECR repositories). We need a declarative, GitOps-friendly way to define and reconcile these resources.

## Options considered

1. **Crossplane (XRDs and Compositions).** Mature; manages both cloud and Kubernetes resources from one API; has an AWS provider.
2. **KRO (Kube Resource Orchestrator).** Lighter and Kubernetes-native, but newer and relies on other tools (e.g. AWS Controllers for Kubernetes) for cloud resources.
3. **Custom operators.** Full flexibility, but the most code to build and maintain.
4. **Terraform runs per tenant.** Familiar, but outside the Kubernetes reconciliation loop and harder to expose as self-service.

## Decision

Use **Crossplane** in the management cluster, with the AWS provider and the Kubernetes/Helm providers. MlQube defines composite resource types such as:

| Resource | Creates |
|---|---|
| `Tenant` | Capsule tenant (ID `<businessunit_name>-<businessunitid>`), quotas, Kueue queue, network policies, S3 bucket, IAM role (Pod Identity), MLflow permissions and S3 artifact prefix |
| `MLProject` | Project namespace, ECR repository, CI configuration, MLflow experiment, starter WorkflowTemplates |
| `Workspace` | Notebook/IDE instance with storage and GPU limits |
| `ModelDeployment` | KServe InferenceService, route, autoscaling, canary policy, dashboards |

Backstage templates create these resources by committing them to Git, and Argo CD applies them.

## Consequences

- One declarative API covers both AWS and Kubernetes resources, and it fits GitOps naturally.
- The team has to learn Crossplane Compositions and composition functions.
- Provider upgrades and drift between AWS and Kubernetes state need monitoring.
- If Crossplane proves too heavy, KRO combined with AWS Controllers for Kubernetes remains a fallback.
