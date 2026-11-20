# ADR-0014: CI reaches the private cluster APIs through Tailscale (Argo CD bootstrap)

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

The EKS API endpoints of the reference build are **private only**. [ADR-0011](0011-private-access-reference-build.md) allowed a public endpoint limited to the owner's IP, but the build runs with that list empty: the operator reaches the APIs through the Tailscale subnet router, like the web UIs.

All changes run from GitHub Actions, never from a laptop. Creating AWS resources works because the AWS APIs are public. But installing **Argo CD**, the first thing inside the management cluster, needs the Kubernetes API, and GitHub-hosted runners are on the internet. Once Argo CD runs, it installs everything else from the `gitops` repository from inside the cluster, so this is mainly a **one-time bootstrap** step per cluster build, repeated on every create/destroy cycle.

## Options considered

1. **Tailscale in the workflow.** The job joins the tailnet as a temporary (ephemeral) device tagged `tag:ci` and reaches the API through the existing subnet router, the same path the operator uses. It signs in with **workload identity federation** (GitHub's OIDC token, like the AWS sign-in), so no Tailscale secret is stored. Argo CD stays a normal open-source install that we control.
2. **EKS managed Argo CD (EKS Capabilities).** AWS runs Argo CD and it is configured through the EKS API, so no path into the cluster is needed. But it adds an hourly AWS charge, ties the UI sign-in to IAM Identity Center, and is less like the self-run setup a company would use.
3. **Public endpoint open to GitHub's IP ranges.** GitHub uses thousands of IP ranges, so the API would be effectively public. Goes against ADR-0011. *Rejected.*
4. **Self-hosted runner inside the VPC.** Works, but it is another always-on machine to patch and pay for, in a build that is destroyed after each session. *Rejected for the reference build.*

## Decision

Use **Tailscale in the workflow** (option 1) for jobs that need a cluster API.

| Concern | Decision |
|---|---|
| **Sign-in** | Tailscale workload identity federation: a trust credential that accepts GitHub OIDC tokens from the `mlqube/infrastructure` repository only (immutable subject), with the `auth_keys` scope and `tag:ci`. Nothing secret is stored in GitHub. |
| **Device** | Ephemeral, tagged `tag:ci`; it accepts the router's subnet routes and is removed automatically after the job. |
| **Which jobs** | Only Terraform layers that talk to a cluster API, starting with `addons-mgmt` (Argo CD on mgmt). Network and cluster layers use AWS APIs only and don't join the tailnet. |
| **What Terraform installs** | Only the bootstrap: the Argo CD Helm chart, the `gitops` repository credentials (a read-only deploy key from SSM Parameter Store), and one root Application ("app of apps") pointing at the `gitops` repository. Everything else is installed by Argo CD. |
| **Who may do what** | The CI apply role is cluster-admin (EKS access entry). Tailnet access rules can later limit `tag:ci` to the VPC ranges. |
| **Scope** | **Reference build only.** An organization uses its own network path (runners inside the network, or its VPN), as ADR-0010 and ADR-0011 describe. |

## Consequences

- The clusters stay private: no public API endpoint, and nothing is exposed to the internet.
- No new secret: the Tailscale sign-in works like the AWS sign-in (OIDC). The only new secret is the `gitops` deploy key, kept in SSM Parameter Store like the router's auth key.
- Cluster-facing jobs depend on the subnet router: if it is down, they fail early with a connection error.
- Destroying Argo CD does not remove AWS resources that its add-ons created (load balancers, DNS records). Before the network can be destroyed, those must be removed first; this is handled when the first such add-on (AWS Load Balancer Controller) is added.
- **Follow-up:** single sign-on to Argo CD (ADR-0009) once ingress and DNS add-ons exist; until then the UI is reached with `kubectl port-forward` and the initial admin password.
