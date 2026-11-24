# ADR-0017: AI assistance in the platform

- **Status:** Proposed (parked for later: a list of use cases to revisit, nothing built yet)
- **Date:** 2026-11-24
- **Deciders:** platform team

## Context

MlQube already has what AI assistance needs to be useful and safe:

- **Knowledge in one place:** every design decision, page and runbook is in this repository ([platform docs](../platform/README.md), these ADRs).
- **One identity:** IAM Identity Center groups, passed to every tool through Dex as group IDs ([ADR-0015](0015-iam-identity-center-identity-hub.md)). An assistant can be scoped to a tenant with the same rules as RBAC.
- **Git as the only way to change things:** Terraform from CI, Argo CD from `gitops`. An assistant that may only *propose* a pull request can't break anything a reviewer doesn't approve.
- **Recurring, well-understood failures** worth explaining automatically: Terraform name limits, guardrail denials, pending pods, OOM-killed jobs, Kyverno audit findings.

Two audiences would gain: **ML engineers** using the golden path, and **the platform team** running it. This ADR records the candidate use cases and the rules any of them must follow, so they can be picked up when the platform is ready for them.

## Options considered (use cases)

### For ML engineers

1. **"Ask the platform" assistant in Backstage.** Answers "how do I request a GPU?" or "why is my workflow pending?" from the docs, plus read-only live state (Kueue, Argo Workflows, pod events) of the asking tenant's namespaces only. *Needs:* Backstage (golden path stage 3), Dex SSO.
2. **Natural language → GitOps pull request.** "Give retail-1042 two more GPUs in non-prod" → a drafted `Tenant` or quota change as a PR to `gitops`; a person approves, Argo CD applies. *Needs:* the `Tenant` API (Phase 2).
3. **Failed-job explainer.** When an Argo Workflow fails, a short diagnosis from the pod events and logs is attached to the workflow ("OOMKilled: request 16Gi, or use g6.2xlarge"). *Needs:* Argo Workflows (Phase 1a / 3).

### For the platform team

4. **CI failure triage.** When `platform.yml` fails, a step sends the failed Terraform or Helm output to an LLM and posts the diagnosis in the run summary. *Needs:* nothing new in the clusters: one workflow step and an API key.
5. **Pull request reviewer for `infrastructure` and `gitops`.** Checks the project's own conventions: a new add-on adds its chart repository, namespace and cluster-wide kinds to the `platform` AppProject; chart versions at least two weeks old; `serviceAccount.name` pinned for Pod Identity; secrets under `mlqube/platform/<add-on>/<name>`. *Needs:* nothing new in the clusters.
6. **Kyverno policy-report summary.** A weekly summary of the Audit-mode PolicyReports per tenant, with drafted fixes, to move policies to Enforce with confidence. *Needs:* Kyverno (deployed), a scheduled job.

### As a platform feature

7. **LLM serving for tenants.** vLLM on KServe as an internal, OpenAI-compatible endpoint per tenant, metered by the tenant label. Makes MlQube a platform for AI applications, not only for ML training. *Needs:* KServe and GPU nodes (Phase 5).
8. **FinOps advisor.** Reads OpenCost and Karpenter data and suggests changes ("retail-1042's GPU nodes were 12% utilized last week; use g6.xlarge"). *Needs:* OpenCost and observability (Phase 6, ADR-0012).

## Decision

**Not decided yet; parked.** When revisited, the suggested order is:

| Order | Use case | Why then |
|---|---|---|
| 1 | **4. CI failure triage** | Smallest (one GitHub Actions step), no cluster components, useful in every build |
| 2 | **5. PR reviewer** | Same shape as 4; enforces conventions that today live only in docs |
| 3 | **1. Backstage assistant** | Together with Backstage in golden path stage 3 |
| 4 | **3. Failed-job explainer** | Once Argo Workflows runs tenants' jobs |
| later | 2, 6, 7, 8 | Each after the component it depends on |

Whatever is built follows these rules:

- **Read-only by default.** An assistant reads docs, logs and status; it never runs `kubectl apply`, `terraform apply` or cloud API calls that change anything.
- **Changes only as pull requests**, reviewed by a person and applied by the existing pipelines (CI, Argo CD).
- **Tenant-scoped data.** An assistant serving a user sees only what that user's groups may see (the same group IDs as RBAC); no cross-tenant answers.
- **No secrets in prompts.** Logs are filtered before they are sent; API keys for the model provider live in AWS Secrets Manager (`mlqube/platform/<add-on>/<name>`) or GitHub secrets, never in the repositories.
- **Provider choice recorded.** Which model provider (an API such as Claude, or a model served in-cluster), and what data may leave the account, is decided per use case in its own ADR before it is built.

## Consequences

- The ideas are kept in one place with their dependencies, so each can be picked up when its prerequisite exists.
- Each use case built later gets its own ADR (provider, data flow, cost) that refers back to this one; this ADR moves to Accepted when the first one is accepted.
- Cost and data residency need attention once tenants' logs or code are sent to an external model; use case 7 (in-cluster models) is the answer where data may not leave the account.
