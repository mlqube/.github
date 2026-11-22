# MlQube infrastructure

> Describes the code in [mlqube/infrastructure](https://github.com/mlqube/infrastructure). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

Infrastructure as code for [MlQube](https://github.com/mlqube/.github): Terraform for AWS (VPCs, EKS clusters and the AWS resources around them) and the one-time bootstrap stack.

**Everything here is applied by GitHub Actions, never from a laptop.** The only exception is the [bootstrap stack](bootstrap.md), deployed once from the AWS console because CI needs its roles before it can run.

## Documentation

| Doc | Read it when |
|---|---|
| [docs/setup.md](../setup.md) | Setting up from zero: tools, sign-in, bootstrap, domain, certificate, Tailscale, keys, first build (ordered checklist) |
| [docs/secrets.md](../secrets.md) | Looking for a secret or trust relationship: where it lives, who uses it, **when it expires**, how to rotate it, what to do if it leaks |
| [docs/troubleshooting.md](../troubleshooting.md) | Something failed: symptoms, causes and fixes for the problems met so far |

Each layer and module also has its own README (linked in the tables below); architecture decisions are in the [ADRs](../../adr).

## Layout

| Path | What | Applied by |
|---|---|---|
| [`bootstrap/`](bootstrap.md) | CloudFormation: GitHub OIDC provider, CI roles, Terraform state bucket | Once, by hand, from the AWS console |
| `modules/` | Reusable Terraform modules (network, EKS cluster, Tailscale router, platform IAM) | Used by `live/` |
| [`live/base/`](base.md) | Always-on resources: the HTTPS certificate for `mlqube.click` (later ECR) | GitHub Actions, "Run workflow" button (layer `base`) |
| `live/platform/` | Ephemeral platform (VPCs, NAT, EKS clusters): created for a test session and destroyed afterwards | GitHub Actions, "Run workflow" button |
| `.github/workflows/` | Checks, plan, apply, create and destroy workflows | GitHub |

The design decisions behind this repository are recorded in the [MlQube ADRs](../../adr); the work is tracked in the [Phase 1 plan](../../phase-1-plan.md).

## Running the platform (GitHub Actions)

| Workflow | Trigger | What it does |
|---|---|---|
| `pre-commit` | Every push and pull request | Formatting, YAML, secrets, CloudFormation and Terraform checks |
| `terraform-plan` | Pull requests that change `live/` or `modules/` | `terraform plan` for each layer with the read-only `mlqube-gha-plan` role; the result is in the job summary. Add-on layers are only validated here (they need the tailnet): plan them with `platform`, action `plan` |
| `platform` | By hand: **Actions → platform → Run workflow** (on `main`) | `plan`, `apply` or `destroy` with the `mlqube-gha-apply` role, for one layer (`network`, `mgmt`, `wl-nonprod`, `addons-mgmt`) or **`all`**: network first, then both clusters in parallel, then `addons-mgmt`; destroy in reverse (`addons-mgmt`, then clusters in parallel, then network). `destroy` requires typing the layer name (or `all`) in *confirm* |
| `terraform-layer` | Called by `platform` only | The Terraform steps for one layer (order check, init, plan / apply / destroy) |

Layers so far:

| Layer | Path | Creates | Cost while it exists |
|---|---|---|---|
| `base` | [`live/base`](base.md) | **Permanent.** ACM certificate for `*.mlqube.click` and `*.nonprod.mlqube.click`, validated through the public zone `mlqube.click` (split-horizon DNS) | Free (the public zone, $0.50/month, comes with the domain) |
| `network` | [`live/platform/network`](network.md) | VPCs `mlqube-mgmt` (10.10.0.0/16) and `mlqube-nonprod` (10.20.0.0/16), two private and two public subnets each across two AZs, one NAT gateway per VPC, a free S3 gateway endpoint, VPC peering between them, the private hosted zone `mlqube.click` attached to both, and the Tailscale subnet router (operator access, ADR-0011) | About $0.09/hour (two NAT gateways) plus data processed; router ~$0.008/hour; private zone free if deleted within 12 hours, otherwise $0.50/month |
| `mgmt` | [`live/platform/eks/mgmt`](eks-mgmt.md) | The management EKS cluster `mgmt` (Kubernetes 1.36) in the mgmt VPC: private API endpoint, a 2-node spot system node group, add-ons VPC CNI (prefix delegation, network policy), CoreDNS, kube-proxy, Pod Identity agent, EBS CSI driver | About $0.16/hour |
| `wl-nonprod` | [`live/platform/eks/wl-nonprod`](eks-wl-nonprod.md) | The non-prod workload EKS cluster `wl-nonprod` in the nonprod VPC, built the same way (shared [`eks-cluster` module](module-eks-cluster.md)) | About $0.16/hour, plus GPU nodes while they run |
| `addons-mgmt` | [`live/platform/addons/mgmt`](addons-mgmt.md) | **Argo CD** in `mgmt` (the hub), registered to deploy to `mgmt` and `wl-nonprod`, the add-ons' AWS roles for both clusters, its read-only access to the `gitops` repository, and the root Application that installs everything else from `gitops`; Argo CD at `https://argocd.mlqube.click` (internal ALB). The job reaches the private API through Tailscale ([ADR-0014](../../adr/0014-ci-access-to-private-clusters.md)) | About $0.0225/hour for Argo CD's internal ALB (shared later by other portals) |

Each layer has its own state, plan and apply. A typical test session:

- **Everything at once:** run `platform` with layer **`all`** and action `apply` (network, then `mgmt` and `wl-nonprod` in parallel, then Argo CD, about 25–30 minutes); work; then layer `all`, action `destroy`, type `all` to confirm (Argo CD, then clusters in parallel, then network).
- **Layer by layer:** `apply` **network**; then `apply` **mgmt** and/or **wl-nonprod** (they don't depend on each other); then **addons-mgmt** (needs mgmt); work; then `destroy` **addons-mgmt**, the clusters, then **network**.

Then check with `make cost-check`. Each layer refuses to apply before the layer it builds on exists (cluster → network, `addons-mgmt` → `mgmt`), or to destroy a layer while one built on it still exists.

## Network

Two VPCs in us-west-2 (`mlqube-mgmt` 10.10.0.0/16 and `mlqube-nonprod` 10.20.0.0/16), private subnets for everything, NAT gateways in small public subnets, and VPC peering between them. The diagram, address plan, what goes in each subnet and the routing are in the [network layer README](network.md).

## Local helper targets (Makefile)

A [`Makefile`](https://github.com/mlqube/infrastructure/blob/main/Makefile) wraps the few things done by hand: checking for leftover costs, and managing the bootstrap stack. It does **not** create or destroy the platform; that is done by GitHub Actions.

### Prerequisites

- **bash and GNU Make:** use **Git Bash** or **WSL**. Plain PowerShell or `cmd` may not find `bash`, which the targets need.
- **AWS CLI v2**, with the `mlqube` profile (IAM Identity Center, `AdministratorAccess`).
- An active AWS sign-in. Sessions expire after a few hours; sign in again with:

  ```bash
  aws sso login --profile mlqube
  ```

### Run it

From the repository root (`cd` into your clone of `mlqube/infrastructure`):

```bash
make help              # list the targets
make whoami            # check which AWS identity will be used
make cost-check        # anything billable still running? (read-only)
make bootstrap-status  # the bootstrap stack and the state bucket (read-only)
```

Every target first checks that you are signed in as the Identity Center admin (`AWSReservedSSO_AdministratorAccess`) and stops otherwise, so it never runs with other credentials by mistake (e.g. old access keys in the `default` profile).

### Targets

| Target | Changes anything? | What it does |
|---|---|---|
| `make help` | No | Lists the targets |
| `make whoami` | No | Shows the AWS identity in use |
| `make cost-check` | No | Lists billable resources still running in the region: EKS clusters, EC2 instances, NAT gateways, load balancers, unattached Elastic IPs, EBS volumes, interface VPC endpoints, RDS instances, non-default VPCs. Empty sections mean nothing of that kind is left |
| `make bootstrap-status` | No | The bootstrap stack, its resources and the objects in the Terraform state bucket |
| `make bootstrap-deploy` | **Yes** | Creates or updates the bootstrap stack. Reuses the account's GitHub OIDC provider if it exists, otherwise creates one |
| `make bootstrap-destroy` | **Yes** | Deletes the bootstrap stack, then empties (all versions) and deletes the state bucket |

### Options

Override any of these on the command line, e.g. `make cost-check REGION=eu-north-1`:

| Variable | Default | Meaning |
|---|---|---|
| `PROFILE` | `mlqube` | AWS CLI profile |
| `REGION` | `us-west-2` | AWS region |
| `STACK` | `mlqube-bootstrap` | Bootstrap stack name |
| `FORCE` | `0` | `1` lets `bootstrap-destroy` delete the state bucket even if it still holds Terraform state |

### Tearing everything down (zero cost)

Destroy in the reverse order of creation:

1. **Platform layer:** run the *destroy platform* workflow in GitHub Actions.
2. **Base layer:** run the *destroy base* workflow in GitHub Actions.
3. **Check:** `make cost-check` should list nothing.
4. **Bootstrap (only if removing MlQube from the account):**

   ```bash
   make bootstrap-destroy
   ```

   It asks you to type `mlqube-bootstrap` to confirm. It **refuses** while the state bucket still holds Terraform state, because deleting state for live resources would leave them running, unmanaged and still costing money. Use `FORCE=1` only if you are sure those resources are gone. The shared GitHub OIDC provider is not deleted if the stack didn't create it.

For day-to-day use, only step 1 matters: the platform is the expensive part. The bootstrap costs a few cents a month and can stay.

## Checks on every commit

[pre-commit](https://pre-commit.com) validates each commit (formatting, YAML, secrets, CloudFormation, Terraform). The same checks run in CI on every push and pull request, so a skipped local hook is still caught.

```bash
pip install pre-commit
pre-commit install          # once per clone
pre-commit run --all-files  # run every check by hand
```
