# ADR-0010: Private ingress with the AWS Load Balancer Controller (internal ALBs)

- **Status:** Accepted
- **Date:** 2026-11-17

## Context

MlQube exposes two kinds of HTTP traffic:

- **Platform UIs and APIs** used by people: Backstage, the Argo Workflows server, MLflow, Grafana and Argo CD. These run in the management cluster, except the Argo Workflows server, which runs in each workload cluster.
- **Model endpoints** (KServe) called by business applications, in the non-prod (staging) and prod workload clusters. Promotion uses canary rollouts, which need traffic splitting between model versions.

Everything should be internal: MlQube serves one organization, so it should be reached only over the corporate network / VPN, never from the internet. Nodes already run in private subnets ([ADR-0002](0002-aws-eks-as-first-cloud.md)). We need TLS everywhere, stable DNS names, and as few components to operate as possible. ADR-0002 already lists the AWS Load Balancer Controller, Route 53 and ACM as the AWS building blocks.

## Options considered

1. **AWS Load Balancer Controller only.** Kubernetes `Ingress` objects create **internal ALBs**, with TLS certificates from ACM and records in a Route 53 private hosted zone. Fully managed by AWS, integrates with AWS WAF and security groups, nothing extra to run in the cluster. But it has limited L7 routing, ties routing to AWS, and an ALB per ingress group costs money.
2. **Gateway API with Envoy Gateway** behind an internal Network Load Balancer. Portable and richer routing, including weighted traffic splitting and per-namespace route delegation for tenants. But it is another data-plane component to run, scale and upgrade in every cluster.
3. **Istio** (ingress gateway plus service mesh). The most features, including mTLS between services. By far the heaviest to operate; we don't need a mesh today. *Rejected for now.*

## Decision

Use **option 1 as the edge for all traffic**:

| Concern | Decision |
|---|---|
| **Load balancers** | AWS Load Balancer Controller in every cluster. `Ingress` objects create **internal ALBs** in private subnets; services in one cluster share an ALB through an **IngressGroup**. |
| **TLS** | Certificates from **ACM**, terminated at the ALB. HTTP is redirected to HTTPS. |
| **DNS** | A **Route 53 private hosted zone** per environment, associated with the VPCs and resolvable from the corporate network. **ExternalDNS** creates records from `Ingress` hosts. |
| **Access** | Security groups allow only the corporate network / VPN ranges and the platform VPCs. Sign-in is handled by each tool over OIDC ([ADR-0009](0009-identity-provider.md)), not at the load balancer. |
| **Platform UIs and APIs** | One host name per tool, e.g. `backstage.<env>.mlqube.<corp-domain>`, routed by the shared internal ALB. |
| **Model endpoints** | Reached through the same kind of internal ALB. **Canary traffic splitting happens inside the cluster**, through KServe; the ALB only forwards to the in-cluster serving layer. |
| **cert-manager** | Only where certificates are needed inside the cluster (e.g. admission webhooks), not for the edge. |

**Deferred to Phase 5 (serving):** which in-cluster networking layer KServe uses for canary rollouts, e.g. KServe's serverless mode with Knative, or Gateway API with Envoy Gateway (option 2). That choice will be recorded in its own ADR, based on how well each supports canary traffic splitting, autoscaling (including scale to zero) and per-tenant routing. Either way, the internal ALB stays the edge.

## Consequences

- No ingress data plane to operate for the platform UIs; AWS runs the load balancers. TLS and DNS are automated through ACM and ExternalDNS.
- Matches the AWS-first decision ([ADR-0002](0002-aws-eks-as-first-cloud.md)). Moving to another cloud means replacing the `Ingress` annotations and the load balancer controller.
- One shared internal ALB per cluster keeps cost predictable; very large numbers of model endpoints may need more ALBs or host-based routing limits checked.
- Advanced routing (header-based routing, traffic mirroring, weighted splits) is not done at the ALB. If those become needed beyond model serving, revisit option 2.
- **Follow-up:** an ADR in Phase 5 for the KServe networking layer, and a check that the Route 53 private zone resolves from the corporate network (DNS forwarding through Route 53 Resolver endpoints).
