# ADR-0008: Sandboxing and node isolation for untrusted tenant code

- **Status:** Proposed
- **Date:** 2026-11-17

## Context

In the shared tier ([ADR-0004](0004-tenancy-model.md)), tenants run arbitrary code (notebooks, workflow steps, training) on shared nodes. A container escape could expose another tenant's data. Considerations specific to EKS:

- EKS has no built-in managed sandbox (unlike GKE Sandbox).
- **gVisor** can be added with a custom node configuration and a RuntimeClass, but its GPU support covers only a subset of drivers and frameworks.
- **Kata Containers** needs bare-metal or nested-virtualization instances, which limits instance choice and raises cost.

## Options considered

1. **No sandboxing.** Rely only on Pod Security Standards and policy. Simplest, but weakest isolation.
2. **gVisor for CPU workloads plus tenant-dedicated GPU nodes.** Strong isolation where sandboxing works well, and node-level separation for GPU work.
3. **Kata Containers on bare-metal instances.** Strong isolation, but expensive and limited in instance types.
4. **Dedicated nodes per tenant for everything.** Strong isolation, but poor bin-packing and high cost.

## Decision

For the **shared tier**:

- **CPU workloads** (notebooks, CPU workflow steps) run with a **gVisor RuntimeClass** on a dedicated Karpenter NodePool configured for gVisor.
- **GPU workloads** run on **tenant-dedicated GPU nodes**. Karpenter launches GPU nodes tainted and labelled per tenant, so no two tenants share a GPU node. Kueue models these with a resource flavor per tenant.
- **Baseline for everything:** Pod Security Standards `restricted`, Kyverno policies, default-deny network policies, no access to the instance metadata service from pods (IMDSv2 hop limit), and IAM only through Pod Identity.
- Premium and enterprise tiers rely on vCluster with dedicated NodePools, or a dedicated cluster.

## Consequences

- Strong isolation without requiring bare-metal instances.
- GPU nodes aren't bin-packed across tenants, which costs more. Scale-to-zero, spot instances and right-sized instance types reduce the impact.
- The gVisor NodePool needs a custom AMI or node bootstrap, and gVisor imposes some performance and compatibility limits on CPU workloads.
- We will revisit running GPU workloads under gVisor as its GPU support matures.
