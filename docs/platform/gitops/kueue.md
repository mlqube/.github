# Kueue (workload clusters)

> Describes the code in [mlqube/gitops · `clusters/mgmt/kueue/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/kueue) and [`platform/kueue/`](https://github.com/mlqube/gitops/tree/main/platform/kueue). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

> **Status:** 🕓 written (golden path v0, section 1); first test at the next build.

**Kueue is the job queue for ML work.** Plain Kubernetes starts every pod as soon as it can, so a burst of GPU jobs from several teams fights over the GPUs in no particular order. Kueue decides **when** a job may start: each tenant has a budget (GPUs, CPU, memory), jobs wait their turn in a queue, and a job starts only when its tenant's budget allows. Idle budget can be borrowed and is given back when its owner needs it.

[Karpenter](karpenter.md) decides **where** a job runs: once Kueue admits a pod, Karpenter starts a node that fits it. So only admitted work makes Karpenter start GPU nodes, and GPU spend stays within each tenant's quota.

It's an official Kubernetes project (the batch working group). Golden path v0, [ADR-0016](../../adr/0016-golden-path-v0.md) decision 8.

## How a job goes through it

```
Workflow step pod, label kueue.x-k8s.io/queue-name: dev
      │  (in a tenant namespace: label mlqube/tenant)
      ▼
LocalQueue "dev" (project namespace) ──► ClusterQueue "<tenant>" (quota: e.g. 4 GPUs)
      │  quota left?   no  → the pod waits behind a scheduling gate (not a stuck Pending pod)
      │                yes → admitted under a ResourceFlavor (gpu → NodePool "gpu")
      ▼
gate removed, node label + toleration added ──► Karpenter starts a GPU node ──► the step runs
```

| Object | What it is | Where it comes from |
|---|---|---|
| **ResourceFlavor** | What a unit of quota means: which nodes. `cpu` → Karpenter NodePool `general`; `gpu` → NodePool `gpu` (with the `nvidia.com/gpu` toleration) | Platform: [`platform/kueue/wl-nonprod/resource-flavors.yaml`](https://github.com/mlqube/gitops/blob/main/platform/kueue/wl-nonprod/resource-flavors.yaml) |
| **WorkloadPriorityClass** | Order inside a queue: `mlqube-main` (1000) before `mlqube-dev` (100), so feature-branch runs never hold up official runs | Platform: [`priority-classes.yaml`](https://github.com/mlqube/gitops/blob/main/platform/kueue/wl-nonprod/priority-classes.yaml) |
| **ClusterQueue** | A tenant's budget, per flavor | Per tenant: [golden path v0 plan](../../golden-path-v0-plan.md) section 2 (by hand), later the glue's `Tenant` |
| **LocalQueue** | The door into a ClusterQueue, in a namespace: `dev` and `main` per project | Per project, the same way |
| **Cohort** | A group of ClusterQueues that may borrow each other's idle quota | With the tenants |

## What exists, and who creates it

| What | Created by | Where |
|---|---|---|
| Kueue (controller, webhooks, CRDs), namespace `kueue-system` | Argo CD, ApplicationSet `kueue` (`<cluster>-kueue`) | Workload clusters only (`mlqube/role: spoke`) |
| ResourceFlavors, WorkloadPriorityClasses | Argo CD, ApplicationSet `kueue-config` (`<cluster>-kueue-config`), from `platform/kueue/<cluster>/` | Same |
| The Helm chart's OCI location | [`clusters/mgmt/kueue/oci-repository.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/kueue/oci-repository.yaml) (public registry, no credentials) | Argo CD in mgmt |

No AWS permissions.

## Settings

| Setting | Value | Why |
|---|---|---|
| Chart | `registry.k8s.io/kueue/charts/kueue` **0.20.5** (Kueue v0.20.5, released 2026-11-05) | At least two weeks old when chosen |
| Integrations | `batch/job`, `pod` | Argo Workflows' step pods are plain pods; batch Jobs for anything else |
| `managedJobsNamespaceSelector` | namespaces with the label `mlqube/tenant` | The platform's own pods (kube-system, argo, ...) are never queued |
| `manageJobsWithoutQueueName` | `false` | Only pods that name a queue are managed |
| Finished workloads | deleted after 72 h | The run's record lives in Argo Workflows and MLflow |
| Replicas | 1 | Reference build; two in production |

## Testing it (build A)

The Phase 1a question: does Kueue queue Argo Workflow steps per tenant, and do GPU nodes follow? Until section 2 adds real tenants, the test uses two throwaway tenants with one GPU each.

```bash
kubectl --context wl-nonprod get pods -n kueue-system
kubectl --context wl-nonprod get resourceflavors,workloadpriorityclasses
```

Test tenants (apply, test, delete):

```yaml
apiVersion: v1
kind: Namespace
metadata: {name: test-a, labels: {mlqube/tenant: test-a}}
---
apiVersion: kueue.x-k8s.io/v1beta2
kind: ClusterQueue
metadata: {name: test-a}
spec:
  namespaceSelector: {matchLabels: {mlqube/tenant: test-a}}
  resourceGroups:
    - coveredResources: [cpu, memory, nvidia.com/gpu]
      flavors:
        - name: gpu
          resources:
            - {name: cpu, nominalQuota: 8}
            - {name: memory, nominalQuota: 32Gi}
            - {name: nvidia.com/gpu, nominalQuota: 1}
---
apiVersion: kueue.x-k8s.io/v1beta2
kind: LocalQueue
metadata: {name: dev, namespace: test-a}
spec: {clusterQueue: test-a}
```

(and the same for `test-b`), plus a workflow whose pods name the queue:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata: {generateName: gpu-, namespace: test-a}
spec:
  serviceAccountName: workflow   # with the executor's RBAC (workflowtaskresults)
  podMetadata:
    labels: {kueue.x-k8s.io/queue-name: dev}
  entrypoint: main
  templates:
    - name: main
      container:
        image: nvcr.io/nvidia/cuda:12.6.3-base-ubuntu24.04
        command: [sh, -c, "nvidia-smi && sleep 120"]
        resources: {limits: {nvidia.com/gpu: 1}}
```

What to check:

- [ ] One workflow in `test-a`: its pod is gated, then admitted (`kubectl get workloads -n test-a`), a GPU node starts, `nvidia-smi` runs, the node goes away afterwards
- [ ] Two workflows in `test-a` at once: the second waits until the first finishes (quota 1 GPU)
- [ ] One workflow in `test-b` at the same time runs (its own quota), within the GPU NodePool's limit
- [ ] A pod in a namespace **without** `mlqube/tenant` is not touched by Kueue

If Kueue and Argo's pods don't work well together, the fallback is Argo's parallelism limits plus ResourceQuotas ([ADR-0005](../../adr/0005-argo-workflows-with-hera-for-ml-jobs.md)).

## Related

- [Argo Workflows](argo-workflows.md) · [Karpenter](karpenter.md) (the `gpu` NodePool)
- [The golden path](../../golden-path.md): where the `dev` and `main` queues appear for an ML engineer
