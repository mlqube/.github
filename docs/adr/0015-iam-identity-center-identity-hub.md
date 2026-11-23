# ADR-0015: IAM Identity Center as the identity hub

- **Status:** Accepted (amends [ADR-0009](0009-identity-provider.md))
- **Date:** 2026-11-22

## Context

[ADR-0009](0009-identity-provider.md) chose single sign-on with the corporate identity provider (e.g. Entra ID or Okta) over OIDC: every tool an OIDC client of the IdP, and each EKS cluster associated with the IdP as an OIDC identity provider for `kubectl`.

Building Argo CD's sign-in showed a better fit for MlQube on AWS:

- People already sign in to AWS through **IAM Identity Center** (permission sets, the group `mlqube-platform-admins`), and `kubectl` already works through it: Identity Center role → IAM → **EKS access entries**. A second identity path into the clusters (EKS OIDC providers) would duplicate that.
- Organizations that run AWS at scale usually connect their corporate directory **into** IAM Identity Center (SAML federation for sign-in, SCIM for users and groups), and manage AWS access there. Identity Center is then the natural hub for the platform's tools as well.
- The reference build has no corporate directory at all; Identity Center (free) provides users, groups and MFA directly.

Constraint found on the way: Identity Center offers **SAML 2.0**, not OIDC, for customer-managed applications.

## Options considered

1. **Keep ADR-0009 as written** (corporate IdP directly, OIDC everywhere). Native OIDC in every tool and group names in tokens, but a second identity path next to AWS access, and nothing to use in the reference build without creating a separate IdP tenant.
2. **IAM Identity Center as the hub, tools through a broker.** One place for people, groups and AWS access; the corporate directory (when there is one) feeds it. Tools that speak SAML use it directly; the rest go through **Dex**, which turns Identity Center's SAML into OIDC. Groups arrive as **IDs**, not names.
3. **Identity Center for AWS only, corporate IdP for the tools.** Two systems to keep in sync for the same people and groups. *Rejected.*

## Decision

**IAM Identity Center is MlQube's identity hub** (option 2). ADR-0009's goals stay: one identity per person, groups per tenant (`mlqube-<tenant>-admins` / `-developers` / `-viewers`), access decided by group, no static keys for workloads. What changes is the mechanism:

| Concern | ADR-0009 | Now |
|---|---|---|
| **Source of people and groups** | The corporate IdP | **IAM Identity Center**. In an organization, an external directory can feed it through SAML federation and SCIM; MFA and conditional access stay with the directory |
| **Tools** (Argo CD, Backstage, Grafana, MLflow, Argo Workflows) | OIDC clients of the IdP | **SAML applications in Identity Center**, through **Dex**, a standalone add-on in the management cluster ([Dex](../platform/gitops/dex.md)), where a tool speaks only OIDC (Argo CD today: [docs/platform/infrastructure/addons-mgmt.md](../platform/infrastructure/addons-mgmt.md#single-sign-on-ssotf)). Only people assigned to an application can sign in at all |
| **Groups in tokens** | Group names (or IDs, depending on the IdP) | **Group IDs** (Identity Center sends IDs). RBAC rules map IDs; the ID of each group is kept next to its name (SSM parameter today) |
| **`kubectl`** | EKS associated with the IdP as an OIDC identity provider | Identity Center **permission set → IAM role → EKS access entry** (no EKS OIDC provider). Tenant scoping through access entry Kubernetes groups, RBAC and Capsule |
| **Workloads** | EKS Pod Identity, per-tenant IAM role | Unchanged |
| **Local development** | Dex with static users | Unchanged (the same Dex, a static connector instead of SAML) |

## Consequences

- One identity system for AWS and the platform's tools; adding a person to a tenant group in Identity Center (or the directory feeding it) grants every matching access.
- No secrets for sign-in: SAML trust is Identity Center's public metadata (sign-in URL, certificate). The certificate must be renewed when Identity Center rotates it ([secrets](../platform/secrets.md)).
- Group IDs make RBAC rules less readable; each rule keeps the group's name in a comment, and IDs are stored next to names.
- CI never talks to Identity Center (its role is denied every Identity Center action by the bootstrap guardrail); group IDs and SAML metadata reach Terraform through SSM Parameter Store.
- Dex is one more component in the management cluster, and its SAML connector has no refresh tokens: sessions end and people sign in again.
- An outage of Identity Center blocks sign-in to the tools and to AWS; running workloads and model endpoints are not affected.
- Diagrams 1, 2 and 5 in [architecture.md](../architecture.md) show Identity Center as the hub, with no external identity provider.
