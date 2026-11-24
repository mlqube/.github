# Architecture Decision Records

Each important MlQube architecture decision is recorded as an ADR. To propose a new one, copy [the template](0000-template.md), give it the next number, and open a pull request.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-assemble-open-source-components.md) | Assemble open-source components instead of building a custom control plane | Accepted |
| [0002](0002-aws-eks-as-first-cloud.md) | AWS (Amazon EKS) is the first cloud provider | Accepted |
| [0003](0003-cluster-topology.md) | Cluster topology: a management cluster plus workload clusters | Accepted |
| [0004](0004-tenancy-model.md) | Tenancy model: business units as tenants, single tier | Accepted |
| [0005](0005-argo-workflows-with-hera-for-ml-jobs.md) | Argo Workflows with the Hera Python SDK for ML jobs and pipelines | Accepted |
| [0006](0006-platform-apis-with-crossplane.md) | Build the platform APIs with Crossplane | Accepted |
| [0007](0007-mlflow-multi-tenancy.md) | One shared MLflow for all tenants (PostgreSQL + S3) | Accepted |
| [0008](0008-workload-sandboxing.md) | Sandboxing and node isolation for untrusted tenant code | Accepted |
| [0009](0009-identity-provider.md) | Use the corporate identity provider (OIDC) for single sign-on | Accepted |
| [0010](0010-ingress.md) | Private ingress with the AWS Load Balancer Controller (internal ALBs) | Accepted |
| [0011](0011-private-access-reference-build.md) | Private access for the reference build with a Tailscale subnet router | Accepted |
| 0012 | Observability (reserved, not yet written) | — |
| [0013](0013-cni-and-network-policy.md) | AWS VPC CNI with prefix delegation and built-in network policy enforcement | Accepted |
| [0014](0014-ci-access-to-private-clusters.md) | CI reaches the private cluster APIs through Tailscale (Argo CD bootstrap) | Accepted |
| [0015](0015-iam-identity-center-identity-hub.md) | IAM Identity Center as the identity hub (amends 0009) | Accepted |
| [0016](0016-golden-path-v0.md) | Golden path v0: trunk-based ML projects, from a feature branch to a registered model | Accepted |
| [0017](0017-ai-assistance-in-the-platform.md) | AI assistance in the platform: use cases and rules (parked) | Proposed |
