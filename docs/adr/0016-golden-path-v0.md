# ADR-0016: Golden path v0, from a feature branch to a registered model

- **Status:** Accepted
- **Date:** 2026-11-24
- **Deciders:** platform team

## Context

Phase 1 is built and tested live: two EKS clusters, the Argo CD hub, Karpenter with CPU and GPU nodes, Dex for single sign-on, Kyverno, External Secrets, cert-manager ([Phase 1 plan](../phase-1-plan.md)). Nothing yet lets an **ML engineer** use it: there is no way to go from Python code to a training run, see the results, and produce a model.

The [roadmap](../roadmap.md) spreads that over several phases (1a spike, 3 ML jobs, 4 tracking, 6 portal). Building them one after another would take a long time before anyone could try the whole path. This ADR instead defines a **thin slice through all of them, "golden path v0"**: the minimum of each, wired end to end, for one hand-made tenant. Each piece is deepened later in its own phase.

The developer's view of the process is on [the golden path](../golden-path.md); the build steps in the [golden path v0 plan](../golden-path-v0-plan.md).

## Decision

### 1. What "done" means for v0

An ML engineer creates a project in Backstage, pushes code to a feature branch, CI builds an image, the training workflow runs on a GPU, and the results are visible in MLflow; merging to `main` makes the official run and a registered model version; deleting the branch removes its images. One tenant (`retail-1042`), one project, made by hand where the glue would later do it.

### 2. Trunk-based development in every ML project

| Branch | Push does | Image | Queue, data | MLflow | Registers a model |
|---|---|---|---|---|---|
| `feat/*` (short-lived) | The engineer's own test run | `feat-<branch>-<sha>`, temporary | `dev` (low priority, smaller GPU budget), sample data | `/<tenant>/<project>/dev`, tagged with branch, commit, PR | **Never** |
| `main` (protected, squash-merge by reviewed PR) | The official run | `main-<sha>`, immutable, kept | `main` (normal priority), full data | `/<tenant>/<project>/main` | **Yes**, linked to commit, image digest, run |

**Feature-branch runs are disposable; main runs are the record.** When a branch is deleted:

| What | Retention | Mechanism |
|---|---|---|
| Feature images | Deleted at once | Cleanup workflow on GitHub's `delete` event; ECR lifecycle rule (`feat-*` after 14 days) as a safety net |
| Feature run metadata (parameters, metrics, tags) | 30 days after the branch is deleted | Cleanup tags the runs with the date; a daily job deletes them, then MLflow's garbage collection |
| Feature artifacts (`mlflow/dev/` prefix) | 14 days | S3 lifecycle rule |
| Argo workflow records | A few days | Workflow TTL; summary in the workflow archive |
| Main images, runs, registered models | Kept, per the organization's retention policy | — |

The periods are settings. Large enterprises split run information the same way: metadata is small and useful for comparison and audit, so it's kept for a while (regulated industries keep audit metadata 90 days or more, even after artifacts are gone); artifacts and images are big, so they go soon; only `main` reaches the registry.

### 3. New repositories

| Repository | What | Visibility |
|---|---|---|
| `mlqube/ml-project-template` | GitHub template repository: `src/`, `pipeline.py` (Hera), `params.yaml`, `Dockerfile`, tests, and three CI workflows (`feature.yaml`, `main.yaml`, `cleanup.yaml`) | Private |
| `mlqube/backstage` | Our Backstage app and its image: software templates, plugins (GitHub, Argo Workflows, MLflow links) | Private |

The CI workflows start inside the template. **Enterprise path:** move them to central **reusable workflows**, so a fix reaches every project without editing each repository.

### 4. Single sign-on: Dex for every new tool

Argo Workflows (its built-in SSO), Backstage (OIDC) and MLflow (through oauth2-proxy) are OIDC clients of the standalone Dex, exactly like Argo CD ([ADR-0015](0015-iam-identity-center-identity-hub.md), [Dex](../platform/gitops/dex.md)). Terraform adds one client per tool to Dex's configuration and writes each client secret into the tool's namespace.

### 5. Databases: PostgreSQL in the cluster for v0

Backstage and MLflow each need PostgreSQL. **In v0 it runs in the management cluster** (one small instance per tool, run by the CloudNativePG operator). Its data is lost on every destroy, which is acceptable for the reference build: Backstage rebuilds its catalog from Git, and MLflow's v0 runs are test data.

> **In a real enterprise deployment, use Amazon RDS for PostgreSQL** (Multi-AZ, automated backups, point-in-time restore, encryption with a customer-managed key, upgrades handled by AWS), as [ADR-0007](0007-mlflow-multi-tenancy.md) already states for MLflow. In-cluster PostgreSQL is chosen here only because the reference build is created and destroyed for each session, and RDS takes long to create and delete.

### 6. Images: ECR in the same account and region, in the base layer

- One repository per project, `mlqube/<tenant>/<project>`, in **us-west-2**, created in the **base layer**, which survives a destroy (images stay between sessions; storage costs cents).
- **Push:** a GitHub OIDC role per project, allowed to push only to its repository. No keys.
- **Pull:** the EKS nodes' existing read-only ECR permission. Over the NAT gateway today; VPC endpoints for ECR and S3 later (cheaper for large images).
- Tags immutable (every tag carries a commit SHA), scan on push, the lifecycle rules above.

**Enterprise path:** ECR in a separate **shared-services account**, pulled by the workload accounts through repository policies; replication to every region with clusters; image signing checked at admission by Kyverno; deployment by digest of the image that trained on `main`.

### 7. How CI submits the workflow: over Tailscale

GitHub-hosted runners can't reach the private clusters. The CI job joins the tailnet for its duration, as Terraform already does ([ADR-0014](0014-ci-access-to-private-clusters.md)), and submits the workflow to the Argo Workflows server at its private URL.

- **Authentication:** Argo Workflows runs with two modes: `sso` for people (through Dex), `client` for CI. CI uses the token of a ServiceAccount in the project's namespace that may only create and watch workflows there. The token is in AWS Secrets Manager under `mlqube/tenants/<tenant>/<project>/argo-ci`; CI reads it with its OIDC role. No long-lived secret in GitHub besides the existing Tailscale OAuth client.
- **Alternatives recorded:** **self-hosted runners inside the VPC** (GitHub's Actions Runner Controller) is the usual enterprise path: no tunnel, at the cost of one more component to run and harden. **A queue in between** (CI sends a message to SQS; Argo Events in the cluster submits the workflow and reports back to the PR) suits organizations that don't want CI on their private network at all. **Submitting through GitOps** is rejected: training runs are one-off jobs, not desired state.

### 8. Queues and GPUs: Kueue

Per tenant, a Kueue **ClusterQueue** with the tenant's GPU quota; per project, two **LocalQueues**: `dev` (a low WorkloadPriorityClass) and `main`. Workflow step pods join a queue through Kueue's plain-pod integration. The GPU nodes come from the existing Karpenter `gpu` NodePool. Whether Kueue and Argo Workflow pods work well together is the Phase 1a question, answered in the first build of v0; the fallback is Argo's parallelism limits plus ResourceQuotas ([ADR-0005](0005-argo-workflows-with-hera-for-ml-jobs.md)).

### 9. MLflow v0

One MLflow server in the management cluster ([ADR-0007](0007-mlflow-multi-tenancy.md)): PostgreSQL in the cluster (decision 5), artifacts in an S3 bucket created in the base layer (with the `mlflow/dev/` lifecycle rule), reachable at `https://mlflow.mlqube.click` over Tailscale, sign-in through Dex. Workflows in `wl-nonprod` reach it over VPC peering. **Per-tenant permissions are not in v0**; they come in Phase 4 with the glue ([the MlQube glue](../glue.md), part C).

### 10. The tenant and project are made by hand

`retail-1042` and its project `churn` are plain YAML in the `gitops` repository (namespace, queues, ServiceAccount, RBAC), plus Terraform for the ECR repository and roles. Writing them by hand shows exactly what the glue's `Tenant` and `MLProject` must generate in Phase 2.

## Consequences

- An ML engineer can try the whole path early, and every later phase deepens a piece that already works end to end.
- New components to run and upgrade: Argo Workflows, Kueue, MLflow, Backstage, CloudNativePG, oauth2-proxy.
- v0's in-cluster databases lose their data on every destroy. Acceptable for the reference build; production uses RDS.
- The hand-made tenant and project are temporary and will be replaced by the glue's APIs.
- The retention rules must be tested, not just written: the end-to-end test deletes a branch and checks what's gone.
