# Why an organization needs an ML/AI developer platform

Most organizations no longer ask *whether* to use ML and AI. They ask how to deliver it **repeatedly, safely and at reasonable cost**. Without a platform, every team builds its own path to production, and that doesn't scale. This document explains the case for an internal developer platform (IDP) for ML/AI, which is what MlQube provides.

---

## 1. What happens without a platform

| Symptom | What it looks like day to day | Business impact |
|---|---|---|
| **Slow time to production** | Models work in notebooks but take months to reach users; each deployment is a one-off project | Delayed ROI; AI initiatives stall after the pilot |
| **Every team builds its own stack** | Each team maintains its own Dockerfiles, training scripts, serving code, CI and dashboards | Duplicated engineering effort; inconsistent quality |
| **Expensive GPUs used badly** | Some GPUs sit idle while other teams wait in ticket queues; nobody knows who is using what | High cloud bills with low utilization |
| **No clear model lineage** | It's unclear which model version is live, what data trained it, or who approved it | Audit failures, incidents that can't be reproduced, regulatory exposure |
| **Shadow infrastructure** | Teams spin up unmanaged clusters, notebooks and API keys to get unblocked | Security gaps, data leakage, unmanaged spend |
| **Platform teams as a bottleneck** | Infrastructure engineers spend their time on tickets ("I need a GPU", "deploy my model") | Burned-out platform teams; frustrated ML teams |
| **Hard to hire and onboard** | New ML engineers spend weeks learning internal tooling before they deliver anything | Slower onboarding; talent spent on undifferentiated work |

## 2. What an ML platform changes

An IDP turns infrastructure into **self-service products with sensible defaults (golden paths)**. ML practitioners get a paved road from idea to production. Platform, security and finance teams get control and visibility without becoming gatekeepers.

| Without a platform | With MlQube |
|---|---|
| Ticket for a GPU, wait days | Self-service workspace with GPU quota in minutes |
| Hand-written training infrastructure | Templated, queued, autoscaled training jobs |
| Models copied to production by hand | Registry promotion creates a reviewed GitOps change |
| One-off serving code per model | Standard autoscaled endpoints with canary rollouts |
| Cost discovered on the monthly bill | Cost per tenant, project and model, visible as it happens |
| Security reviewed per project | Isolation, identity and policy built into the platform |

## 3. Value for each stakeholder

### Leadership / business
- **Faster time to value.** Shorter path from experiment to production, so AI investment pays back sooner.
- **Scales without growing headcount at the same rate.** One platform serves many teams.
- **Lower risk.** Consistent controls, auditability and compliance across all ML workloads.

### ML engineers and data scientists
- **Focus on models, not infrastructure.** No Kubernetes, CUDA or networking knowledge needed for the common path.
- **Fast feedback loops.** Workspaces, experiments and deployments in minutes, not weeks.
- **Freedom where it matters.** Golden paths for the common case, escape hatches for advanced needs.

### Platform and infrastructure teams
- **From tickets to products.** Teams use self-service APIs instead of filing requests.
- **One standard stack** to secure, upgrade and operate, instead of a dozen bespoke ones.
- **Declarative and GitOps-driven.** Every change is versioned, reviewable and reversible.

### Security, risk and compliance
- **Tenant and team isolation** at the network, identity, data and compute layers.
- **Policy as code.** Approved images, resource limits and egress rules are enforced automatically.
- **Full lineage.** Data → experiment → model version → deployment → approver.

### Finance (FinOps)
- **Cost attribution** per tenant, team, project and model.
- **Better GPU utilization** through queueing, fair-share quotas, autoscaling and scale-to-zero.
- **Predictable spend** with quotas and budgets enforced before costs pile up.

## 4. Why build it on Kubernetes

- **One substrate for everything.** Notebooks, distributed training, pipelines and inference all run on the same scheduler.
- **Elastic GPU capacity.** Node autoscaling and scale-to-zero make GPU spend follow demand.
- **A rich ML ecosystem.** KServe, Kubeflow, Ray, Kueue and MLflow are mature and community-backed.
- **Portable.** Runs on EKS, GKE and AKS, which avoids lock-in to a single vendor's ML service.
- **Declarative operations.** GitOps, policy engines and controllers make the platform reproducible and auditable.

## 5. Why not just use a managed ML service?

Managed services (e.g. cloud ML suites) are a valid choice for some organizations. An IDP like MlQube fits better when you need:

- **Control over cost.** Your own GPU capacity, spot instances, and no extra per-call markup.
- **Portability.** The same platform across clouds, or the option to move later.
- **Multi-tenancy.** Serving many internal teams or external customers with strict isolation and chargeback.
- **Openness.** Bringing your own frameworks, runtimes and open-weight models without waiting for vendor support.
- **Integration.** Fitting your existing identity, GitOps, security and observability standards.

## 6. Results to measure

An ML platform should prove its value with measurable outcomes:

| Metric | What it shows |
|---|---|
| **Time from idea to first deployed model** | Developer productivity and how well the golden paths work |
| **Deployment frequency and lead time for model changes** | Delivery speed (DORA-style metrics applied to ML) |
| **GPU utilization and idle GPU-hours** | Infrastructure efficiency |
| **Cost per training run / per 1K inferences, by tenant** | Unit economics and chargeback accuracy |
| **Share of production models with full lineage** | Governance and audit readiness |
| **Time to onboard a new team or engineer** | Platform usability |
| **Platform tickets per month** | Shift from gatekeeping to self-service |

## 7. When is it the right time?

An ML platform is worth the investment when several of these are true:

- More than one team is training or serving models
- GPU spend is significant or growing quickly
- Models are moving from pilots into customer-facing products
- Regulatory, audit or customer requirements call for lineage and isolation
- Platform engineers spend more time on requests than on improvements
- You offer ML capabilities to **multiple customers or business units** (multi-tenancy)

If only one small team ships an occasional model, a lightweight setup or a managed service may be enough. MlQube is aimed at organizations that have outgrown that stage.

---

**Next:** [Vision](vision.md) · [Architecture](architecture.md) · [Roadmap](roadmap.md)
