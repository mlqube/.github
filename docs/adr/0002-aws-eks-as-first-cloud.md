# ADR-0002: AWS (Amazon EKS) is the first cloud provider

- **Status:** Accepted
- **Date:** 2026-11-17

## Context

MlQube runs on managed Kubernetes in a public cloud. Supporting EKS, GKE and AKS from day one would roughly triple the infrastructure, testing and operations work before we deliver any user value. We need one primary cloud to start with, and we should structure the code so others can be added later.

The team's main expertise is AWS, and many target customers already run their workloads there.

## Options considered

1. **AWS / Amazon EKS.** Deepest team expertise, the largest share of the cloud market, and Karpenter for fast, flexible node provisioning. Drawback: sandboxed runtimes (gVisor/Kata) take more setup than on GKE.
2. **Google Cloud / GKE.** Very smooth GPU support and built-in GKE Sandbox. Less team expertise.
3. **Azure / AKS.** Strong in enterprises that already use Microsoft. Less team expertise.
4. **All three clouds from day one.** Maximum portability, but a much bigger build before any value is delivered.

## Decision

Use **AWS with Amazon EKS** as the first and primary cloud. The main AWS building blocks:

| Need | AWS service / component |
|---|---|
| Kubernetes | Amazon EKS |
| Node autoscaling (CPU, GPU, spot) | Karpenter |
| Workload identity | EKS Pod Identity (IAM role per tenant/workload, no static keys) |
| Artifacts, datasets, model weights | Amazon S3 (bucket per tenant) |
| Container images | Amazon ECR |
| Metadata databases (e.g. MLflow) | Amazon RDS for PostgreSQL |
| Secrets | AWS Secrets Manager via External Secrets |
| Ingress, DNS, certificates | AWS Load Balancer Controller, Route 53, ACM / cert-manager |
| Networking | One VPC per environment, private subnets for nodes |

Infrastructure is written in Terraform. AWS-specific modules are kept separate so another cloud can be added later without rewriting the platform layer.

## Consequences

- We can move fast using existing AWS expertise.
- Karpenter gives flexible GPU provisioning across instance families (e.g. g5/g6 for inference and smaller training, p4d/p5 for large training), with spot instances for interruptible jobs.
- GPU capacity can be scarce. We will need several instance families, spot fallbacks and possibly capacity reservations.
- Sandboxed runtimes need custom node configuration on EKS (see [ADR-0008](0008-workload-sandboxing.md)).
- Adding another cloud later means building equivalents for the AWS-specific infrastructure modules and Crossplane compositions.
