# metrics-server (every cluster)

> Describes the code in [mlqube/gitops · `clusters/mgmt/metrics-server/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/metrics-server). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

Collects the **current CPU and memory use** of every node and pod from the kubelets, every 15 seconds, and serves it through the Kubernetes metrics API (`metrics.k8s.io`). Two things read it:

- **`kubectl top`**: `kubectl top nodes`, `kubectl top pods -A`.
- **The Horizontal Pod Autoscaler**: scaling a deployment on CPU or memory needs these numbers (later: model endpoints, the Backstage and MLflow servers).

It keeps **only the latest values**, no history. Dashboards, history and alerts come with observability ([Phase 1 plan, section 7](../../phase-1-plan.md#7-observability-per-adr-0012); ADR-0012 still to be written).

## What exists, and who creates it

| Created by | What |
|---|---|
| **Argo CD**, [`applicationset.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/metrics-server/applicationset.yaml) | metrics-server: Helm chart **3.14.0** (metrics-server 0.9.0), namespace `kube-system`, one replica, one Application per cluster (`<cluster>-metrics-server`) |
| **The chart** | The `APIService` `v1beta1.metrics.k8s.io`, which tells the Kubernetes API server to forward metrics requests to metrics-server (a cluster-wide kind, allowed in the `platform` project) |
| **Terraform** | Nothing: metrics-server needs no AWS permissions |

## Settings

| Value | Why |
|---|---|
| Chart defaults (`--kubelet-preferred-address-types=InternalIP,...`, `--kubelet-use-node-status-port`, `--metric-resolution=15s`) | Right for EKS as they are: metrics-server reaches each kubelet on the node's private IP |
| `replicas: 1` | Reference build; two in production, so `kubectl top` and autoscaling survive a node loss |
| `fullnameOverride: metrics-server` | Plain object names instead of names derived from the Application name |

## Checking it (once the platform runs)

```bash
kubectl --context mgmt get apiservice v1beta1.metrics.k8s.io   # AVAILABLE True
kubectl --context mgmt top nodes
```

`kubectl top` answers about a minute after metrics-server starts.
