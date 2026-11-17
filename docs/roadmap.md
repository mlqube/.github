# Roadmap

> Phases are ordered by dependency and the value they deliver. Serving comes before training on purpose: it delivers visible value early and tests tenancy and networking first.

| Phase | Goal | Exit criteria |
|---|---|---|
| **0. Decisions** | Settle the key architecture questions as ADRs | Architecture signed off; ADRs accepted |
| **1. Foundation** | One cloud: IaC, cluster with GPU node pool, GitOps, identity, observability | `git push` reconciles the whole platform; a GPU workload runs and is visible in dashboards |
| **2. Tenancy** | `Tenant` API, isolation, quotas, Kueue, policies | Two tenants can't see each other's data or network traffic; GPU quotas are enforced |
| **3. Serving** | KServe with vLLM, gateway, autoscaling, `ModelDeployment` API | A tenant deploys an open LLM and a classic model through a declarative resource |
| **4. Registry + CI/CD** | MLflow per tenant; registry promotion → GitOps PR → canary | Promoting a model version in the registry results in a canary deployment |
| **5. Training + workspaces** | Notebooks, Kubeflow Trainer / KubeRay, pipelines | The full golden path works end to end |
| **6. Portal & product** | Backstage templates and catalog, metering, billing export, tenant admin | A new tenant onboards without operator help |

## Later

- Support for a second cloud provider
- Dedicated-cluster enterprise tier
- Feature store (e.g. Feast)
- Model evaluation, guardrails, and drift monitoring
- Model caching and warm pools for very large LLMs

## Key risks

| Risk | Mitigation |
|---|---|
| GPU cost and availability | Scale-to-zero, spot capacity for training, quotas from day one |
| Gaps in tenant isolation | Threat model in Phase 2; policy-as-code; optional sandboxed runtimes |
| Upgrade burden across many OSS components | Pinned versions, GitOps, a staging cluster, and an upgrade schedule |
| Slow cold starts for large models | Model caching, warm replicas, local model stores |
