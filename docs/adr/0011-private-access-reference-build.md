# ADR-0011: Private access for the reference build with a Tailscale subnet router

- **Status:** Accepted
- **Date:** 2026-11-18
- **Update:** the build runs with private EKS endpoints only (operator and CI through Tailscale), see [ADR-0014](0014-ci-access-to-private-clusters.md)

## Context

[ADR-0010](0010-ingress.md) puts all MlQube web tools and model endpoints behind **internal** ALBs in private subnets, reached over the corporate network / VPN. In an organization, that VPN already exists.

The first MlQube build is a **reference build** in a single personal AWS account (us-west-2). There is no corporate network or VPN, there is one user (the platform owner), and cost must stay low: the platform is created with Terraform when needed and destroyed after each test session. We still want to exercise the real design (internal ALBs, private DNS, TLS names) rather than work around it.

Two kinds of access are needed:

- **Kubernetes API** for `kubectl`, Terraform and Helm.
- **Web UIs and endpoints** behind the internal ALBs (Argo CD and Grafana in Phase 1; Backstage, MLflow, Argo Workflows and model endpoints later), using names from the Route 53 private hosted zone.

## Options considered

1. **AWS Client VPN** with SAML sign-in. All-AWS and closest to a corporate VPN, but needs certificates and a SAML app, and costs about $0.15 per hour while running.
2. **Tailscale subnet router** (WireGuard mesh VPN). Free personal plan, about 15 minutes to set up, private DNS works through split DNS. A third-party service.
3. **SSM Session Manager port forwarding.** No inbound ports, but one tunnel per service and TLS names don't match `localhost`. Awkward for browsers.
4. **`kubectl port-forward`.** Nothing to deploy, but it bypasses the ALB and DNS, so the ingress design isn't tested. *Kept as a debugging shortcut only.*
5. **Internet-facing ALB limited to one IP.** Cheapest, but breaks ADR-0010. *Rejected.*

## Decision

For the reference build, use a **Tailscale subnet router** for the web UIs, and a **restricted public EKS endpoint** for the Kubernetes API.

| Concern | Decision |
|---|---|
| **Router placement** | A small EC2 instance (e.g. `t4g.nano`) in a **private subnet of the mgmt VPC**, created by the platform's Terraform and destroyed with it. It runs outside the clusters, so access still works when a cluster is broken or being rebuilt. |
| **Joining the tailnet** | Terraform passes a **pre-authorized, tagged auth key** (`tag:mlqube-router`), stored in AWS Secrets Manager. The tailnet policy **auto-approves** the router's advertised routes, so rebuilding needs no manual steps. |
| **Routes** | The router advertises the mgmt and non-prod VPC address ranges. The VPCs are connected to each other, so one router reaches both. VPC ranges must not overlap with the home network. |
| **DNS** | **Split DNS** in Tailscale: names under the MlQube domain are resolved by the VPC's DNS resolver, i.e. the Route 53 private hosted zone. All other names use the laptop's normal DNS. |
| **Network exposure** | The router has no public IP and no inbound ports; it only connects outward through the NAT gateway. Traffic is end-to-end encrypted with WireGuard. |
| **Access control** | Tailnet access rules allow only the platform owner to use the router. VPC security groups still apply. |
| **Kubernetes API** | EKS **public and private** endpoints enabled; the public endpoint is limited to the owner's IP address. Every call is still authenticated with AWS identity (IAM Identity Center) and authorized by Kubernetes RBAC. |
| **Scope** | **Reference build only.** An organization deploying MlQube uses its corporate VPN or network connectivity instead, as ADR-0010 describes; nothing else in the platform changes. |

## Consequences

- The real ingress design is exercised end to end: internal ALB, private DNS names and valid TLS certificates, with nothing exposed to the internet.
- Almost no cost: Tailscale's free personal plan, plus the small instance while the platform runs (about $0.10 per day). Nothing once destroyed.
- MlQube depends on a third-party service for operator access in the reference build. If Tailscale is unavailable, `kubectl port-forward` through the EKS endpoint still works for debugging.
- The tailnet auth key is a secret: it must be tagged, pre-authorized for this purpose only, rotated before it expires, and never committed to Git.
- The owner's public IP may change, so the EKS endpoint allowlist must be easy to update (a Terraform variable).
- **Follow-up:** choose VPC CIDR ranges that don't overlap the home network, and set up the tailnet (account, tag, auto-approval and split DNS) before the first `terraform apply`.
