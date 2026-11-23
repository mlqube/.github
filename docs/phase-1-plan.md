# Phase 1 plan: Foundation on AWS

> Part of the [roadmap](roadmap.md). Phase 1 covers the `mgmt` and `wl-nonprod` clusters only; the prod cluster comes in Phase 5.

**Goal:** Terraform for the VPCs and the `mgmt` and `wl-nonprod` EKS clusters; Karpenter with CPU and GPU NodePools; Argo CD hub; identity; observability; local kind setup.

**Exit criteria:** `git push` reconciles both clusters, and a GPU pod runs on a Karpenter-provisioned node and shows up in the dashboards.

**Suggested order:** 0 → 1 → 2 → 3, then 4–7 in parallel. Sections 8 and 1a don't need AWS and can start right away.

**Reference build:** the first build runs in a single personal AWS account in **us-west-2**, for one user, at low cost. The platform layer (VPCs, NAT, EKS clusters, nodes, load balancers) is **created with Terraform for each test session and destroyed afterwards**; only a small base layer stays (Terraform state, budget, ECR, DNS zone), costing a few dollars a month.

## 0. Inputs and decisions (blockers)

- [x] AWS account and region: one personal account, **us-west-2**; the management and workload clusters share it (reference build)
- [x] Human access to AWS: **IAM Identity Center** with an `AdministratorAccess` permission set for the `mlqube-platform-admins` group; CLI through SSO, no long-lived access keys
- [x] Cost guardrail: AWS Budget of **$50/month** with email alerts at 50%, 80% and 100% of actual spend and 100% of forecast
- [x] GPU service quotas in us-west-2: **On-Demand G and VT: 4 vCPUs** and **Spot G and VT: 8 vCPUs**, approved 2026-11-18 (no P instances)
- [x] Network design: VPCs `mlqube-mgmt` **10.10.0.0/16** and `mlqube-nonprod` **10.20.0.0/16** (10.30.0.0/16 reserved for prod), no overlap with the home network, WSL, Docker/kind or Tailscale; connected by **VPC peering** ([network layer](platform/infrastructure/network.md), private repo)
- [x] Private access without a corporate VPN: **Tailscale subnet router** in the mgmt VPC, split DNS, EKS API endpoint limited to the owner's IP ([ADR-0011](adr/0011-private-access-reference-build.md))
- [x] DNS domain: **`mlqube.click`**, registered in Route 53; split-horizon DNS (public zone only for certificate validation, private zone attached to the VPCs); ACM certificate for `*.mlqube.click` and `*.nonprod.mlqube.click` **issued** (base layer, 2026-11-20)
- [x] Identity provider: **AWS IAM Identity Center** as the identity hub ([ADR-0015](adr/0015-iam-identity-center-identity-hub.md), amends [ADR-0009](adr/0009-identity-provider.md)); tools through SAML (Dex), `kubectl` through access entries
- [ ] ADR-0012: observability, self-hosted or Amazon Managed Prometheus/Grafana

## 1. Repositories and CI

- [x] Create `mlqube/infrastructure` (Terraform) and `mlqube/gitops` (Argo CD apps and add-on configuration); both private
- [ ] Branch protection and CODEOWNERS (branch protection on private repositories needs a paid GitHub plan)
- [x] CI without static keys: GitHub Actions assumes AWS roles through OIDC (`plan` and `apply` roles, [bootstrap](platform/infrastructure/bootstrap.md)); pre-commit (`terraform fmt`, `validate`, secrets, YAML) and `plan` on pull requests; `apply`/`destroy` by hand through the `platform` workflow (the platform is built per session, not on merge)
- [ ] tflint and checkov in the checks
- [x] Terraform state backend: S3 bucket, encrypted, S3-native locking

## 2. AWS foundation (Terraform)

- [x] VPCs for shared services (`mgmt`) and non-prod: private subnets for nodes, NAT, S3 gateway endpoint; interface endpoints (ECR, STS, Secrets Manager) available but off to save cost ([network layer](platform/infrastructure/network.md))
- [x] Connectivity between the VPCs (peering) and the private hosted zone `mlqube.click`; the Tailscale router stands in for the corporate network (no Resolver endpoints in the reference build)
- [x] EKS clusters `mgmt` and `wl-nonprod`: pinned versions (1.36), a small managed node group for system pods, EKS add-ons (VPC CNI, CoreDNS, kube-proxy, EBS CSI driver, Pod Identity agent)
- [x] Tagging scheme (`mlqube/*` default tags) and AWS Budgets alerts
- [ ] KMS encryption for Kubernetes secrets: left out of the reference build (a customer-managed key costs about $1 per create/destroy cycle); EKS's default encryption applies
- [x] IAM roles through EKS Pod Identity for Karpenter, the AWS Load Balancer Controller and ExternalDNS, one set per cluster ([addons-mgmt](platform/infrastructure/addons-mgmt.md))
- [x] Pod Identity role for External Secrets (read-only, `mlqube/platform/*`)

## 3. GitOps bootstrap

- [x] Terraform installs Argo CD in `mgmt` from CI through Tailscale ([ADR-0014](adr/0014-ci-access-to-private-clusters.md)), at `https://argocd.mlqube.click` (internal ALB)
- [ ] After that, Argo CD manages itself (today Terraform also upgrades it)
- [x] App of apps with one ApplicationSet per add-on; `wl-nonprod` registered as a spoke (hub and spoke, [clusters/mgmt](platform/gitops/clusters-mgmt.md))
- [x] Argo CD projects: `bootstrap` (root app), `platform` (add-ons), `default` locked down; verified 2026-11-23 (an Application in `default` is refused)
- [ ] Sync waves for ordering ([#13](https://github.com/mlqube/.github/issues/13))
- [x] Pinned chart versions
- [ ] Changes roll out to non-prod first

## 4. Cluster add-ons (through Argo CD, both clusters)

- [x] AWS VPC CNI managed add-on with prefix delegation and network policy enforcement on ([ADR-0013](adr/0013-cni-and-network-policy.md))
- [ ] A default-deny policy verified between two test namespaces
- [x] Karpenter with a CPU NodePool per cluster (spot first)
- [x] Karpenter scale test on both clusters, 2026-11-23: a 3-CPU pod got a spot node in about 40 s (mgmt `c8id.xlarge`, wl-nonprod `c8i-flex.xlarge`), removed about 2 min after the pod was deleted
- [ ] GPU (spot) NodePool in `wl-nonprod`, tainted so only GPU work lands on it (written, g6/g5 within the quotas; to verify at the next build)
- [ ] NVIDIA device plugin (written; to verify at the next build)
- [ ] DCGM exporter for GPU metrics (with observability)
- [x] AWS Load Balancer Controller, ExternalDNS
- [x] cert-manager (in-cluster certificates only), internal CA `mlqube-internal-ca` per cluster; verified 2026-11-23 (test certificate issued)
- [x] External Secrets Operator connected to AWS Secrets Manager; verified 2026-11-23 (test secret synced; another path denied by IAM; tenant-labelled namespace denied by the store)
- [ ] Kyverno with the Pod Security baseline policies in Audit mode (written, mlqube/gitops#11; to verify at the next build); Enforce once the reports are clean
- [ ] Required-labels policy (with the tenant label convention, Phase 2)
- [ ] metrics-server (written; to verify at the next build)

## 5. Identity ([ADR-0009](adr/0009-identity-provider.md))

Mechanism changed by [ADR-0015](adr/0015-iam-identity-center-identity-hub.md): IAM Identity Center, SAML through Dex, access entries instead of an EKS OIDC provider.

- [x] Argo CD sign-in through Identity Center (SAML app, Dex); `mlqube-platform-admins` → `role:admin`, everyone else no access; local admin off (`admin.enabled: false` verified 2026-11-23)
- [x] Group claim format checked: Identity Center sends group **IDs**; the ID is kept in SSM Parameter Store
- [ ] Grafana sign-in the same way (with observability)
- [x] `kubectl` through Identity Center roles and EKS access entries; CI and Argo CD through their own access entries

## 6. Ingress and private access ([ADR-0010](adr/0010-ingress.md), [ADR-0011](adr/0011-private-access-reference-build.md))

- [x] One shared internal ALB per cluster (IngressGroup `mlqube-mgmt`), ACM certificate, HTTPS only, inbound limited to the VPC ranges
- [x] Tailnet set up: router tag, auto-approved routes, split DNS for `mlqube.click`; CI joins as `tag:ci` through workload identity
- [x] Tailscale subnet router (small EC2 instance in a private mgmt subnet) created and destroyed by Terraform; auth key in SSM Parameter Store
- [x] EKS API private by default, reached through the tailnet; a public endpoint limited to given IPs is an optional Terraform variable
- [x] Argo CD reachable by name from the laptop through the tailnet
- [ ] Grafana the same way (with observability)

## 7. Observability (per ADR-0012)

- [ ] In `mgmt`: Prometheus (or Amazon Managed Prometheus), Grafana, Loki, OpenTelemetry Collector
- [ ] In `wl-nonprod`: collectors that send metrics and logs to `mgmt`
- [ ] Dashboards for clusters, Karpenter and GPUs (DCGM); a few basic alerts
- [ ] `mlqube/tenant` label convention in place from day one, so OpenCost works later

## 8. Local development

- [ ] kind setup with Argo CD pointed at the same GitOps repo (local overlay) and Dex with test users and groups
- [ ] One-command bootstrap (e.g. `make up`) and a short README

## 9. Operations basics

- [ ] Version pinning and an upgrade policy (non-prod first)
- [ ] Runbooks: bootstrapping a cluster, break-glass access, rotating secrets
- [ ] Teardown tested, so non-prod can be rebuilt from code

## 1a. Spike: Argo Workflows + Kueue + Karpenter (in parallel)

- [ ] Install Argo Workflows and Kueue, first in local kind, then in `wl-nonprod`
- [ ] Two test tenants, each with a ClusterQueue, a LocalQueue and a GPU quota; Kueue's plain-pod integration enabled for workflow step pods
- [ ] A workflow with GPU steps proves: queueing per tenant, quota enforcement, borrowing and reclaiming idle quota, Karpenter scaling GPU nodes up and back to zero, all-or-nothing admission for multi-pod steps
- [ ] Record the result as an ADR (or update [ADR-0005](adr/0005-argo-workflows-with-hera-for-ml-jobs.md)); if it fails, use the fallback (Argo parallelism limits plus ResourceQuotas)

## Not in Phase 1

Crossplane and the `Tenant` API, Capsule, gVisor and per-tenant isolation (Phase 2); MLflow and RDS (Phase 4); the prod cluster and KServe (Phase 5); Backstage (Phase 6).
