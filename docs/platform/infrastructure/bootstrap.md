# Bootstrap

> Describes the code in [mlqube/infrastructure · `bootstrap/`](https://github.com/mlqube/infrastructure/tree/main/bootstrap). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

The bootstrap stack is the **only** part of this repository that is deployed by hand. Everything else (`live/`) is applied by GitHub Actions. CI needs an AWS role before it can run any Terraform, so that role, and the bucket that holds Terraform state, are created once from the AWS console with [`cloudformation/bootstrap.yaml`](https://github.com/mlqube/infrastructure/blob/main/bootstrap/cloudformation/bootstrap.yaml).

## What it creates

| Resource | Name | Purpose |
|---|---|---|
| IAM OIDC provider | `token.actions.githubusercontent.com` | Lets GitHub Actions sign in to AWS with short-lived tokens; no stored keys |
| S3 bucket | `mlqube-tfstate-<account-id>-us-west-2` | Terraform state: versioned, encrypted, private, HTTPS only. Locking uses lock files in the bucket (`use_lockfile = true`), so no DynamoDB table is needed. Kept even if the stack is deleted. |
| IAM role | `mlqube-gha-plan` | `terraform plan` on pull requests and branches: read-only access to AWS, read/write on the state bucket |
| IAM role | `mlqube-gha-apply` | `terraform apply` / `destroy`, **only from the `main` branch**. Broad permissions, with guardrails: it can't change the bootstrap roles, the OIDC provider, the state bucket's protection or this stack, can't create IAM users or access keys, and can't change Organizations, Identity Center, account or billing settings. |

Cost: a few cents a month (S3 storage and requests). The roles and the OIDC provider are free.

## Deploy it (once, from the console)

1. Sign in through the AWS access portal → account → **AdministratorAccess** → **Management console**, region **US West (Oregon) us-west-2**.
2. **Check for an existing GitHub OIDC provider:** **IAM → Identity providers**. If `token.actions.githubusercontent.com` is already listed, note its ARN. An account can have only one provider per URL.
3. Open **CloudFormation → Stacks → Create stack → With new resources (standard)**.
4. **Prepare template:** *Choose an existing template* → **Upload a template file** → choose `bootstrap/cloudformation/bootstrap.yaml` → **Next**.
5. **Stack name:** `mlqube-bootstrap` (the apply role's guardrails refer to this name).
6. **Parameters:** keep `GitHubOrg = mlqube` and `InfrastructureRepo = infrastructure`.
   - No existing provider: keep `CreateOidcProvider = true`, leave `ExistingOidcProviderArn` empty.
   - Existing provider: set `CreateOidcProvider = false` and paste its ARN into `ExistingOidcProviderArn`.
7. **Next** → keep the defaults on *Configure stack options* → **Next**.
8. Review, tick **"I acknowledge that AWS CloudFormation might create IAM resources with custom names"**, then **Submit**.
9. Wait for **CREATE_COMPLETE** (about a minute), then open the **Outputs** tab and note `TerraformStateBucket`, `PlanRoleArn` and `ApplyRoleArn`. The workflows use these values.

## Change it later

Edit `bootstrap.yaml`, open a pull request, merge it, then in the console: **CloudFormation → mlqube-bootstrap → Update → Replace current template** → upload the new file. GitHub Actions can't update this stack; that is deliberate.

## Remove it

Delete the stack from the console. The state bucket is **retained** (so state is never lost by accident); delete it by hand only after the platform and base layers have been destroyed.
