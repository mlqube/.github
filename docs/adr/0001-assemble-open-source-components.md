# ADR-0001: Assemble open-source components instead of building a custom control plane

- **Status:** Accepted
- **Date:** 2026-11-17

## Context

MlQube must provide workspaces, training, a model registry, serving, CI/CD and a developer portal, all multi-tenant, on managed Kubernetes. Mature open-source projects already exist for each capability (Kubeflow components, KServe, MLflow, Argo, Backstage, Kueue, Crossplane). Building our own equivalents would take years and duplicate community work.

## Options considered

1. **Custom control plane.** Our own CRDs, operators and API for every capability. Full control, but a huge build and maintenance cost, and it reinvents mature tools.
2. **Assemble OSS with a thin glue layer.** Integrate existing projects and build only tenancy, high-level platform APIs, portal templates and metering. Faster to deliver and familiar to users; the cost is integration work and keeping many components upgraded.
3. **Adopt a full distribution (e.g. Kubeflow as a whole).** Quick to start, but heavy to run, and its multi-user model is hard to fit into a multi-tenant platform.

## Decision

Option 2: **assemble OSS components with a thin MlQube glue layer** ([the MlQube glue](../glue.md)). Components are adopted individually (e.g. KServe, Kubeflow Trainer, Notebooks), not as one monolithic distribution.

## Consequences

- Faster time to value; users work with tools they already know.
- MlQube's own code stays small: platform APIs, Backstage templates and plugins, policies and metering.
- We have to manage version compatibility and upgrades across many projects, so GitOps, pinned versions and a staging cluster are required.
- Gaps in upstream multi-tenancy (e.g. MLflow authorization) have to be closed in the glue layer.
