# Module: eks-cluster

> Describes the code in [mlqube/infrastructure · `modules/eks-cluster/`](https://github.com/mlqube/infrastructure/tree/main/modules/eks-cluster). Docs for all repositories live here, in `mlqube/.github` ([index](../README.md)).

One EKS cluster with a small system node group and the core add-ons. Used by the [`mgmt`](eks-mgmt.md) and [`wl-nonprod`](eks-wl-nonprod.md) layers, so both clusters are built the same way. Built on [terraform-aws-modules/eks](https://registry.terraform.io/modules/terraform-aws-modules/eks/aws) (v21) and [terraform-aws-modules/eks-pod-identity](https://registry.terraform.io/modules/terraform-aws-modules/eks-pod-identity/aws) (v2).

## What each cluster gets

| Part | Setting | Why |
|---|---|---|
| Kubernetes version | From the layer (`kubernetes_version`, currently **1.36**) | One release behind the newest (1.37), in standard support until 2027-08. Upgrade before a version leaves standard support: extended support costs about $0.60/hour per cluster instead of $0.10 |
| API endpoint | Private always; public only for the CIDRs in `endpoint_public_access_cidrs` (from the repository variable `EKS_PUBLIC_ACCESS_CIDRS`; unset = private only) | [ADR-0011](../../adr/0011-private-access-reference-build.md): no API open to the internet |
| Access | EKS access entries (no `aws-auth` ConfigMap): cluster-admin for the CI apply role that creates the cluster and for the roles in `admin_principal_arns` (the Identity Center `AdministratorAccess` role) | People and CI use IAM identities; no static kubeconfig credentials |
| System node group | 2 **spot** nodes (`t3.large`, `t3a.large`, `m5.large`, `m6i.large` or `m7i.large`, whichever is available), Amazon Linux 2023, 30 GB disk, label `mlqube/node-role=system`; scales up to 3 | Runs CoreDNS, controllers, Karpenter and (in `mgmt`) Argo CD. Workload nodes come from Karpenter later |
| **VPC CNI** add-on | Prefix delegation and network policy enforcement on | [ADR-0013](../../adr/0013-cni-and-network-policy.md) |
| CoreDNS, kube-proxy | Managed add-ons, latest compatible version | Core cluster services |
| EKS Pod Identity agent | Managed add-on | Gives pods temporary AWS credentials through IAM roles (no keys, [ADR-0009](../../adr/0009-identity-provider.md)) |
| EBS CSI driver | Managed add-on with its own Pod Identity role (`<cluster>-ebs-csi`) | Persistent volumes (Prometheus, Loki and others) |
| Secrets encryption | AWS-owned keys (EKS default) | No customer-managed KMS key, which would cost about $1/month for every create/destroy cycle |
| Control-plane logs | Off (`control_plane_log_types`, e.g. `["audit"]`) | CloudWatch logs are billed per GB |
| Karpenter discovery | Node security group tagged `karpenter.sh/discovery = <cluster>`; private subnets tagged by the network layer | Ready for Karpenter |

## Cost per cluster while it exists

| Item | Per hour |
|---|---|
| EKS control plane (standard support) | $0.10 |
| 2 system nodes (spot, `t3.large`-class) | about $0.05 |
| EBS volumes for the nodes (2 × 30 GB gp3) | under $0.01 |
| **One cluster** | **about $0.16** |

## Open points

- **Argo CD bootstrap (next layer):** installing Argo CD needs access to the Kubernetes API from the workflow. GitHub-hosted runners have changing IP addresses, so they can't reach a public endpoint limited to the operator's IP, nor the private endpoint. Options to decide before that layer: let EKS install Argo CD as a managed capability if available, run the bootstrap from inside the VPC, or allow the runners' address ranges for the duration of the bootstrap.
- **Access entry for the Identity Center role:** the entry uses the role's full ARN as IAM reports it (with the `aws-reserved/sso.amazonaws.com/...` path). The first apply confirms EKS accepts this form.
