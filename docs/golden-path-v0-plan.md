# Golden path v0 plan

> Decisions: [ADR-0016](adr/0016-golden-path-v0.md). The process from the ML engineer's side: [the golden path](golden-path.md). Follows the [Phase 1 plan](phase-1-plan.md) (done) and pulls a thin slice of Phases 1a, 3, 4 and 6 forward ([roadmap](roadmap.md)).

**Goal:** an ML engineer goes from a Backstage form to a registered model, through a feature-branch test run and an official run on `main`, on GPU, with results in MLflow; deleting the branch cleans up after it.

**Exit criteria:** the end-to-end test in section 7 passes on a fresh build.

**Approach:** write each part ahead, test in as few builds as possible (two are planned: **build A** after sections 1–5 tests the path without Backstage; **build B** after section 6 tests everything). Everything is in Terraform or `gitops`; nothing is set up by hand except what's marked.

## 0. Prerequisites

- [x] Phase 1 built and tested live (2026-11-24): clusters, Argo CD, Karpenter CPU + GPU, Dex, Kyverno, External Secrets
- [ ] Two more GPU instance types in the `gpu` NodePool (e.g. g6.4xlarge, g4dn.xlarge), within the quotas, so spot succeeds more often (Karpenter warned it wants at least 5 types for its on-demand fallback)
- [ ] Sync waves ([#13](https://github.com/mlqube/.github/issues/13)): the new add-ons add more apps that depend on CRDs

## 1. Argo Workflows and Kueue (wl-nonprod)

- [ ] Kueue add-on (ApplicationSet, wl-nonprod only): plain-pod integration on, limited to namespaces labelled `mlqube/tenant`; ResourceFlavors `cpu`/`gpu`, priorities `mlqube-main`/`mlqube-dev` (written: [Kueue](platform/gitops/kueue.md))
- [ ] Argo Workflows add-on (wl-nonprod): server with `sso` + `client` auth modes, default workflow TTL; Ingress `workflows.nonprod.mlqube.click` on the internal ALB (written: [Argo Workflows](platform/gitops/argo-workflows.md))
- [ ] Argo Workflows' workflow archive (needs PostgreSQL: with section 4)
- [ ] Dex client `argo-workflows` (Terraform `sso.tf`), secret through Secrets Manager and External Secrets into the `argo` namespace; v0: who can sign in is decided by the Identity Center assignment (admins), `sso.rbac` off; per-tenant RBAC with the tenants (written)
- [ ] `platform` AppProject: the new chart repositories, namespaces and cluster-wide kinds (written)
- [ ] **Test (build A):** a workflow with a GPU step queues in Kueue, gets a Karpenter GPU node, runs, and the node goes away; a second tenant's queue can't use the first one's quota (the Phase 1a spike)

## 2. Tenants through the glue ([ADR-0018](adr/0018-tenancy-through-crossplane-and-tenant-repos.md))

- [x] Crossplane in mgmt: engine, providers (AWS, Kubernetes), functions, their access; boundary `mlqube-boundary-tenant` ([Crossplane](platform/gitops/crossplane.md); not tested live)
- [ ] Repository `mlqube/xrd-tenancy`: XRDs and Compositions for `Tenant` and `MLProject`, examples, CI render tests
- [ ] `gitops`: ApplicationSet for `xrd-tenancy` (mgmt); ApplicationSet with the SCM provider generator for `tenant-*` repositories; Argo CD project `tenants`
- [ ] GitHub App `mlqube-argocd` (read all repositories) and Argo CD's credentials template for `https://github.com/mlqube` (Terraform, key from Parameter Store). *By hand, once: create the GitHub App.*
- [ ] Destroy workflow: delete the tenant Applications and wait until no `Tenant` is left, before the add-ons layer
- [ ] Repository `mlqube/tenant-retail-1042` with `tenant.yaml` and `projects/churn.yaml`, made by the platform team (Backstage does it from section 6)
- [ ] **Test:** the tenant and project appear in wl-nonprod (namespace, queues, ServiceAccounts, RBAC) and AWS (role, bucket, ECR repository, CI role, secret); a second build takes the bucket and ECR repository back over

## 3. CI access

- [ ] Tailscale for project CI: an ACL tag for CI jobs that may reach only the Argo Workflows server (not the cluster APIs)

## 4. MLflow v0 (mgmt)

- [ ] CloudNativePG operator add-on (mgmt), one PostgreSQL cluster for MLflow
- [ ] S3 bucket for artifacts in the base layer, with the lifecycle rule `mlflow/dev/` after 14 days
- [ ] MLflow server (Pod Identity to the bucket), oauth2-proxy in front with a Dex client, Ingress `mlflow.mlqube.click`
- [ ] Reachable from wl-nonprod workflows over VPC peering
- [ ] **Test (build A):** a run from a workflow appears in MLflow with its artifacts; sign-in works

## 5. `mlqube/ml-project-template`

- [ ] Template repository: `src/` (a small churn model on a public dataset), `pipeline.py` (Hera: prepare → train → evaluate → register), `params.yaml` (dev and main data, GPU size), `Dockerfile` (CUDA base), tests
- [ ] `feature.yaml`: on push to `feat/*`: tests → build `feat-<branch>-<sha>` → push → join Tailscale → submit to the `dev` queue → wait → comment metrics and the MLflow comparison link on the PR
- [ ] `main.yaml`: on push to `main`: the same with `main-<sha>`, the `main` queue and full data; register the model version (tags: commit, image digest, run)
- [ ] `cleanup.yaml`: on branch delete: delete `feat-<branch>-*` images; tag the branch's MLflow runs with the deletion date
- [ ] Daily job (CronWorkflow in mgmt): delete feature runs 30 days after their branch was deleted, then MLflow garbage collection
- [ ] Repository settings: `main` protected, squash-merge only, delete branch on merge
- [ ] **Test (build A):** a project repository made from the template by hand runs the whole flow (section 7 without Backstage)

## 6. Backstage (mgmt)

- [ ] `mlqube/backstage`: Backstage app, image built by CI and pushed to ECR
- [ ] Backstage add-on: PostgreSQL (CloudNativePG), Dex client (OIDC), Ingress `backstage.mlqube.click`
- [ ] GitHub App `mlqube-backstage` (create repositories, write contents, read the catalog); its private key in Secrets Manager `mlqube/platform/backstage/github-app`, delivered by External Secrets. *By hand, once: create the GitHub App.*
- [ ] Software template "New tenant": creates the repository `tenant-<id>` with `tenant.yaml` from the form; the customer gets read access ([ADR-0018](adr/0018-tenancy-through-crossplane-and-tenant-repos.md))
- [ ] Software template "New ML project": creates the project's repository from `ml-project-template` and adds `projects/<project>.yaml` to its tenant's repository
- [ ] Links from the catalog to the project's Argo Workflows, MLflow experiments and ECR repository

## 7. End-to-end test (build B)

- [ ] Create the project `churn` in Backstage; the repository exists, from the template
- [ ] Push `feat/test-change`: image `feat-test-change-<sha>` in ECR; the workflow runs on the `dev` queue on a GPU node; the run is in `…/churn/dev` with branch, commit and PR tags; the PR has CI's metrics comment
- [ ] Merge: image `main-<sha>`; the official run on the `main` queue; a new registered model version linked to commit and image
- [ ] Branch deleted: its images are gone from ECR; its runs carry the deletion tag
- [ ] A feature run can't register a model (the attempt fails)
- [ ] Destroy; record the results here and on the front page

## Later (not in v0)

- Per-tenant MLflow permissions; Capsule, default-deny NetworkPolicies and quotas in the `Tenant`'s Composition (Phase 2 onwards)
- RDS instead of in-cluster PostgreSQL; ECR in a shared-services account; reusable CI workflows; self-hosted runners in the VPC (ADR-0016 enterprise paths)
- Promotion to serving (`ModelDeployment`, Phase 5)
