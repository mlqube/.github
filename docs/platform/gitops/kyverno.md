# Kyverno (every cluster)

> Describes the code in [mlqube/gitops · `clusters/mgmt/kyverno/`](https://github.com/mlqube/gitops/tree/main/clusters/mgmt/kyverno). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

Kyverno is the clusters' **policy engine**. Every object sent to the Kubernetes API (a pod, a deployment, ...) passes through it and is checked against the policies. It also rechecks, every hour, the objects already in the cluster. The results go into **PolicyReports**, one per namespace.

Today it runs the **Pod Security Standards "baseline"** policies in **Audit** mode: violations are **reported, never blocked**. Later the same engine carries the tenant guardrails: required labels, allowed images, quotas (Phase 2).

## The policies

From Kyverno's own policies chart, as CEL `ValidatingPolicy` objects (cluster-wide):

| Policy | Flags a pod that ... |
|---|---|
| `disallow-privileged-containers` | runs a privileged container |
| `disallow-host-namespaces` | shares the node's network, PID or IPC namespace |
| `disallow-host-path` | mounts a directory of the node |
| `disallow-host-ports` | binds a port on the node |
| `disallow-host-process` | runs a Windows host process |
| `disallow-capabilities` | adds Linux capabilities beyond the default set |
| `disallow-proc-mount` | changes the `/proc` mount type |
| `disallow-selinux` | sets custom SELinux options |
| `restrict-apparmor-profiles` | uses an AppArmor profile other than the default |
| `restrict-seccomp` | turns seccomp off (`Unconfined`) |
| `restrict-sysctls` | sets unsafe sysctls |

These are the same rules as the Kubernetes "baseline" Pod Security Standard: they stop a pod from taking over its node. `kube-system` (the VPC CNI and kube-proxy need node access) and `kyverno` are excluded.

## Audit now, Enforce later

| Mode | What happens to a violating pod |
|---|---|
| **Audit** (now) | It is created; the violation shows up in the namespace's PolicyReport |
| **Enforce** (later) | The API refuses it, with the policy's message |

Audit first, so a policy can never stop an add-on from starting on its first build. To move to Enforce:
1. At a build, read the reports (`kubectl get policyreport -A`) and check that the platform's own pods pass.
2. For each platform pod that legitimately needs an exception, add a narrow `PolicyException`.
3. Change `validationFailureAction` to `Enforce` in [`policies-applicationset.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/kyverno/policies-applicationset.yaml).
4. Revisit `forceFailurePolicyIgnore` (below): with Enforce, failing open means a Kyverno outage lets violations through.

## What exists, and who creates it

| Created by | What |
|---|---|
| **Argo CD**, [`applicationset.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/kyverno/applicationset.yaml) | Kyverno: Helm chart **3.9.2** (Kyverno v1.19.2), namespace `kyverno`, one Application per cluster (`<cluster>-kyverno`). Four deployments: the admission controller (checks requests), the background controller, the cleanup controller and the reports controller |
| **Argo CD**, [`policies-applicationset.yaml`](https://github.com/mlqube/gitops/blob/main/clusters/mgmt/kyverno/policies-applicationset.yaml) | The 11 baseline policies: Kyverno's `kyverno-policies` chart 3.9.2, one Application per cluster (`<cluster>-kyverno-policies`) |
| **Kyverno, at runtime** | Its webhook configurations (it manages them itself, so Argo CD doesn't track them), native ValidatingAdmissionPolicies generated from the CEL policies, and the PolicyReports |
| **Terraform** | Nothing: Kyverno needs no AWS permissions |

The policies Application needs Kyverno's CRDs. On the first sync it retries until `<cluster>-kyverno` has installed them (sync waves: [mlqube/.github#13](https://github.com/mlqube/.github/issues/13)).

## Settings

| Value | Why |
|---|---|
| `features.forceFailurePolicyIgnore.enabled: true` | Kyverno's webhooks **fail open**: if Kyverno is down or has been removed, the API accepts requests instead of refusing everything. Right for Audit; revisit with Enforce |
| `crds.migration.enabled: false` | A Helm post-upgrade job that migrates stored objects between CRD versions. Argo CD would rerun it after every sync, and every build starts empty. Turn it on for one sync when upgrading Kyverno across CRD versions on a live cluster |
| `webhooksCleanup.enabled: false` | Helm pre-delete jobs that remove Kyverno's webhooks on uninstall. Argo CD doesn't run pre-delete hooks; failing open makes leftover webhooks harmless instead |
| `replicas: 1` for each controller | Reference build. Production: three admission controllers, so policy checks survive a node loss |
| `fullnameOverride: kyverno` | Plain object names instead of names derived from the Application name |

The chart's Helm **test** pods are hooks, which Argo CD doesn't create.

## Checking it (once the platform runs)

```bash
kubectl get validatingpolicies               # 11 policies, READY True
kubectl get policyreport -A                  # PASS / FAIL counts per namespace
```

A quick test: create a privileged pod in a test namespace. It is created (Audit), and within a minute the namespace's PolicyReport shows a FAIL for `disallow-privileged-containers`. Then delete it.
