# Phase 1 plan: Foundation on AWS

> Part of the [roadmap](roadmap.md). Phase 1 covers the `mgmt` and `wl-nonprod` clusters only; the prod cluster comes in Phase 5.

**Goal:** Terraform for the VPCs and the `mgmt` and `wl-nonprod` EKS clusters; Karpenter with CPU and GPU NodePools; Argo CD hub; identity; observability; local kind setup.

**Exit criteria:** `git push` reconciles both clusters, and a GPU pod runs on a Karpenter-provisioned node and shows up in the dashboards.

**Suggested order:** 0 → 1 → 2 → 3, then 4–7 in parallel. Sections 8 and 1a don't need AWS and can start right away.

## 0. Inputs and decisions (blockers)

- [ ] AWS account(s) and region; whether the management and workload clusters share one account
- [ ] GPU service quotas (on-demand and spot G/P instance vCPUs) in that region
- [ ] Network design: CIDR ranges, connectivity between the VPCs (Transit Gateway or peering) and to the corporate network / VPN
- [ ] DNS domain, e.g. `*.nonprod.mlqube.<corp-domain>`
- [ ] IdP team agrees to register OIDC apps and create the `mlqube-*` groups ([ADR-0009](adr/0009-identity-provider.md))
- [ ] ADR-0011: observability, self-hosted or Amazon Managed Prometheus/Grafana

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

- [ ] Terraform installs Argo CD in `mgmt` once; after that, Argo CD manages itself
- [ ] App-of-apps / ApplicationSets layout; register `wl-nonprod` as a target cluster; sync waves for ordering
- [ ] Pinned chart versions; changes roll out to non-prod first

## 4. Cluster add-ons (through Argo CD, both clusters)

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

## 6. Ingress ([ADR-0010](adr/0010-ingress.md))

- [ ] One shared internal ALB per cluster (IngressGroup), ACM certificate, HTTPS only, security groups limited to corporate / VPN ranges
- [ ] Argo CD and Grafana reachable by name from the corporate network

## 7. Observability (per ADR-0011)

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
