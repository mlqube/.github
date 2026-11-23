# Layer: addons-mgmt (Argo CD bootstrap)

> Describes the code in [mlqube/infrastructure · `live/platform/addons/mgmt/`](https://github.com/mlqube/infrastructure/tree/main/live/platform/addons/mgmt). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

Installs **Argo CD** in the `mgmt` cluster, gives it read-only access to the [`gitops`](https://github.com/mlqube/gitops) repository, and creates one **root Application** ("app of apps") that points at `clusters/mgmt` in that repository. From then on, Argo CD installs and updates everything else from `gitops` (Karpenter, AWS Load Balancer Controller, ExternalDNS, observability, ...); Terraform does only this first step.

| Part | Setting |
|---|---|
| Argo CD | Helm chart `argo-cd` 10.14.0 (Argo CD v3.6.1), namespace `argocd`; single sign-on through the standalone Dex (OIDC; its bundled Dex is off); notifications off for now |
| GitOps repository | `git@github.com:mlqube/gitops.git`, branch `main`, through a **read-only deploy key** read from SSM Parameter Store `/mlqube/argocd/gitops-deploy-key` |
| Root Application | `root`: applies every manifest under `clusters/mgmt` (automated sync, prune, self-heal). It is in its own Argo CD project, **`bootstrap`**, created by the same Helm release: only the gitops repository, only mgmt's `argocd` namespace, only ApplicationSets, AppProjects and repository Secrets. The add-ons' `platform` project and the locked-down `default` are in gitops ([projects](../gitops/clusters-mgmt.md#argo-cd-projects-what-each-application-may-do)) |
| Cluster access | The API is private, so the workflow job **joins the tailnet** as a temporary `tag:ci` device and reaches the API through the Tailscale router ([ADR-0014](../../adr/0014-ci-access-to-private-clusters.md)) |
| Add-ons' AWS roles ([`app_pod_identity.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/app_pod_identity.tf)) | EKS Pod Identity roles (no keys), **one set per cluster** in `var.clusters` (`mgmt`, `wl-nonprod`): **AWS Load Balancer Controller** (`<cluster>-aws-lbc`, `kube-system/aws-load-balancer-controller`), **ExternalDNS** (`kube-system/external-dns`, private zone only), **Karpenter** (`karpenter/karpenter`, node role `karpenter-node-<cluster>`, spot interruption queue `karpenter-<cluster>`), and **External Secrets** (`external-secrets/external-secrets`, read-only, Secrets Manager secrets `mlqube/platform/*` only). Created before the root Application, so the add-ons have permissions from their first start |
| Hub and spoke ([`argocd_clusters.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/argocd_clusters.tf)) | Argo CD runs only here (the hub) and deploys to every cluster. Terraform gives Argo CD an IAM role (**Pod Identity** for `argocd-application-controller` and `argocd-server`), an **EKS access entry** (cluster-admin) for it in each spoke (`wl-nonprod`), and writes one Argo CD **cluster secret** per cluster: the hub in-cluster, each spoke with its private API endpoint, CA and AWS auth. Labels and annotations on the secrets (`mlqube/addons`, `mlqube/vpc-name`, `mlqube/dns-domain`) feed the gitops ApplicationSets. Argo CD reaches the spoke over the VPC peering. See [architecture view 6](../../architecture.md#6-gitops-hub-and-spoke) |
| Order | After **both** clusters (it installs Argo CD in mgmt and registers wl-nonprod); destroyed before either. `all` includes it. |
| Cost | Argo CD runs on the system nodes; its internal ALB costs about $0.0225/hour plus usage while the platform runs |

## One-time setup (before the first apply)

Three things, done by hand once. None of them puts a secret in Git or in chat.

### 1. Tailnet policy: allow the `tag:ci` tag

Tailscale admin console → **Access controls**, add `tag:ci` next to the router tag:

```json
"tagOwners": {
  "tag:mlqube-router": ["autogroup:admin"],
  "tag:ci":            ["autogroup:admin"]
},
```

If your access rules still allow everything (the default), nothing else is needed. If you restricted them, allow `tag:ci` to reach `10.10.0.0/16` and `10.20.0.0/16`.

### 2. Tailscale trust credential for GitHub Actions (workload identity federation)

The workflow signs in to Tailscale with GitHub's OIDC token, exactly like it signs in to AWS, so no Tailscale key is stored anywhere.

Tailscale admin console → **Settings → Trust credentials → Credential → OpenID Connect**:

| Field | Value |
|---|---|
| Issuer | GitHub (`https://token.actions.githubusercontent.com`) |
| Subject | `repo:mlqube@<org-id>/infrastructure@<repo-id>:ref:refs/heads/main` (this repository's immutable subject, `main` only, same as the AWS apply role) |
| Scopes | **Auth Keys**: write |
| Tags | `tag:ci` |

It shows a **Client ID** and an **Audience**. Save them as repository secrets of `mlqube/infrastructure`: the Client ID as `TAILSCALE_CLIENT_ID`, the Audience as `TAILSCALE_CLAIM` (each command prompts for the value, so it doesn't land in your shell history):

```bash
gh secret set TAILSCALE_CLIENT_ID --repo mlqube/infrastructure
```

```bash
gh secret set TAILSCALE_CLAIM --repo mlqube/infrastructure
```

### 3. Read-only deploy key for the `gitops` repository

`gitops` is private, so Argo CD needs a key to read it. Create a key pair, give GitHub the public half (read-only), and put the private half in Parameter Store:

```bash
ssh-keygen -t ed25519 -N "" -C argocd-gitops -f argocd-gitops
```

```bash
gh repo deploy-key add argocd-gitops.pub --repo mlqube/gitops --title argocd-mgmt
```

```bash
aws ssm put-parameter --name /mlqube/argocd/gitops-deploy-key --type SecureString --value file://argocd-gitops --profile mlqube --region us-west-2
```

Then delete both local files (`argocd-gitops`, `argocd-gitops.pub`). The key is read-only and only for `gitops`; replace it by adding a new deploy key and overwriting the parameter (`--overwrite`).

## Running it

Actions → **platform** → Run workflow → layer `addons-mgmt` (or `all`), action `plan`, then `apply`.

The job: signs in to AWS (OIDC) → checks the `mgmt` cluster exists → **joins the tailnet** → checks the API answers through the router → `terraform plan` / `apply`. A PR only validates this layer: planning it needs the tailnet and the deploy key, so it runs in `platform` with action `plan`.

## Opening Argo CD

With Tailscale on, open **`https://argocd.mlqube.click`** → **Log in via AWS Identity Center**: your usual AWS sign-in.

### Single sign-on ([`sso.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/sso.tf))

| Part | Setting |
|---|---|
| Identity provider | **AWS IAM Identity Center**, a customer-managed **SAML 2.0** application `Argo CD (MlQube)` (setup: [docs/setup.md step 10b](../setup.md#10b-argo-cd-single-sign-on-iam-identity-center)) |
| Broker | **Dex**, a standalone add-on in mgmt at `https://dex.mlqube.click` (Identity Center has no OIDC for custom apps). Argo CD is its OIDC client `argo-cd`; the client secret is random per build (Secret `argocd/argocd-dex-client`). This layer writes Dex's configuration (Secret `dex/dex-config`) and namespace; Argo CD deploys Dex from gitops ([Dex](../gitops/dex.md)). Callback / SAML audience `https://dex.mlqube.click/callback` |
| SAML metadata | Sign-in URL and certificate from SSM String parameters `/mlqube/argocd/sso-url`, `/mlqube/argocd/sso-ca` (public metadata, not secrets) |
| Who gets in | Only people **assigned** to the application in Identity Center |
| What they may do | `mlqube-platform-admins` → **`role:admin`** (its Identity Center group ID, from SSM `/mlqube/argocd/sso-admin-group-id`: Identity Center sends IDs, not names). Anyone else → **no access** (`policy.default` empty). Tenant groups come in Phase 2 |
| Local `admin` | **Off** (`argocd_admin_enabled = false`): everyone signs in through Identity Center. Break-glass below |

The CLI: `argocd login argocd.mlqube.click --sso --grpc-web` (opens the same login in the browser).

### How the address works (Ingress)

How it gets there: the Argo CD chart creates an **Ingress** (class `alb`, host `argocd.mlqube.click`). Once Argo CD has installed the AWS Load Balancer Controller and ExternalDNS from `gitops` (a few minutes after the apply), the controller creates an **internal ALB** with the `*.mlqube.click` certificate, and ExternalDNS writes the name into the **private** zone. Your laptop resolves it through Tailscale split DNS and reaches the ALB through the router. The flow is drawn in the gitops [load balancer controller README](../gitops/aws-load-balancer-controller.md).

| Ingress setting | Value | Why |
|---|---|---|
| `scheme` | `internal` | Private subnets only (ADR-0010) |
| `target-type` | `ip` | Straight to the pod IPs |
| `listen-ports`, `certificate-arn`, `ssl-policy` | HTTPS 443 only, the `base` layer's certificate, TLS 1.2/1.3 | TLS ends at the ALB; the ALB talks HTTP to Argo CD (`server.insecure`) |
| `inbound-cidrs` | `10.10.0.0/16`, `10.20.0.0/16` | Only the platform VPCs (and Tailscale traffic through the router) |
| `group.name` | `mlqube-mgmt` | Later portals (Grafana, Backstage, MLflow) share this ALB instead of one each |

Fallback while the load balancer isn't ready (or for debugging): `kubectl --context mgmt -n argocd port-forward svc/argocd-server 8080:80`, then `http://localhost:8080` (single sign-on needs the real URL; use the break-glass admin there).

The `argocd` CLI works through the ALB with `--grpc-web`.

### Break-glass: the local admin

Only if single sign-on is broken (Identity Center down, the SAML application changed, the certificate rotated):

1. `platform` → `addons-mgmt` → `apply` with the local admin on: set `argocd_admin_enabled` to `true` in [variables.tf](https://github.com/mlqube/infrastructure/blob/main/live/platform/addons/mgmt/variables.tf) through a PR (or a one-off `TF_VAR_argocd_admin_enabled=true` in the workflow).
2. Copy the initial password to the clipboard (PowerShell; new on every build):

```bash
$p = kubectl --context mgmt -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"; [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p)) | Set-Clipboard
```

3. Log in as `admin`, fix single sign-on, then set `argocd_admin_enabled` back to `false` and apply.

Your `kubectl` access (Identity Center admin role → EKS access entry) doesn't depend on Argo CD's login, so you can always inspect and repair the cluster directly.

## Destroy

`all` → `destroy` removes this layer first, then the clusters. On its own: layer `addons-mgmt`, action `destroy`. Neither cluster (`mgmt`, `wl-nonprod`) can be destroyed while this layer exists.

Add-ons create AWS resources that Terraform doesn't know about, in every cluster Argo CD manages, and left behind they would block destroying the network. So before `terraform destroy`, the job (on the tailnet, which reaches both clusters' private APIs):

1. stops Argo CD's application and ApplicationSet controllers in mgmt, so nothing gets recreated;
2. in **each cluster** (`mgmt`, `wl-nonprod`), deletes Karpenter's NodePools, Ingresses and `LoadBalancer` Services;
3. waits until each cluster's Karpenter has terminated its nodes and each load balancer controller has removed its load balancers;
4. clears the Applications' finalizers, so the `argocd` namespace can be deleted.

DNS records left by ExternalDNS don't matter: the network layer deletes the private zone with whatever is in it (`force_destroy`). If the layer doesn't exist, its destroy is skipped.
