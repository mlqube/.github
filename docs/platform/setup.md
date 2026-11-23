# One-time setup

> About the platform built from [mlqube/infrastructure](https://github.com/mlqube/infrastructure). Docs for all repositories live here, in `mlqube/.github` ([index](README.md)).

Everything that has to exist **before** the first `platform` run, in order. Do it once per AWS account (or when rebuilding from zero); after that, every test session is just *apply → work → destroy* (see the [repository README](infrastructure/README.md#running-the-platform-github-actions)).

Nothing here puts a secret in Git, in a workflow file or in chat: secrets go into SSM Parameter Store or GitHub repository secrets only. What exists, where, and when it expires is listed in [secrets.md](secrets.md). When something fails, see [troubleshooting.md](troubleshooting.md).

| # | Step | Where | Done when |
|---|---|---|---|
| 1 | [Tools on your laptop](#1-tools-on-your-laptop) | Laptop | `aws`, `gh`, `kubectl`, `tailscale` answer |
| 2 | [AWS sign-in (Identity Center)](#2-aws-sign-in-identity-center) | AWS + laptop | `make whoami` prints the AdministratorAccess role |
| 3 | [GitHub organization and repositories](#3-github-organization-and-repositories) | GitHub | Repos exist; deploy keys allowed |
| 4 | [Bootstrap stack](#4-bootstrap-stack) | AWS console | Stack `mlqube-bootstrap` is `CREATE_COMPLETE` |
| 5 | [Domain](#5-domain) | Route 53 | `mlqube.click` registered, public zone exists |
| 6 | [Certificate (`base` layer)](#6-certificate-base-layer) | GitHub Actions | ACM certificate **Issued** |
| 7 | [Tailscale tailnet](#7-tailscale-tailnet) | Tailscale admin console | Policy and split DNS saved |
| 8 | [Router auth key](#8-router-auth-key) | Tailscale + SSM | Parameter `/mlqube/tailscale/router-authkey` exists |
| 9 | [CI access to the tailnet](#9-ci-access-to-the-tailnet) | Tailscale + GitHub | Secrets `TAILSCALE_CLIENT_ID`, `TAILSCALE_CLAIM` exist |
| 10 | [Argo CD deploy key](#10-argo-cd-deploy-key) | Laptop + GitHub + SSM | Deploy key `argocd-mgmt` and parameter `/mlqube/argocd/gitops-deploy-key` exist |
| 10b | [Argo CD single sign-on](#10b-argo-cd-single-sign-on-iam-identity-center) | Identity Center + SSM | SAML application assigned to `mlqube-platform-admins`; parameters `/mlqube/argocd/sso-url`, `/mlqube/argocd/sso-ca` and `/mlqube/argocd/sso-admin-group-id` exist |
| 11 | [First platform build](#11-first-platform-build-and-checks) | GitHub Actions | Argo CD apps Synced and Healthy |

## 1. Tools on your laptop

| Tool | For | Check |
|---|---|---|
| AWS CLI v2 | Sign-in, read-only checks, SSM parameters | `aws --version` |
| GitHub CLI (`gh`), signed in to the `mlqube` organization | PRs, secrets, deploy keys | `gh auth status` |
| Tailscale client, signed in, **Use Tailscale subnets** on | Reaching the private VPCs | `tailscale status` |
| `kubectl` (`winget install Kubernetes.kubectl`) | Looking at the clusters | `kubectl version --client` |
| Git Bash or WSL, and `make` | The [Makefile](https://github.com/mlqube/infrastructure/blob/main/Makefile) helpers | `make help` |
| `pre-commit` (`pip install pre-commit`, then `pre-commit install`) | The same checks CI runs | `pre-commit run --all-files` |
| Optional: Python with `diagrams`, and Graphviz | Regenerating the pictures in `docs/diagrams` | `python -c "import diagrams"` |

Terraform is **not** needed locally to run the platform: GitHub Actions runs it. Install Terraform 1.14 only to validate code before a PR.

## 2. AWS sign-in (Identity Center)

- One AWS account, region **us-west-2**. Sign-in goes through **IAM Identity Center**: permission set **AdministratorAccess**, assigned to the group `mlqube-platform-admins`. No IAM users, no access keys.
- Configure the CLI profile once (start URL and region from the AWS access portal), named **`mlqube`**:

```bash
aws configure sso --profile mlqube
```

- Each day (the session lasts some hours):

```bash
aws sso login --profile mlqube
```

```bash
make whoami
```

It must print a role `AWSReservedSSO_AdministratorAccess_…`.

## 3. GitHub organization and repositories

| Item | Setting |
|---|---|
| Organization | `mlqube` |
| Repositories | `.github` (**public**: docs, ADRs, issues), `infrastructure` and `gitops` (**private**) |
| OIDC subject format | The organization uses GitHub's **immutable** subject (`repo:mlqube@<org-id>/infrastructure@<repo-id>:…`). AWS and Tailscale trust exactly that, so a re-created repository with the same name gets a new ID and is **not** trusted. Check the IDs with `gh api orgs/mlqube -q .id` and `gh api repos/mlqube/infrastructure -q .id` |
| **Deploy keys** | Organization **Settings → Member privileges → Deploy keys**: allow repository admins to create deploy keys. Without it, step 10 fails with *"Deploy keys are disabled for this repository"* |

## 4. Bootstrap stack

The only thing deployed by hand: the GitHub OIDC provider, the Terraform state bucket `mlqube-tfstate-<account-id>-us-west-2`, and the roles `mlqube-gha-plan` / `mlqube-gha-apply`. Steps: [bootstrap/README.md](infrastructure/bootstrap.md). Check:

```bash
make bootstrap-status
```

## 5. Domain

- `mlqube.click` registered in **Route 53** (Domains → Register). Registration creates the **public hosted zone** with 4 name servers; Terraform only reads it.
- Registered until **2027-11-19**, **auto-renew off**: renew it (or turn auto-renew on) before then, or the certificate and all names stop working. See [secrets.md](secrets.md#renewals-calendar).

## 6. Certificate (`base` layer)

Actions → **platform** → Run workflow → layer **`base`**, action `plan`, then `apply`. It creates the ACM certificate for `*.mlqube.click` and `*.nonprod.mlqube.click` and validates it through the public zone. Permanent: not part of `all`, never destroyed at session end. Details: [live/base/README.md](infrastructure/base.md). Check: ACM console (us-west-2) → certificate **Issued**.

## 7. Tailscale tailnet

Free Personal plan. In the Tailscale admin console:

**Access controls** (the policy file): add the two tags and the route auto-approval. With the default "allow all" access rules nothing else is needed.

```json
"tagOwners": {
  "tag:mlqube-router": ["autogroup:admin"],
  "tag:ci":            ["autogroup:admin"]
},
"autoApprovers": {
  "routes": {
    "10.10.0.0/16": ["tag:mlqube-router"],
    "10.20.0.0/16": ["tag:mlqube-router"]
  }
},
```

**DNS → Nameservers → Add nameserver → Custom:** `10.10.0.2`, **Restrict to domain** `mlqube.click` (split DNS: only MlQube names go to the VPC resolver).

Why: [ADR-0011](../adr/0011-private-access-reference-build.md); how it fits together: [tailscale-router README](infrastructure/module-tailscale-router.md).

## 8. Router auth key

1. Tailscale admin console → **Settings → Keys → Generate auth key**: **reusable**, **ephemeral**, **pre-approved**, tags **`tag:mlqube-router`**, expiry **90 days**.
2. Store it in SSM, pasting the key only into the console form: AWS console (us-west-2) → **Systems Manager → Parameter Store → Create parameter**: name `/mlqube/tailscale/router-authkey`, tier **Standard**, type **SecureString**, KMS key `alias/aws/ssm`, value: the key.
3. Note the expiry date in [secrets.md](secrets.md#renewals-calendar): an expired key means the router never joins and nothing private is reachable.

## 9. CI access to the tailnet

Jobs that talk to a private cluster API (today `addons-mgmt`) join the tailnet with GitHub's OIDC token, like they sign in to AWS ([ADR-0014](../adr/0014-ci-access-to-private-clusters.md)).

1. Tailscale admin console → **Settings → Trust credentials → Credential → OpenID Connect**:

| Field | Value |
|---|---|
| Issuer | GitHub (`https://token.actions.githubusercontent.com`) |
| Subject | `repo:mlqube@<org-id>/infrastructure@<repo-id>:ref:refs/heads/main` |
| Scopes | **Auth Keys**: write |
| Tags | `tag:ci` |

2. Save the **Client ID** and the **Audience** it shows as repository secrets of `infrastructure` (each command prompts for the value):

```bash
gh secret set TAILSCALE_CLIENT_ID --repo mlqube/infrastructure
```

```bash
gh secret set TAILSCALE_CLAIM --repo mlqube/infrastructure
```

`TAILSCALE_CLAIM` holds the **Audience**.

## 10. Argo CD deploy key

Argo CD reads the private `gitops` repository with a **read-only deploy key**. In a temporary folder (PowerShell), press Enter twice at the passphrase prompt (Argo CD can't use a passphrase):

```bash
cd $env:TEMP
```

```bash
ssh-keygen -t ed25519 -C argocd-gitops -f argocd-gitops
```

```bash
gh repo deploy-key add argocd-gitops.pub --repo mlqube/gitops --title argocd-mgmt
```

```bash
aws ssm put-parameter --name /mlqube/argocd/gitops-deploy-key --type SecureString --value file://argocd-gitops --profile mlqube --region us-west-2
```

```bash
Remove-Item argocd-gitops, argocd-gitops.pub
```

## 10b. Argo CD single sign-on (IAM Identity Center)

Argo CD (and later every other tool) signs people in through **IAM Identity Center** (SAML), via **Dex**, the standalone identity broker in mgmt ([Dex](gitops/dex.md)). Free; nothing secret to store.

1. IAM Identity Center console (us-west-2) → **Applications → Customer managed → Add application** → *I have an application I want to set up* → **SAML 2.0** → Next.
2. **Display name** `Argo CD (MlQube)`. Under **IAM Identity Center metadata**: copy the **IAM Identity Center sign-in URL**, and **download the IAM Identity Center certificate** (a `.pem` file).
3. **Application properties → Application start URL** (optional): `https://argocd.mlqube.click`.
4. **Application metadata → Manually type your metadata values**:
   - **Application ACS URL:** `https://dex.mlqube.click/callback`
   - **Application SAML audience:** `https://dex.mlqube.click/callback`

   (Before Dex became a standalone add-on, both were `https://argocd.mlqube.click/api/dex/callback`. An existing application only needs these two fields changed: **Actions → Edit configuration**.)
5. **Submit**, then **Actions → Edit attribute mappings**:

| User attribute in the application | Maps to | Format |
|---|---|---|
| `Subject` | `${user:subject}` | `persistent` |
| `email` (add) | `${user:email}` | `unspecified` |
| `groups` (add) | `${user:groups}` | `unspecified` |

6. **Assigned users and groups → Assign** the group **`mlqube-platform-admins`** (only assigned people can sign in at all).
7. Store the two metadata values in SSM Parameter Store as **String** (they're public metadata, not secrets):

```bash
aws ssm put-parameter --name /mlqube/argocd/sso-url --type String --value "<IAM Identity Center sign-in URL>" --profile mlqube --region us-west-2
```

```bash
aws ssm put-parameter --name /mlqube/argocd/sso-ca --type String --value file://<downloaded-certificate>.pem --profile mlqube --region us-west-2
```

8. Store the **ID** of `mlqube-platform-admins` too (Identity Center sends group IDs, not names, and CI's role may not read Identity Center). In Git Bash:

```bash
ids=$(aws sso-admin list-instances --profile mlqube --region us-west-2 --query "Instances[0].IdentityStoreId" --output text) && gid=$(aws identitystore get-group-id --identity-store-id "$ids" --alternate-identifier '{"UniqueAttribute":{"AttributePath":"DisplayName","AttributeValue":"mlqube-platform-admins"}}' --profile mlqube --region us-west-2 --query GroupId --output text) && MSYS_NO_PATHCONV=1 aws ssm put-parameter --name /mlqube/argocd/sso-admin-group-id --type String --value "$gid" --profile mlqube --region us-west-2
```

Terraform maps that group ID to Argo CD's `role:admin`; everyone else gets no access.

## 11. First platform build and checks

Actions → **platform** → Run workflow → layer **`all`** (not the default `network`), action `apply`. About 30 minutes: network → both clusters in parallel → `addons-mgmt` (add-on roles, Argo CD, root Application).

| Check | Command or place | Expected |
|---|---|---|
| Router joined | Tailscale admin console → Machines, or `tailscale status` | `mlqube-router` online, tagged `tag:mlqube-router` |
| VPC reachable | `ping 10.10.0.2` | replies |
| kubeconfig | `aws eks update-kubeconfig --region us-west-2 --name mgmt --alias mgmt --profile mlqube` (same for `wl-nonprod`) | context added |
| Nodes | `kubectl --context mgmt get nodes` | 2 system nodes `Ready` |
| Argo CD | `kubectl --context mgmt -n argocd get applications` | `root` and the add-ons **Synced / Healthy** |
| Argo CD UI | `https://argocd.mlqube.click` (a few minutes after the apply) → **Log in via AWS Identity Center** | your usual AWS sign-in, then admin rights, valid certificate |

At the end of the session: layer **`all`**, action **`destroy`**, type `all` in *confirm*, then `make cost-check`.
