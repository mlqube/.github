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
- [x] Identity provider: **Microsoft Entra ID** ([ADR-0009](adr/0009-identity-provider.md)); OIDC apps and `mlqube-*` groups still to be created
- [ ] ADR-0012: observability, self-hosted or Amazon Managed Prometheus/Grafana

## 1. Repositories and CI

- [ ] Create `mlqube/infrastructure` (Terraform) and `mlqube/gitops` (Argo CD apps and add-on configuration)
- [ ] Branch protection and CODEOWNERS
- [ ] CI without static keys: GitHub Actions assumes an AWS role through OIDC; `terraform fmt`, `validate`, tflint and checkov, and `plan` on pull requests, `apply` on merge
- [ ] Terraform state backend: S3 bucket with locking, encrypted

## 2. AWS foundation (Terraform)

- [ ] VPCs for shared services (`mgmt`) and non-prod: private subnets only, NAT, VPC endpoints (S3, ECR, STS, Secrets Manager)
- [ ] Connectivity between the VPCs and to the corporate network; Route 53 private hosted zone and Resolver endpoints for corporate DNS
- [ ] EKS clusters `mgmt` and `wl-nonprod`: pinned versions, a small managed node group for system pods, EKS add-ons (VPC CNI, CoreDNS, kube-proxy, EBS CSI driver, Pod Identity agent)
- [ ] KMS encryption for Kubernetes secrets; tagging scheme (`mlqube/*` and cost allocation tags); AWS Budgets alerts
- [ ] IAM roles through EKS Pod Identity for the platform controllers (Karpenter, AWS Load Balancer Controller, ExternalDNS, External Secrets)

## 3. GitOps bootstrap

- [ ] Terraform installs Argo CD in `mgmt` once, from CI through Tailscale ([ADR-0014](adr/0014-ci-access-to-private-clusters.md)); after that, Argo CD manages itself
- [ ] App-of-apps / ApplicationSets layout; register `wl-nonprod` as a target cluster; sync waves for ordering
- [ ] Pinned chart versions; changes roll out to non-prod first

## 4. Cluster add-ons (through Argo CD, both clusters)

- [ ] AWS VPC CNI managed add-on with prefix delegation and network policy enforcement on ([ADR-0013](adr/0013-cni-and-network-policy.md)); a default-deny policy verified between two test namespaces
- [ ] Karpenter with CPU and GPU (spot) NodePools; GPU nodes tainted so only GPU work lands on them
- [ ] NVIDIA GPU Operator (or device plugin) and the DCGM exporter for GPU metrics
- [ ] AWS Load Balancer Controller, ExternalDNS, cert-manager (in-cluster certificates only)
- [ ] External Secrets Operator connected to AWS Secrets Manager
- [ ] Kyverno baseline policies (no privileged pods, required labels); metrics-server

## 5. Identity ([ADR-0009](adr/0009-identity-provider.md))

- [ ] OIDC applications for Argo CD and Grafana; tokens carry only the `mlqube-*` groups
- [ ] Check the group claim format (names vs object IDs, overage claim) and record the result
- [ ] EKS OIDC identity provider association on both clusters; RBAC for `mlqube-platform-admins`
- [ ] IAM access entries only for automation and break-glass access, with a documented procedure

## 6. Ingress and private access ([ADR-0010](adr/0010-ingress.md), [ADR-0011](adr/0011-private-access-reference-build.md))

- [ ] One shared internal ALB per cluster (IngressGroup), ACM certificate, HTTPS only, security groups limited to the VPC and tailnet ranges
- [ ] Tailnet set up: tag `tag:mlqube-router`, auto-approved routes, split DNS for the MlQube domain, access rules for the owner only
- [ ] Tailscale subnet router (small EC2 instance in a private mgmt subnet) created and destroyed by Terraform; auth key in Secrets Manager
- [ ] EKS public endpoint limited to the owner's IP (Terraform variable)
- [ ] Argo CD and Grafana reachable by name from the laptop through the tailnet

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
