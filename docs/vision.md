# Vision

## Problem

Teams building ML and AI products repeatedly hit the same infrastructure problems:

- **GPU access is slow and unfair.** Requests go through tickets, quotas are managed by hand, and expensive GPUs sit idle or are hoarded.
- **The path from notebook to production is hand-built.** Every team writes its own training scripts, Dockerfiles, serving code and deployment manifests.
- **Model lifecycle is opaque.** It's unclear which model version is in production, who promoted it, or what data trained it.
- **Costs are invisible.** GPU spend can't easily be attributed to business units, teams or projects.
- **Kubernetes is powerful but hard.** Data scientists shouldn't need to learn CRDs, node pools and ingress controllers to ship a model.

For the full organizational case, including value for each stakeholder and results to measure, see [Why an organization needs an ML/AI developer platform](why-an-ml-idp.md).

## What MlQube is

MlQube is an **internal developer platform (IDP)** for a single organization, in which each **business unit is a tenant**. It runs on managed Kubernetes, starting with **Amazon EKS on AWS**. It gives ML practitioners self-service golden paths to **build, train, register and serve models**, and gives platform operators control over isolation, quotas, cost and upgrades.

MlQube **assembles proven open-source projects** instead of reinventing them. Its own code is a thin glue layer ([the MlQube glue](glue.md)):

- Higher-level platform resources (`Tenant`, `MLProject`, `Workspace`, `ModelDeployment`)
- Developer portal templates and plugins
- Tenancy, policy and metering that tie the components together

## Personas

| Persona | Needs |
|---|---|
| **ML engineer / data scientist** | GPU notebooks, training jobs, experiment tracking, one-click model endpoints |
| **Business-unit admin** | Manage members, quotas and spend for their business unit (tenant) |
| **Platform operator** | Run the fleet safely: provision tenants, upgrade components, enforce policy, report cost per business unit |

## Goals

1. **Self-service.** A new project, from template to served endpoint, needs no help from the platform team.
2. **Fair, efficient GPU use.** Queueing, quotas, autoscaling and scale-to-zero by default.
3. **Auditable model lifecycle.** Every promotion is a versioned, reviewed change (GitOps).
4. **Strong tenant isolation.** Separate network, identity, data and compute boundaries per tenant.
5. **Cost transparency.** GPU-hours and serving usage attributed per tenant and project.
6. **Python-first.** ML engineers write Python and run it as jobs and pipelines (Argo Workflows with Hera), with no YAML required.
7. **Portable.** AWS first, with infrastructure modules designed so other clouds can be added.

## Non-goals (for now)

- Building our own training framework, serving runtime or experiment tracker
- Supporting on-prem or bare-metal clusters in the first release
- Feature stores, data labeling and model evaluation suites (possible later additions)
- Replacing general-purpose application platforms; MlQube focuses on ML workloads

## Guiding principles

- **Assemble, don't reinvent.** Prefer CNCF and well-adopted OSS; build only the glue.
- **Everything is declarative.** Platform and tenant state live in Git and are reconciled by controllers.
- **Golden paths, not golden cages.** Opinionated defaults, with escape hatches for advanced users.
- **Secure by default.** Isolation, least privilege and policy enforcement are part of the platform, not optional extras.
- **Measure everything.** Usage, performance and cost are first-class signals.
