# Architecture Decision Records

Each important MlQube architecture decision is recorded as an ADR. To propose a new one, copy [the template](0000-template.md), give it the next number, and open a pull request.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-assemble-open-source-components.md) | Assemble open-source components instead of building a custom control plane | Accepted |
| [0002](0002-aws-eks-as-first-cloud.md) | AWS (Amazon EKS) is the first cloud provider | Accepted |
| [0003](0003-cluster-topology.md) | Cluster topology: a management cluster plus workload clusters | Accepted |
| [0004](0004-tenancy-model.md) | Tenancy model: tiered isolation | Proposed |
| [0005](0005-argo-workflows-with-hera-for-ml-jobs.md) | Argo Workflows with the Hera Python SDK for ML jobs and pipelines | Accepted |
| [0006](0006-platform-apis-with-crossplane.md) | Build the platform APIs with Crossplane | Proposed |
| [0007](0007-mlflow-multi-tenancy.md) | One MLflow instance per tenant | Proposed |
| [0008](0008-workload-sandboxing.md) | Sandboxing and node isolation for untrusted tenant code | Proposed |
