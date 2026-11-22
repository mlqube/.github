# ADR-0013: AWS VPC CNI with prefix delegation and built-in network policy enforcement

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Every EKS cluster needs a **CNI** (container network interface) plugin, which gives pods their IP addresses and connects them. [ADR-0004](0004-tenancy-model.md) also requires **default-deny network policies** in every tenant namespace, so something must enforce Kubernetes `NetworkPolicy` objects. No decision says what does either.

Forces:

- **Address space.** With the AWS VPC CNI, every pod gets an IP address from a VPC subnet. The reference build's VPCs have two `/18` private subnets each (about 32,000 addresses per environment), so addresses are plentiful. In an organization, VPC ranges handed out by the corporate network team can be much smaller.
- **The EKS control plane runs outside the cluster's network.** It must reach admission webhooks and API services running as pods (Kyverno, Capsule, cert-manager, AWS Load Balancer Controller, Karpenter, KServe, metrics-server). That works only if pod IPs are routable in the VPC.
- **Load balancing.** Internal ALBs ([ADR-0010](0010-ingress.md)) can send traffic straight to pod IPs (`target-type: ip`) only if pods have VPC addresses.
- **Performance.** Training and inference traffic between GPU nodes should not pay for encapsulation.
- **Tailscale** ([ADR-0011](0011-private-access-reference-build.md)) uses `100.64.0.0/10`, which rules out that range for any additional pod addresses.

## Options considered

1. **AWS VPC CNI with prefix delegation, enforcing network policies itself.** Pods get native VPC IP addresses; prefix delegation hands each node blocks of 16 addresses, which raises the number of pods per node. Since 2023 the VPC CNI can enforce standard Kubernetes `NetworkPolicy`. Managed as an EKS add-on and supported by AWS.
2. **AWS VPC CNI plus Calico in policy-only mode.** Same addressing as option 1; Calico enforces policies and adds features such as cluster-wide (global) policies, policy tiers and DNS-based rules. One more component to run.
3. **Calico as the CNI (overlay, VXLAN or IP-in-IP).** Pods get addresses from a Calico pool, so only nodes use VPC addresses. But the EKS control plane can't reach overlay pod IPs, so every webhook and API service needs `hostNetwork: true`; ALBs can't target pods directly; AWS doesn't support third-party CNIs (no security groups for pods, no Fargate); encapsulation adds overhead.
4. **Cilium** (ENI mode or overlay). Rich policy and observability, but a bigger component to operate, with the same overlay trade-offs as option 3 in overlay mode.
5. **IPv6 cluster.** Practically unlimited pod addresses, but a larger design change for every component and integration.

## Decision

Use **option 1**: the **AWS VPC CNI** in every EKS cluster.

| Concern | Decision |
|---|---|
| **Installation** | The `vpc-cni` EKS managed add-on, version pinned, installed with the cluster by Terraform |
| **Pod addresses** | From the cluster's private subnets ([network layer](../platform/infrastructure/network.md)) |
| **Pods per node** | **Prefix delegation** on (`ENABLE_PREFIX_DELEGATION=true`); node `maxPods` set to match, so nodes aren't limited by the number of network interfaces |
| **Network policies** | Enforced by the VPC CNI's network policy agent (`enableNetworkPolicy: "true"`). Each tenant namespace gets a **default-deny** policy plus explicit allows (DNS, platform services), created by the `Tenant` API ([ADR-0006](0006-platform-apis-with-crossplane.md)) |
| **Calico** | Not used now. It can be added later in **policy-only** mode (option 2) if MlQube needs cluster-wide policies, policy tiers or DNS-based rules, without changing pod addressing |
| **If addresses become scarce** | Use **custom networking** with a secondary VPC CIDR for pods, **not** in `100.64.0.0/10` (Tailscale): e.g. `198.19.0.0/16`. Pods stay routable in the VPC, so webhooks and ALBs keep working. An overlay CNI (option 3) is the last resort |

## Consequences

- Pods are ordinary VPC addresses: webhooks, ALB `target-type: ip`, security groups for pods and VPC flow logs all work without extra configuration, and GPU traffic isn't encapsulated.
- Pods consume VPC addresses, so subnet sizing matters. The reference build's `/18` private subnets are far larger than needed; an organization with a small corporate range should plan for custom networking from the start.
- The VPC CNI enforces standard Kubernetes `NetworkPolicy` only: no cluster-wide or DNS-based policies. Tenant isolation must be expressed per namespace, which the `Tenant` API automates.
- Network policy enforcement needs a recent VPC CNI version and a supported node OS (e.g. Amazon Linux 2023 or Bottlerocket); this is checked when the EKS layer is built.
- **Follow-up (EKS layer, Phase 1):** install the `vpc-cni` add-on with prefix delegation and network policy enforcement on; verify that a default-deny policy blocks traffic between two test namespaces.
