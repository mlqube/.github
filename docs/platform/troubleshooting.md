# Troubleshooting

> About the platform built from [mlqube/infrastructure](https://github.com/mlqube/infrastructure). Docs for all repositories live here, in `mlqube/.github` ([index](README.md)).

Problems met while building and running the platform, with the symptom you see, the cause and the fix. Newest lessons first within each section. Add to it whenever something new breaks.

- [Platform runs (GitHub Actions)](#platform-runs-github-actions)
- [Tailscale, private access and the router](#tailscale-private-access-and-the-router)
- [Argo CD and the gitops repository](#argo-cd-and-the-gitops-repository)
- [Destroy](#destroy)
- [Laptop: AWS CLI, kubectl, Git Bash, local checks](#laptop-aws-cli-kubectl-git-bash-local-checks)

Most useful first look: the failed job's log (`gh run view <run-id> --log-failed --repo mlqube/infrastructure`), then [`make cost-check`](https://github.com/mlqube/infrastructure/blob/main/Makefile) to see what exists in AWS.

## Platform runs (GitHub Actions)

### The `clusters` job takes 0 s and nothing is created for EKS

- **Cause:** the run was started with **layer `network`**, the dropdown's default. Only `all`, `mgmt` or `wl-nonprod` select clusters; the job is skipped by design.
- **Fix:** run again with layer **`all`** (or the cluster). The *select layers* job log shows what was chosen (`LAYER: …`).

### PR plan fails: `Error acquiring the state lock` (`PreconditionFailed`)

- **Cause:** a `platform` run is applying or destroying that layer at the same moment; Terraform allows one operation per state at a time. The log's *Lock Info* shows `OperationTypeApply` and the time.
- **Fix:** wait for the platform run to finish, then re-run the failed check (`gh run rerun <run-id> --failed --repo mlqube/infrastructure`). Never force-unlock while a run is active.

### PR plan of a cluster layer fails: `data.terraform_remote_state.network.outputs is object with no attributes`

- **Cause:** the network was destroyed; its state file still exists but is empty. Fixed: the check now counts resources and **skips** cluster plans when the network has none. If you see it again, the dependency check in `terraform-plan.yml` regressed.

### Every PR plan wants to replace `aws_eks_access_entry.this["cluster_creator"]`

- **Cause (fixed in PR #8):** "cluster creator" admin access meant *whoever runs Terraform*: the apply role created the cluster, the plan role planned it. The apply role is now named explicitly ([modules/eks-cluster](https://github.com/mlqube/infrastructure/blob/main/modules/eks-cluster/main.tf)).

### `addons-mgmt` is only validated in PRs, never planned

- **By design:** planning it needs the tailnet and the deploy key. Run `platform` → layer `addons-mgmt` → action **`plan`** to see its plan.

### A cluster or network apply fails: `The network layer isn't applied yet` / `The mgmt cluster isn't applied yet`

- **Cause:** layer order check. Apply in order: `network` → clusters → `addons-mgmt` (or use `all`).

## Tailscale, private access and the router

### `addons-mgmt` fails: *Can't reach the mgmt API through the tailnet*

The runner joined the tailnet, but nothing answers at the private API. Almost always the **router isn't on the tailnet**.

1. Tailscale admin console → Machines (or `tailscale status` on the laptop): is **`mlqube-router`** listed and online?
2. If not, read its boot log (read-only):

```bash
aws ec2 describe-instances --filters "Name=tag:Name,Values=mlqube-router" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text --profile mlqube --region us-west-2
```

```bash
aws ec2 get-console-output --instance-id <id> --latest --output text --query Output --profile mlqube --region us-west-2
```

| Boot log shows | Cause | Fix |
|---|---|---|
| `curl: (28) Failed to connect to tailscale.com` | No internet yet: the router booted before the NAT route worked (fixed in PR #11: waits up to 10 min, created after the VPC) | If it still happens: check the NAT gateway and the private route tables |
| `oom-kill … task=dnf` | Out of memory on a 512 MB instance (fixed: `t4g.micro`) | Keep at least 1 GB |
| `could not read /mlqube/tailscale/router-authkey` | Parameter missing, renamed, or not readable | Create it ([setup step 8](setup.md#8-router-auth-key)) |
| `tailscale up` error: invalid / expired key | The auth key expired (90 days) or isn't reusable | [Rotate the key](secrets.md#rotate-the-router-auth-key), then rebuild the network |
| Router joined, but routes not approved | Policy lacks `autoApprovers` for `tag:mlqube-router`, or the key isn't tagged | Fix the tailnet policy ([setup step 7](setup.md#7-tailscale-tailnet)) |

After fixing the cause, recreate the router: `platform` → `network` → `apply` replaces it when its boot script changed; otherwise destroy and rebuild the network.

### `Join the tailnet` fails with `invalid boolean flag accept-routes: flag provided multiple times`

- **Cause (fixed in PR #10):** `tailscale/github-action@v4` already passes `--accept-routes`; adding it in `args` breaks `tailscale up`. Don't add it back.

### `Join the tailnet` fails to authenticate

- Check the trust credential's **subject** is exactly `repo:mlqube@<org-id>/infrastructure@<repo-id>:ref:refs/heads/main`, the run is on `main`, `TAILSCALE_CLIENT_ID` holds the Client ID and `TAILSCALE_CLAIM` the **Audience**, and `tag:ci` is in `tagOwners` ([setup step 9](setup.md#9-ci-access-to-the-tailnet)).

### `kubectl`: `dial tcp 10.x.x.x:443: i/o timeout`

- Tailscale is off on the laptop, or the router isn't joined (see above). Check `tailscale status` and `ping 10.10.0.2`.

### `kubectl`: `the server has asked for the client to provide credentials`

- Your AWS SSO session expired: `aws sso login --profile mlqube`. After a rebuild, also re-run `aws eks update-kubeconfig` (the API endpoint changes).

### A `*.mlqube.click` name doesn't resolve

- Split DNS missing (`tailscale dns status` must show `mlqube.click → 10.10.0.2`), the router isn't joined, or ExternalDNS hasn't written the record yet (`kubectl --context mgmt -n kube-system logs deploy/external-dns`).

## Argo CD and the gitops repository

### `gh repo deploy-key add` fails: `Deploy keys are disabled for this repository`

- **Cause:** an **organization** setting, not the key. **Fix:** GitHub → organization **Settings → Member privileges → Deploy keys** → allow, then run the command again.

### Single sign-on (Identity Center) fails

| Symptom | Cause | Fix |
|---|---|---|
| No **Log in via AWS Identity Center** button | Dex not configured: the SSO parameters were missing at apply time, or Dex isn't running | `kubectl --context mgmt -n argocd get pods` (an `argocd-dex-server` pod); check `/mlqube/argocd/sso-url` and `/mlqube/argocd/sso-ca` exist; apply `addons-mgmt` |
| Identity Center says **No access** although you're assigned (directly or through your group) | The application has **no attribute mappings** (or `Subject` doesn't match what Dex asks for): Identity Center can't build the SAML response | Add the three mappings from [setup step 10b](setup.md#10b-argo-cd-single-sign-on-iam-identity-center): `Subject` → `${user:subject}` (persistent), `email` → `${user:email}`, `groups` → `${user:groups}`; then retry in a private window |
| Identity Center says *you don't have access to this application* | You (or your group) aren't assigned to the `Argo CD (MlQube)` application | Identity Center → Applications → the app → **Assign users and groups** |
| Back in Argo CD with *failed to authenticate* / *Invalid NameIDFormat* / *audience* errors | The application's ACS URL / audience isn't exactly `https://argocd.mlqube.click/api/dex/callback`, or `Subject` isn't `${user:subject}` with format `persistent` | Fix the application settings ([setup step 10b](setup.md#10b-argo-cd-single-sign-on-iam-identity-center)); `kubectl --context mgmt -n argocd logs deploy/argocd-dex-server --tail=50` shows the exact reason |
| Logged in, but you see **no applications** | Your groups didn't arrive, or aren't mapped: the `groups` attribute mapping (`${user:groups}`) is missing, or you're not in `mlqube-platform-admins` | Fix the attribute mapping; check your group in Identity Center. Argo CD → **User info** shows the groups it received |
| *certificate signed by unknown authority* in the Dex log | The certificate in `/mlqube/argocd/sso-ca` doesn't match the application's (rotated) | Download it again, overwrite the parameter (`--overwrite`), apply `addons-mgmt` |

### Argo CD login says *Invalid username or password* (break-glass admin)

- The local `admin` is **disabled** by default: log in with **AWS Identity Center**. The admin only works after a [break-glass](infrastructure/addons-mgmt.md#break-glass-the-local-admin) apply with `argocd_admin_enabled = true`.
- The secret stores the password **base64-encoded**; pasting the raw value fails. Copy the decoded password straight to the clipboard (PowerShell), then paste it:

```bash
$p = kubectl --context mgmt -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"; [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p)) | Set-Clipboard
```

- Through the ALB use `https://argocd.mlqube.click`; with the port-forward fallback use `http://localhost:8080` (not `https`). After about 5 failed attempts Argo CD slows logins for a few minutes. The password is new on every build.

### `https://argocd.mlqube.click` doesn't open

Check each link of the chain, in order:

| Check | Command | Expected / if not |
|---|---|---|
| Add-ons running | `kubectl --context mgmt -n argocd get applications` | `aws-load-balancer-controller` and `external-dns` **Healthy**. Right after an apply, wait a few minutes |
| Ingress has an address | `kubectl --context mgmt -n argocd get ingress argocd-server` | `ADDRESS` = `internal-k8s-mlqubemgmt-….elb.amazonaws.com`. Empty: `kubectl --context mgmt -n kube-system logs deploy/aws-load-balancer-controller --tail=50` (permissions, subnets, certificate) |
| Name resolves | `nslookup argocd.mlqube.click` | A `10.10.x.x` address. If not: split DNS, the router, or `kubectl --context mgmt -n kube-system logs deploy/external-dns --tail=50` |
| ALB answers | `curl -sv https://argocd.mlqube.click/healthz` | `200`. Timeout: Tailscale off, or the ALB's `inbound-cidrs`; `502/503`: target group unhealthy (the pods or `/healthz`) |

Meanwhile the port-forward still works: `kubectl --context mgmt -n argocd port-forward svc/argocd-server 8080:80`.

### The `root` Application shows *repository not accessible* / *authentication required*

- Deploy key missing on GitHub, or the SSM parameter holds a different key. Compare `gh repo deploy-key list --repo mlqube/gitops` with the key you stored; [rotate](secrets.md#rotate-the-gitops-deploy-key) if unsure.

### The `wl-nonprod-…` Applications show *Unknown* / the cluster shows *Failed* in Argo CD

Argo CD in mgmt can't reach or sign in to wl-nonprod. Check the UI under **Settings → Clusters** (`wl-nonprod`, connection status), then:

| Error | Cause | Fix |
|---|---|---|
| `dial tcp 10.20.x.x:443: i/o timeout` | Network: the VPC peering routes, or wl-nonprod's API security group doesn't allow 443 from `10.10.0.0/16` | Check the network layer's peering routes and `private_api_allowed_cidrs` in the cluster module |
| `Unauthorized` / `the server has asked for the client to provide credentials` | Argo CD's IAM role has no access entry in wl-nonprod, or its pods started before their Pod Identity association existed | `aws eks list-access-entries --cluster-name wl-nonprod`; restart `argocd-application-controller` and `argocd-server` |
| `no such host` / an old endpoint | The cluster secret holds the endpoint of a previous build | `platform` → `addons-mgmt` → `apply` rewrites it |

### `<cluster>-karpenter-nodepools` shows *SyncFailed* right after a build

- Expected for a minute or two: it needs Karpenter's CRDs, which `<cluster>-karpenter` installs first. It retries on its own (up to 20 times). If it stays failed, look at `<cluster>-karpenter` first.

## Destroy

### `network` destroy fails: a VPC, subnet or security group `has dependencies` / `DependencyViolation`

- **Cause:** AWS resources created by add-ons, not by Terraform: Karpenter nodes, or load balancers from the AWS Load Balancer Controller (and their security groups / network interfaces).
- **Prevention:** destroy with layer **`all`**, so `addons-mgmt` runs its cleanup step first (deletes NodePools and Ingresses, waits for nodes and load balancers to go).
- **Fix by hand if needed:** `make cost-check`, then delete leftover instances / load balancers tagged with the cluster (EC2 and EC2 → Load Balancers consoles), and re-run the destroy.

### `mgmt` destroy refused: `The addons-mgmt layer still exists`

- Destroy `addons-mgmt` first (or use `all`).

## Laptop: AWS CLI, kubectl, Git Bash, local checks

### `Error when retrieving token from sso: Token has expired and refresh failed`

- `aws sso login --profile mlqube`.

### A command with a path like `/aws-reserved/…` or `/mlqube/…` gets mangled in Git Bash

- Git Bash rewrites arguments that look like Unix paths into Windows paths. Prefix the command with `MSYS_NO_PATHCONV=1`, or run it in PowerShell.

### Local `terraform validate` (pre-commit) fails with `Module not installed`

- Run `terraform init -backend=false` in that layer folder once (the hook's own retry needs `jq`).

### CI fails on a provider with *the lock file has no checksum for this platform*

- Lock all platforms when adding or upgrading a provider, in the layer folder:

```bash
terraform providers lock -platform=linux_amd64 -platform=windows_amd64 -platform=darwin_arm64 -platform=darwin_amd64
```

### `check for added large files` fails on a diagram PNG

- The limit is 500 KB. Lower the `dpi` in the diagram script's graph settings and render again.

### actionlint (CI) reports `SC2129`

- Several `echo … >> "$GITHUB_OUTPUT"` lines: group them in `{ …; } >> "$GITHUB_OUTPUT"`.

### Bash heredocs turn `\n` into real line breaks in generated Python

- Use a file editor (or write the script to a file) instead of `cat <<EOF` for code that contains `\n` escapes.
