"""MlQube view 5: the enterprise view, all parts joined together.

Run: python docs/diagrams/mlqube_5_enterprise.py  ->  mlqube_5_enterprise.png / .svg
"""

from __future__ import annotations

from mlqube_style import (
    BLUE, BROWN, GREEN, ORANGE, PURPLE, RED, TEAL,
    box, icon, lane, legend, new_diagram, place_columns, plain, publish, step,
)

from diagrams.aws.compute import EC2ContainerRegistry, EC2Instances, EC2SpotInstance
from diagrams.aws.database import RDSPostgresqlInstance
from diagrams.aws.management import Cloudtrail
from diagrams.aws.network import ElbApplicationLoadBalancer, Route53
from diagrams.aws.security import CertificateManager, IdentityAndAccessManagementIamRole, SecretsManager
from diagrams.aws.storage import SimpleStorageServiceS3Bucket
from diagrams.custom import Custom
from diagrams.generic.network import VPN
from diagrams.k8s.group import NS
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import User, Users
from diagrams.onprem.container import Gvisor
from diagrams.onprem.gitops import Argocd
from diagrams.onprem.iac import Terraform
from diagrams.onprem.logging import Loki
from diagrams.onprem.mlops import Mlflow
from diagrams.onprem.monitoring import Grafana, Prometheus
from diagrams.onprem.vcs import Github
from diagrams.aws.security import SingleSignOn

NAME = "mlqube_5_enterprise"

FLOWS = [
    (1, BLUE, "bold", "Developer submits a Python/Hera job → Argo Workflows → Kueue → Karpenter GPU node"),
    (2, GREEN, "bold", "Job logs runs and registers the model → shared MLflow (metadata → RDS, artifacts → S3 prefix)"),
    (3, PURPLE, "bold", "Model promotion → GitOps PR in GitHub → Argo CD → KServe canary in prod"),
    (4, ORANGE, "bold", "GitOps: Argo CD (management) → both workload clusters"),
    (5, BROWN, "dashed", "Crossplane provisions per-tenant S3 bucket, IAM role, namespaces"),
    (6, TEAL, "dashed", "SSO: IAM Identity Center (SAML, via Dex) → Backstage, Argo Workflows UI, MLflow; groups per tenant"),
    (7, RED, "dotted", "Metrics/cost: all clusters → central observability → OpenCost → per-BU cost report"),
]


def build():
    diagram = new_diagram(
        NAME,
        "MlQube: Enterprise ML Platform on AWS",
        "5 · Full view · hub-and-spoke EKS clusters · one tenant per business unit · "
        "infrastructure as code with Terraform",
    )
    with diagram:
        # 1. people
        with lane("1 · People & business units", "people"):
            with box("Tenant: retail-1042"):
                retail = Users("ML engineers &\ndata scientists")
            with box("Tenant: risk-analytics-2001"):
                risk = Users("ML engineers &\ndata scientists")
            with box("Tenant: marketing-3007"):
                marketing = Users("ML engineers &\ndata scientists")
            platform_team = User("Platform team")
            finops = User("Finance / FinOps")

        # 2. corporate edge
        with lane("2 · Corporate edge & identity", "edge"):
            idp = SingleSignOn("IAM Identity Center\nSSO · groups\nmlqube-<tenant>-admins\n/-developers/-viewers")
            vpn = VPN("Corporate network / VPN\nprivate access to portals\n(internal ALB · Route 53)")
            with box("GitHub org"):
                hera = Custom("Python code\n+ Hera SDK", icon("hera"))
                github = Github("GitHub repos\n(app · GitOps · infra)")
                actions = GithubActions("GitHub Actions\n(build · test)")
                terraform = Terraform("Terraform\n(VPCs · EKS · RDS)")

        # 3. AWS (inside a column, declaration order runs bottom to top)
        with lane("3 · AWS account · region", "aws", fontsize="20"):
            with lane("Shared-services VPC (private subnets)", "mgmt"):
                with box("Management cluster (Amazon EKS)", fontsize="15"):
                    crossplane = Custom("Crossplane\nplatform APIs +\nAWS provider", icon("crossplane"))
                    argocd = Argocd("Argo CD\nGitOps hub")
                    backstage = Custom("Backstage\ndeveloper portal", icon("backstage"))
                    mlflow = Mlflow("MLflow (shared)\ntracking + model registry\nper-tenant permissions")
                    with box("Central observability"):
                        otel = Custom("OpenTelemetry\nCollector", icon("opentelemetry"))
                        prometheus = Prometheus("Prometheus")
                        loki = Loki("Loki")
                        grafana = Grafana("Grafana")
                        opencost = Custom("OpenCost", icon("opencost"))

            with lane("Non-prod VPC (private subnets)", "nonprod"):
                with box("Workload cluster: non-prod (Amazon EKS)", fontsize="15"):
                    staging = Custom("Staging endpoints\n(KServe)", icon("kserve"))
                    notebooks = Custom("Notebooks", icon("jupyter"))
                    argo_wf = Custom("Argo Workflows\n(server + UI)", icon("argo"))
                    kueue = Custom("Kueue\nGPU queue per tenant", icon("kueue"))
                    with box("Tenant namespaces · non-prod (Capsule)"):
                        np_ns = [NS("retail-1042-*"), NS("risk-analytics-2001-*"), NS("marketing-3007-*")]
                        np_capsule = Custom("Capsule · quotas\ndefault-deny netpol\nPod Identity role", icon("capsule"))
                    with box("Karpenter NodePools · non-prod"):
                        np_karp = Custom("Karpenter", icon("karpenter"))
                        np_inf = EC2Instances("GPU inference")
                        np_cpu = EC2Instances("CPU")
                        np_gvisor = Gvisor("CPU · gVisor\nsandboxed")
                        np_gpu = EC2SpotInstance("GPU per tenant\n(spot, training)")

            with lane("Prod VPC (private subnets)", "prod"):
                with box("Workload cluster: prod (Amazon EKS)", fontsize="15"):
                    kserve = Custom("KServe endpoints\ncanary rollout", icon("kserve"))
                    vllm = Custom("vLLM runtime\n(LLMs)", icon("vllm"))
                    cron = Custom("Production pipelines\nCronWorkflows\n(scheduled retraining)", icon("argo"))
                    with box("Tenant namespaces · prod (Capsule)"):
                        p_ns = [NS("retail-1042-*"), NS("risk-analytics-2001-*"), NS("marketing-3007-*")]
                    with box("Karpenter NodePools · prod"):
                        p_karp = Custom("Karpenter", icon("karpenter"))
                        p_cpu = EC2Instances("CPU")
                        p_gvisor = Gvisor("CPU · gVisor\nsandboxed")
                        p_gpu = EC2SpotInstance("GPU per tenant\n(spot, training)")
                        p_inf = EC2Instances("GPU inference")

            with lane("Shared AWS services", "shared"):
                s3_mlflow = SimpleStorageServiceS3Bucket("S3: MLflow artifacts\ns3://<bucket>/tenants/<tenant>/")
                rds = RDSPostgresqlInstance("RDS PostgreSQL\n(Multi-AZ)\nMLflow backend store")
                ecr = EC2ContainerRegistry("ECR\nimages")
                s3_tenant = SimpleStorageServiceS3Bucket("S3: bucket per\ntenant per env")
                iam = IdentityAndAccessManagementIamRole("IAM role per tenant\n(EKS Pod Identity)")
                secrets = SecretsManager("Secrets Manager")
                eso = Custom("External Secrets\nOperator", icon("external-secrets"))
                route53 = Route53("Route 53")
                acm = CertificateManager("ACM")
                alb = ElbApplicationLoadBalancer("AWS Load Balancer\nController (ALB)")

        # 4. governance
        with lane("4 · Governance & FinOps", "gov"):
            kyverno = Custom("Kyverno policies\n(all clusters)", icon("kyverno"))
            audit = Cloudtrail("Audit & lineage\nCloudTrail · EKS audit\nMLflow lineage")
            cost_report = Custom("Showback / chargeback\nper BU (tenant label)\n→ Finance / FinOps", icon("opencost"))

        # edges
        aws_c = "cluster_3 · AWS account · region"
        nonprod_c = "cluster_Workload cluster: non-prod (Amazon EKS)"
        prod_c = "cluster_Workload cluster: prod (Amazon EKS)"

        for team in (retail, risk, marketing):
            team >> plain() >> vpn
        retail >> step(1, BLUE, "writes Python") >> hera
        platform_team >> plain() >> terraform

        hera >> step(1, BLUE, "submit job") >> argo_wf
        argo_wf >> step(1, BLUE) >> kueue
        kueue >> step(1, BLUE, "admit") >> np_karp
        np_karp >> step(1, BLUE, "GPU node") >> np_gpu

        argo_wf >> step(2, GREEN, "log runs, register model") >> mlflow
        mlflow >> step(2, GREEN, "metadata") >> rds
        mlflow >> step(2, GREEN, "artifacts") >> s3_mlflow

        mlflow >> step(3, PURPLE, "promote → GitOps PR") >> github
        github >> step(3, PURPLE, "merge") >> argocd
        argocd >> step(3, PURPLE, "canary") >> kserve
        kserve >> plain() >> vllm

        argocd >> step(4, ORANGE, "sync", lhead=nonprod_c) >> notebooks
        argocd >> step(4, ORANGE, "sync", lhead=prod_c) >> cron

        crossplane >> step(5, BROWN, "per-tenant bucket", style="dashed") >> s3_tenant
        crossplane >> step(5, BROWN, "IAM role", style="dashed") >> iam
        crossplane >> step(5, BROWN, "tenant namespaces", style="dashed") >> np_capsule

        idp >> step(6, TEAL, "SAML · Dex", style="dashed") >> backstage
        idp >> step(6, TEAL, "SAML · Dex", style="dashed") >> argo_wf
        idp >> step(6, TEAL, "SAML · Dex", style="dashed") >> mlflow

        staging >> step(7, RED, "metrics · logs", style="dotted", ltail=nonprod_c) >> otel
        cron >> step(7, RED, "metrics · logs", style="dotted", ltail=prod_c) >> otel
        otel >> step(7, RED, style="dotted") >> prometheus
        prometheus >> step(7, RED, style="dotted") >> opencost
        opencost >> step(7, RED, "cost per BU", style="dotted") >> cost_report

        github >> plain() >> actions
        actions >> plain() >> ecr
        terraform >> plain(lhead=aws_c) >> ecr
        alb >> plain() >> backstage
        route53 >> plain() >> alb
        acm >> plain() >> alb
        secrets >> plain() >> eso
        otel >> plain() >> loki
        prometheus >> plain() >> grafana

        place_columns(
            diagram,
            [
                [retail, risk, marketing, platform_team, finops],
                [hera, idp, vpn],
                [github, actions, terraform],
                [mlflow, argocd, crossplane, backstage, ecr, rds, s3_mlflow],
                [otel, loki, grafana, s3_tenant, iam, secrets, eso, alb],
                [prometheus, opencost, route53, acm],
                [argo_wf, notebooks, staging, cron, kserve, vllm],
                [kueue, np_capsule, *np_ns, *p_ns],
                [np_karp, p_karp],
                [np_gpu, np_cpu, np_gvisor, np_inf, p_inf, p_gpu, p_cpu, p_gvisor],
                [kyverno, audit, cost_report],
            ],
            legend(["people", "edge", "mgmt", "nonprod", "prod", "shared", "gov"], FLOWS),
        )
    return diagram


if __name__ == "__main__":
    publish(build(), NAME)
