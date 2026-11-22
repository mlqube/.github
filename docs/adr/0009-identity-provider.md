# ADR-0009: Use the corporate identity provider (OIDC) for single sign-on

- **Status:** Accepted, **amended by [ADR-0015](0015-iam-identity-center-identity-hub.md)**: IAM Identity Center is the identity hub (SAML through Dex for the tools, access entries for `kubectl`). The goals below still hold; the mechanism is ADR-0015's.
- **Date:** 2026-11-17

## Context

MlQube needs one sign-in for every tool people use: Backstage, the Argo Workflows UI, MLflow, Grafana, Argo CD (platform admins) and `kubectl` against the EKS clusters. What a person may do depends on the **tenant** (business unit) they belong to and their **role** in it ([ADR-0004](0004-tenancy-model.md)).

MlQube serves a single organization, which already has a corporate identity provider (e.g. Microsoft Entra ID or Okta). That IdP already handles joiners and leavers, MFA and conditional access, and security teams expect access reviews to happen there.

Workloads (pods) also need access to AWS, but that is machine identity, not people's identity. It is handled separately with EKS Pod Identity and a per-tenant IAM role ([ADR-0004](0004-tenancy-model.md), [ADR-0007](0007-mlflow-multi-tenancy.md)).

## Options considered

1. **Self-hosted Keycloak.** Full control over realms, clients and claims, and works offline in local development. But it is another critical, stateful service to run, patch and back up, and it would still have to federate with the corporate IdP. Users and groups would live in two places. *Rejected.*
2. **Amazon Cognito.** Managed by AWS. But it would also have to federate with the corporate IdP, its group and claim handling is limited for this use, and it adds a second user directory. *Rejected.*
3. **The corporate IdP directly, over OIDC.** One source of truth for people and groups; MFA, conditional access and offboarding come for free. MlQube depends on the IdP team to register applications and create groups, and must work within the IdP's token limits.
4. **The corporate IdP behind an in-cluster broker (Dex).** Only one application registration in the IdP, and claims can be normalized in one place. But the broker becomes a critical component for every sign-in. *Kept as a fallback (see Decision).*

## Decision

Use the **organization's corporate identity provider directly, over OIDC**, for all people. MlQube does not run its own user directory.

| Concern | Decision |
|---|---|
| **Applications** | Each tool (Backstage, Argo Workflows server, MLflow, Grafana, Argo CD) is registered as an OIDC client in the corporate IdP. If registering many clients is impractical, put **Dex** in the management cluster as a broker with a single registration (option 4). |
| **Groups** | One group per tenant and role: `mlqube-<tenant>-admins`, `mlqube-<tenant>-developers`, `mlqube-<tenant>-viewers`, plus `mlqube-platform-admins`. The tenant ID follows [ADR-0004](0004-tenancy-model.md), e.g. `mlqube-retail-1042-developers`. |
| **Group claims** | Tokens include only the `mlqube-*` groups (group filtering or app roles in the IdP), to stay under token size limits and avoid leaking unrelated group membership. |
| **Authorization** | Each tool maps groups to roles: Backstage ownership, MLflow permissions per tenant, Grafana teams, Argo Workflows SSO RBAC (group → tenant ServiceAccount), Argo CD RBAC (platform admins). The `Tenant` API ([ADR-0006](0006-platform-apis-with-crossplane.md)) writes these mappings; no one maintains them by hand. |
| **`kubectl`** | Each EKS cluster is associated with the corporate IdP as an **OIDC identity provider**. Kubernetes RBAC and Capsule bind the IdP groups to the tenant's namespaces. IAM-based **EKS access entries** are kept only for platform automation and break-glass access. |
| **Workloads** | Never use the IdP. Pods get temporary AWS credentials through **EKS Pod Identity** and the tenant's IAM role. No static cloud keys anywhere. |
| **Local development** | The kind setup runs **Dex with static test users and groups**, so the same OIDC configuration works without the corporate IdP. |
| **Group lifecycle** | Creating a tenant documents the groups it needs; the IdP team (or later, automation through the IdP's API or SCIM) creates them. MlQube never manages user accounts. |

## Consequences

- One identity for people across all tools, with MFA, conditional access and offboarding handled by the corporate IdP. Access reviews happen in one place.
- No identity service for the platform team to operate, except Dex in local development (and in production only if the fallback is needed).
- MlQube depends on the IdP team for application registrations and new groups. Onboarding a business unit includes an IdP request until it is automated.
- **To check in Phase 1:**
  - Which group identifier the IdP puts in tokens. Microsoft Entra ID, for example, emits group object IDs by default and switches to an overage claim beyond about 200 groups; the mapping must use names or app roles that MlQube can predict.
  - That every tool's OIDC integration supports group-based authorization. MLflow in particular needs an OIDC-capable auth plugin or proxy ([ADR-0007](0007-mlflow-multi-tenancy.md)).
  - That the EKS OIDC identity provider association works with the IdP's issuer and token format.
- An outage of the corporate IdP blocks sign-in to MlQube. Running workloads and model endpoints are not affected, because they don't depend on people signing in.
