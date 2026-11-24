# Roadmap

> Phases are ordered by dependency and user value. Running Python ML code as Argo Workflows jobs is the core developer experience, so it comes immediately after the foundation and tenancy.

| Phase | Goal | Exit criteria |
|---|---|---|
| **0. Decisions** ✅ | Settle the key architecture questions as [ADRs](adr/) | ADRs 0001–0008 accepted (done 2026-11-17) |
| **1. Foundation (AWS)** ([plan](phase-1-plan.md)) | Terraform for the VPC and the `mgmt` and `wl-nonprod` EKS clusters; Karpenter with CPU and GPU NodePools; Argo CD hub; identity; observability; local kind setup | `git push` reconciles both clusters; a GPU pod runs on a Karpenter-provisioned node and shows up in dashboards |
| **1a. Spike** | Argo Workflows + Kueue + Karpenter GPU queueing | Workflow GPU steps queue per tenant and run on scaled-up GPU nodes |
| **2. Tenancy** | `Tenant` API (Crossplane), Capsule, quotas, Kueue queues, policies, S3 bucket and IAM role per tenant | Two tenants can't see each other's workflows, data or network traffic; GPU quotas are enforced |
| **3. ML jobs** | Argo Workflows with SSO, Hera SDK, curated GPU images, golden-path templates, CronWorkflows | An ML engineer submits a Python training job with Hera, and it runs on GPU with artifacts in S3 |
| **4. Tracking & registry** | One shared MLflow (RDS PostgreSQL + S3) with OIDC SSO and per-tenant permissions, connected to the workflow templates | Training runs log to MLflow automatically; models are registered with lineage back to the workflow that produced them; tenant A cannot see tenant B's experiments, models or artifacts |
| **5. Serving & promotion** | `wl-prod` cluster, KServe with vLLM, `ModelDeployment` API, promotion from registry → GitOps PR → canary | Promoting a model in MLflow results in a canary endpoint in prod |
| **6. Portal & product** | Backstage templates and catalog, notebooks/workspaces, distributed training (Trainer/Ray), showback/chargeback per business unit, BU admin self-service | A new business unit onboards and reaches a served model with no operator help |

## Later

- Support for a second cloud provider
- Feature store (e.g. Feast)
- Model evaluation, guardrails and drift monitoring
- Model caching and warm pools for very large LLMs
- AI assistance in the platform: CI failure triage, a PR reviewer, an assistant in Backstage, failed-job explanations ([ADR-0017](adr/0017-ai-assistance-in-the-platform.md), parked)

## Key risks

| Risk | Mitigation |
|---|---|
| GPU cost and availability on AWS | Several instance families, spot for training, scale-to-zero, quotas from day one, capacity reservations where needed |
| Kueue integration with Argo Workflow pods | Phase 1a spike before building on it; fall back to Argo's own parallelism limits plus ResourceQuotas |
| Gaps in tenant isolation | Threat model in Phase 2; policy as code; gVisor for CPU and tenant-dedicated GPU nodes |
| Running several EKS clusters | Everything in Terraform and GitOps; upgrade non-prod first |
| Upgrade burden across many OSS components | Pinned versions, GitOps, staging first, a regular upgrade schedule |
| Slow cold starts for large models | Model caching, warm replicas, local model stores |
