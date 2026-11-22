# base layer: domain certificate (permanent)

> Describes the code in [mlqube/infrastructure · `live/base/`](https://github.com/mlqube/infrastructure/tree/main/live/base). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

> Terraform root: [`main.tf`](https://github.com/mlqube/infrastructure/blob/main/live/base/main.tf), [`variables.tf`](https://github.com/mlqube/infrastructure/blob/main/live/base/variables.tf), [`outputs.tf`](https://github.com/mlqube/infrastructure/blob/main/live/base/outputs.tf). Back to the [repository README](README.md).

Resources that **stay** across every platform create/destroy cycle. Today that is the HTTPS certificate for MlQube's names; later it can hold other always-on resources (e.g. ECR repositories).

| | |
|---|---|
| Domain | `mlqube.click`, registered in Route 53 |
| Public hosted zone | `mlqube.click`, created by the registration. Terraform only **reads** it, so it can never delete it |
| Certificate | ACM, `*.mlqube.click` and `*.nonprod.mlqube.click`, validated through DNS, renewed automatically by ACM |
| State | `s3://mlqube-tfstate-<account-id>-us-west-2/base/terraform.tfstate` |
| Depends on | nothing (independent of the platform layers; not part of `all`) |
| Cost | Certificate: free. Public hosted zone: $0.50/month (created by the registration, not by this layer). Domain: yearly registration |

## How the DNS fits together (split-horizon)

| Zone `mlqube.click` | Answers | Holds | Created by |
|---|---|---|---|
| **Public** | Anyone on the internet | Only the certificate validation CNAMEs: no platform names are published | Route 53 registration; validation records by **this layer** |
| **Private** | Only inside the VPCs (and the operator's laptop through Tailscale split DNS) | The real names, e.g. `argocd.mlqube.click` → mgmt internal ALB | The [network layer](network.md); records by ExternalDNS (later) |

| Names | Point to | Covered by the certificate as |
|---|---|---|
| `argocd.`, `grafana.`, later `backstage.`, `mlflow.mlqube.click` | Internal ALB of the `mgmt` cluster | `*.mlqube.click` |
| `<app>.nonprod.mlqube.click` (e.g. `workflows.nonprod.mlqube.click`) | Internal ALB of the `wl-nonprod` cluster | `*.nonprod.mlqube.click` |
| `<app>.prod.mlqube.click` (Phase 5) | Internal ALB of the prod cluster | add `*.prod.mlqube.click` to `certificate_names` |

A wildcard covers one level only, which is why each environment sub-domain is a separate name on the certificate.

## What it creates

- `aws_acm_certificate.platform`: one certificate for the names in `certificate_names`
- `aws_route53_record.validation`: the CNAME records ACM checks, in the public zone. They must stay: ACM uses them to renew the certificate before it expires
- `aws_acm_certificate_validation.platform`: waits until ACM has issued the certificate (usually a few minutes)

Output `certificate_arn` is what the internal ALBs will use (through the AWS Load Balancer Controller).

## Run it

1. **Actions → platform → Run workflow:** layer `base`, action `plan` to review, then `apply`. It finishes when the certificate is issued.
2. It stays up. Destroying it (`base` → `destroy`, type `base`) removes the certificate and its validation records, but never the domain or the public zone; the ALBs then can't serve HTTPS until it is applied again.

On pull requests, `terraform-plan` plans this layer like the others.
