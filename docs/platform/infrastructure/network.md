# Network layer

> Describes the code in [mlqube/infrastructure · `live/platform/network/`](https://github.com/mlqube/infrastructure/tree/main/live/platform/network). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

> Terraform root for the platform network: [`main.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/network/main.tf), [`variables.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/network/variables.tf), [`outputs.tf`](https://github.com/mlqube/infrastructure/blob/main/live/platform/network/outputs.tf); the reusable VPC module is in [`modules/network`](https://github.com/mlqube/infrastructure/tree/main/modules/network). Back to the [repository README](README.md).

The `network` layer creates one VPC per environment in **us-west-2**, each spread over two availability zones (AZ a and AZ b are the first two available zones in the account). Everything that runs MlQube lives in **private subnets**; the **public subnets only hold the NAT gateway**. The two VPCs are joined by **VPC peering**.

```mermaid
flowchart LR
    internet((Internet))
    laptop["Operator laptop<br/>(Tailscale)"]

    subgraph region["AWS us-west-2"]
        direction LR

        subgraph mgmt["VPC mlqube-mgmt · 10.10.0.0/16"]
            direction TB
            igw1["Internet gateway"]
            subgraph mgmt_pub["Public subnets (NAT only)"]
                direction LR
                mpa["AZ a · 10.10.200.0/24<br/>NAT gateway + Elastic IP"]
                mpb["AZ b · 10.10.201.0/24<br/>(empty)"]
            end
            subgraph mgmt_priv["Private subnets"]
                direction LR
                mva["AZ a · 10.10.0.0/18"]
                mvb["AZ b · 10.10.64.0/18"]
            end
            mwork["mgmt EKS cluster: nodes and pods<br/>(Argo CD, Crossplane, Backstage, MLflow, observability)<br/>internal ALB · Tailscale subnet router"]
            s3a["S3 gateway endpoint"]
        end

        subgraph nonprod["VPC mlqube-nonprod · 10.20.0.0/16"]
            direction TB
            igw2["Internet gateway"]
            subgraph np_pub["Public subnets (NAT only)"]
                direction LR
                npa["AZ a · 10.20.200.0/24<br/>NAT gateway + Elastic IP"]
                npb["AZ b · 10.20.201.0/24<br/>(empty)"]
            end
            subgraph np_priv["Private subnets"]
                direction LR
                nva["AZ a · 10.20.0.0/18"]
                nvb["AZ b · 10.20.64.0/18"]
            end
            nwork["wl-nonprod EKS cluster: nodes and pods<br/>(tenant namespaces, Argo Workflows, notebooks, staging endpoints)<br/>Karpenter CPU / gVisor / GPU nodes · internal ALB"]
            s3b["S3 gateway endpoint"]
        end
    end

    s3[("Amazon S3")]

    mgmt_priv --- mwork
    np_priv --- nwork
    mgmt_priv -- "0.0.0.0/0" --> mpa --> igw1 --> internet
    np_priv -- "0.0.0.0/0" --> npa --> igw2 --> internet
    mgmt_priv <-- "VPC peering<br/>10.10/16 ⇄ 10.20/16" --> np_priv
    mgmt_priv --> s3a --> s3
    np_priv --> s3b --> s3
    laptop -. "WireGuard tunnel<br/>(no inbound ports)" .-> mwork

    %% ---- colours (see the legend below the diagram)
    classDef public   fill:#FFF3E0,stroke:#E65100,stroke-width:2px,color:#4E2600
    classDef private  fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D2A4A
    classDef workload fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#123B16
    classDef gateway  fill:#F3E5F5,stroke:#6A1B9A,stroke-width:2px,color:#3A0E50
    classDef storage  fill:#E0F2F1,stroke:#00695C,stroke-width:2px,color:#003D33
    classDef external fill:#ECEFF1,stroke:#455A64,stroke-width:2px,color:#1C2A31

    class mpa,mpb,npa,npb public
    class mva,mvb,nva,nvb private
    class mwork,nwork workload
    class igw1,igw2 gateway
    class s3a,s3b,s3 storage
    class internet,laptop external

    style region   fill:#FAFAFA,stroke:#FF9900,stroke-width:2px,color:#212121
    style mgmt     fill:#F1F8E9,stroke:#43A047,stroke-width:2px,color:#1B3D1E
    style nonprod  fill:#FFF8E1,stroke:#FB8C00,stroke-width:2px,color:#4E2600
    style mgmt_pub fill:#FFFBF5,stroke:#E65100,stroke-dasharray:5 3,color:#4E2600
    style np_pub   fill:#FFFBF5,stroke:#E65100,stroke-dasharray:5 3,color:#4E2600
    style mgmt_priv fill:#F5FAFF,stroke:#1565C0,stroke-dasharray:5 3,color:#0D2A4A
    style np_priv   fill:#F5FAFF,stroke:#1565C0,stroke-dasharray:5 3,color:#0D2A4A

    %% links, in the order they are declared above:
    %% 0-1 subnets to workloads, 2-7 outbound internet, 8 peering, 9-12 S3, 13 Tailscale
    linkStyle 0,1 stroke:#2E7D32,stroke-width:1.5px
    linkStyle 2,3,4,5,6,7 stroke:#E65100,stroke-width:2px
    linkStyle 8 stroke:#6A1B9A,stroke-width:3px
    linkStyle 9,10,11,12 stroke:#00695C,stroke-width:2px
    linkStyle 13 stroke:#00838F,stroke-width:2px,stroke-dasharray:6 4
```

**Legend**

| Colour | Meaning |
|---|---|
| 🟧 Amber | Public subnets and the NAT gateway: the only part that reaches the internet; amber arrows are the outbound path |
| 🟦 Blue | Private subnets |
| 🟩 Green | EKS workloads: clusters, nodes and pods |
| 🟪 Purple | Internet gateways; the thick purple arrow is the VPC peering between mgmt and nonprod |
| Teal | S3 gateway endpoints and Amazon S3; the dashed teal arrow is the operator's Tailscale tunnel |
| ⬜ Grey | Outside AWS: the internet and the operator's laptop |

The VPC boxes use the same colours as the [MlQube architecture diagrams](../../architecture.md#enterprise-view): green for the management VPC, orange for non-prod.

## Address plan

Each `/16` is split into four `/18` quarters. Two quarters are the private subnets; the public `/24`s sit in the fourth quarter; the rest is kept free.

| VPC | Private, AZ a | Private, AZ b | Public, AZ a | Public, AZ b | Free for later |
|---|---|---|---|---|---|
| `mlqube-mgmt` | `10.10.0.0/18` | `10.10.64.0/18` | `10.10.200.0/24` | `10.10.201.0/24` | `10.10.128.0/18`, rest of `10.10.192.0/18` |
| `mlqube-nonprod` | `10.20.0.0/18` | `10.20.64.0/18` | `10.20.200.0/24` | `10.20.201.0/24` | `10.20.128.0/18`, rest of `10.20.192.0/18` |
| `mlqube-prod` (Phase 5) | reserved: `10.30.0.0/16` | | | | |

Each private subnet has about 16,000 addresses, because EKS gives every pod its own VPC IP address. The ranges don't overlap the operator's home network (`192.168.1.0/24`), WSL (`192.168.224.0/20`), Docker and kind (`172.16.0.0/12`) or Tailscale (`100.64.0.0/10`).

## What goes where

| Part of the network | Holds | Must not hold |
|---|---|---|
| **Public subnets** | The NAT gateway and its Elastic IP (one per VPC, in AZ a), attached to the internet gateway | Nodes, pods, databases, load balancers: nothing else (ingress is internal only, [ADR-0010](../../adr/0010-ingress.md)) |
| **Private subnets, `mlqube-mgmt`** | The management EKS cluster: its control-plane network interfaces, system node group and Karpenter nodes; platform pods (Argo CD, Crossplane, Backstage, MLflow, Prometheus, Grafana, Loki, OpenCost); the internal ALB for the portals; the Tailscale subnet router ([ADR-0011](../../adr/0011-private-access-reference-build.md)); later the RDS PostgreSQL for MLflow (Phase 4) | Tenant workloads ([ADR-0003](../../adr/0003-cluster-topology.md)) |
| **Private subnets, `mlqube-nonprod`** | The non-prod workload EKS cluster: Karpenter NodePools (CPU, gVisor CPU, GPU per tenant), tenant namespaces, Argo Workflows, notebooks, staging model endpoints, and its internal ALB | Platform control-plane services |
| **VPC peering** | Private traffic between the two VPCs: Argo CD and Crossplane managing the workload cluster, metrics and logs sent to central observability, operator access to the non-prod portals through the Tailscale router | Internet traffic (peering is not transitive: nonprod can't use mgmt's NAT gateway) |
| **S3 gateway endpoint** | Free path to S3 for container image layers (ECR), Terraform state and model artifacts, keeping that traffic off the NAT gateway | — |
| **Private hosted zone `mlqube.click`** | Attached to both VPCs; answers only from inside them (and from the operator's laptop through Tailscale split DNS). Holds the real names, e.g. `argocd.mlqube.click` → mgmt internal ALB, written by ExternalDNS. Same name as the public zone (split-horizon), which only holds certificate validation records ([base layer](base.md)) | Public names: nothing here is visible from the internet |
| **Interface endpoints** (off) | Optional private paths to ECR, STS and Secrets Manager; `enable_interface_endpoints = true` turns them on (about $0.08/hour per VPC) | — |

## Routing

| Route table | Destination | Target |
|---|---|---|
| Private (one per VPC, shared by both AZs) | `0.0.0.0/0` | NAT gateway in AZ a |
| | The other VPC's CIDR (`10.20.0.0/16` or `10.10.0.0/16`) | VPC peering connection |
| | S3 prefix list | S3 gateway endpoint |
| | Own VPC CIDR | local |
| Public (one per VPC) | `0.0.0.0/0` | Internet gateway |

A single NAT gateway per VPC keeps the reference build cheap. The trade-off: if AZ a has an outage, the private subnets lose outbound internet access until it recovers. A production setup would use one NAT gateway per AZ.

## Tailscale access (operator's laptop)

This layer also creates the **Tailscale subnet router** ([module](module-tailscale-router.md), [ADR-0011](../../adr/0011-private-access-reference-build.md)) in a private subnet of the mgmt VPC. It advertises `10.10.0.0/16` and `10.20.0.0/16` to the tailnet, so the operator's laptop reaches the private EKS API endpoints (and, later, the portals) through an encrypted tunnel. The clusters allow HTTPS to their private API from both VPC ranges for this. Turn it off with `enable_tailscale_router = false`.

### One-time setup (Tailscale admin console)

1. Tailscale account (free Personal plan); laptop signed in, with **Use Tailscale subnets** on.
2. **Access controls:** `tagOwners` with `tag:mlqube-router`, and `autoApprovers` routes `10.10.0.0/16` and `10.20.0.0/16` for that tag.
3. **DNS → Nameservers:** custom nameserver `10.10.0.2` restricted to `mlqube.click` (split DNS).

### Auth key (before the first network apply, then every 90 days)

1. Tailscale admin console → **Settings → Keys → Generate auth key**: **reusable**, **ephemeral**, **pre-approved**, tag `tag:mlqube-router`, expiry 90 days.
2. AWS console (us-west-2) → **Systems Manager → Parameter Store → Create parameter**:
   - Name: `/mlqube/tailscale/router-authkey`
   - Tier: **Standard** (free) · Type: **SecureString** · KMS key: `alias/aws/ssm` (default)
   - Value: the auth key
3. Never paste the key anywhere else (Git, chat, workflow logs). The router reads it at boot through its IAM role; it never appears in Terraform state.

To rotate: generate a new key, update the parameter's value, then recreate the router (destroy and apply the network, or replace just the instance).

### Check it

After `network` → `apply` (or `all`):

- Tailscale admin console → **Machines**: `mlqube-router`, tagged `tag:mlqube-router`, with subnet routes approved.
- On the laptop: `tailscale status` lists `mlqube-router`; `ping 10.10.0.2` answers.
- After a cluster apply: `aws eks update-kubeconfig --region us-west-2 --name mgmt --profile mlqube`, then `kubectl get nodes`.
