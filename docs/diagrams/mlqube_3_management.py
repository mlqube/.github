"""MlQube view 3: the management cluster and the shared AWS services.

What runs in the management cluster (the platform's control plane), and how it
uses the shared AWS services to deliver, provision, track and observe the
workload clusters. Tenant workloads never run in the management cluster.

Run: python docs/diagrams/mlqube_3_management.py  ->  mlqube_3_management.png / .svg
"""

from __future__ import annotations

from mlqube_style import (
    BROWN, GREEN, ORANGE, RED, SLATE, TEAL,
    box, icon, lane, legend, new_diagram, place_columns, plain, publish, step,
)

from diagrams.aws.compute import EC2ContainerRegistry
from diagrams.aws.compute import ElasticKubernetesService as EKS
from diagrams.aws.database import RDSPostgresqlInstance
from diagrams.aws.network import ElbApplicationLoadBalancer, Route53
from diagrams.aws.security import IdentityAndAccessManagementIamRole, SecretsManager
from diagrams.aws.storage import SimpleStorageServiceS3Bucket
from diagrams.custom import Custom
from diagrams.k8s.others import CRD
from diagrams.onprem.client import User, Users
from diagrams.onprem.gitops import Argocd
from diagrams.onprem.iac import Terraform
from diagrams.onprem.logging import Loki
from diagrams.onprem.mlops import Mlflow
from diagrams.onprem.monitoring import Grafana, Prometheus
from diagrams.onprem.vcs import Github

NAME = "mlqube_3_management"

FLOWS = [
    (1, SLATE, "bold", "Terraform builds the foundation: VPCs, the three EKS clusters, RDS, base IAM; it bootstraps Argo CD"),
    (2, ORANGE, "bold", "Argo CD (hub) syncs platform add-ons and configuration from Git to the management and workload clusters"),
    (3, TEAL, "dashed", "A tenant or project is requested in Backstage; the template opens a PR with a Tenant / MLProject claim"),
    (4, BROWN, "dashed", "Crossplane turns the claim into AWS and Kubernetes resources: S3 bucket, IAM role, ECR repo, namespaces, quotas"),
    (5, GREEN, "bold", "MLflow keeps metadata in RDS PostgreSQL and artifacts in S3 under a prefix per tenant"),
    (6, GREEN, "dashed", "External Secrets copies secrets (e.g. the RDS password) from Secrets Manager into the clusters"),
    (7, RED, "dotted", "All clusters send metrics, logs and traces to central observability; OpenCost reports cost per BU"),
]


def build():
    diagram = new_diagram(
        NAME,
        "MlQube: Management cluster and shared services",
        "3 · The platform's control plane · tenant workloads never run here",
        ranksep="1.4",
        nodesep="0.7",
    )
    with diagram:
        # inside a column, declaration order runs bottom to top
        with lane("People", "people"):
            platform_team = User("Platform team")
            engineer = Users("Tenant admin /\nML engineer")

        with lane("Corporate edge", "edge"):
            terraform = Terraform("Terraform\nfoundation (IaC)")
            github = Github("GitHub\nGitOps repos\nplatform · tenants")

        with lane("AWS account · region", "aws", fontsize="20"):
            with lane("Management cluster (EKS, shared-services VPC)", "mgmt"):
                with box("Cluster add-ons (in every cluster)"):
                    albc = ElbApplicationLoadBalancer("AWS Load Balancer\nController")
                    kyverno = Custom("Kyverno\npolicies", icon("kyverno"))
                    eso = Custom("External Secrets\nOperator", icon("external-secrets"))
                with box("Central observability"):
                    opencost = Custom("OpenCost\ncost per tenant label", icon("opencost"))
                    grafana = Grafana("Grafana\ndashboards")
                    loki = Loki("Loki\nlogs")
                    prometheus = Prometheus("Prometheus\nmetrics")
                    otel = Custom("OpenTelemetry\nCollector", icon("opentelemetry"))
                with box("ML metadata"):
                    mlflow = Mlflow("MLflow (one, shared)\ntracking + model registry\nper-tenant permissions")
                with box("Platform APIs (MlQube glue)"):
                    crossplane = Custom("Crossplane\n+ AWS and Kubernetes\nproviders", icon("crossplane"))
                    claims = CRD("MlQube APIs\nTenant · MLProject\nWorkspace · ModelDeployment")
                with box("Delivery and portal"):
                    argocd = Argocd("Argo CD\nGitOps hub\n(ApplicationSets)")
                    backstage = Custom("Backstage\ntemplates · catalog\ncost views", icon("backstage"))

            with lane("Shared AWS services", "shared"):
                route53 = Route53("Route 53 · ACM\nprivate DNS + TLS")
                secrets = SecretsManager("Secrets Manager")
                s3_mlflow = SimpleStorageServiceS3Bucket("S3: MLflow artifacts\ns3://<bucket>/tenants/<tenant>/")
                rds = RDSPostgresqlInstance("RDS PostgreSQL\nMulti-AZ\nMLflow backend store")
                ecr = EC2ContainerRegistry("ECR\nrepo per project")
                iam = IdentityAndAccessManagementIamRole("IAM role per tenant\n(EKS Pod Identity)")
                s3_tenant = SimpleStorageServiceS3Bucket("S3: bucket per\ntenant per env")
            # (shared services stack top to bottom: tenant resources, MLflow stores, secrets, DNS)

            with lane("Workload clusters", "nonprod"):
                prod = EKS("Prod cluster (EKS)\ntenant namespaces")
                nonprod = EKS("Non-prod cluster (EKS)\ntenant namespaces")

        with lane("Governance & FinOps", "gov"):
            cost = Custom("Showback / chargeback\nper BU", icon("opencost"))

        # ① foundation
        platform_team >> step(1, SLATE, "terraform apply") >> terraform
        terraform >> step(1, SLATE, "VPCs · EKS · RDS · IAM") >> rds
        terraform >> step(1, SLATE, "bootstrap") >> argocd

        # ② GitOps
        github >> step(2, ORANGE, "desired state") >> argocd
        argocd >> step(2, ORANGE, "sync") >> nonprod
        argocd >> step(2, ORANGE, "sync") >> prod
        argocd >> step(2, ORANGE, "add-ons") >> eso

        # ③ self-service request
        engineer >> step(3, TEAL, "new tenant / project", style="dashed") >> backstage
        backstage >> step(3, TEAL, "template opens PR", style="dashed") >> github
        argocd >> step(3, TEAL, "applies claim", style="dashed") >> claims

        # ④ Crossplane provisioning
        claims >> step(4, BROWN, "reconcile", style="dashed") >> crossplane
        crossplane >> step(4, BROWN, "bucket", style="dashed") >> s3_tenant
        crossplane >> step(4, BROWN, "IAM role", style="dashed") >> iam
        crossplane >> step(4, BROWN, "ECR repo", style="dashed") >> ecr
        crossplane >> step(4, BROWN, "namespaces · quotas · queues", style="dashed") >> nonprod

        # ⑤ MLflow stores
        mlflow >> step(5, GREEN, "metadata") >> rds
        mlflow >> step(5, GREEN, "artifacts") >> s3_mlflow

        # ⑥ secrets
        secrets >> step(6, GREEN, "sync", style="dashed") >> eso
        eso >> step(6, GREEN, "DB password", style="dashed") >> mlflow

        # ⑦ observability and cost
        nonprod >> step(7, RED, "metrics · logs · traces", style="dotted") >> otel
        prod >> step(7, RED, "metrics · logs · traces", style="dotted") >> otel
        otel >> step(7, RED, style="dotted") >> prometheus
        otel >> plain() >> loki
        prometheus >> plain() >> grafana
        prometheus >> step(7, RED, style="dotted") >> opencost
        opencost >> step(7, RED, "cost per BU", style="dotted") >> cost

        route53 >> plain() >> albc

        place_columns(
            diagram,
            [
                [engineer, platform_team],
                [github, terraform],
                [backstage, argocd],
                [claims, mlflow, otel, loki, eso],
                [crossplane, prometheus, grafana, opencost, kyverno, albc],
                [s3_tenant, iam, ecr, rds, s3_mlflow, secrets, route53],
                [nonprod, prod],
                [cost],
            ],
            legend(
                [("people", "People"), ("edge", "Corporate edge"), "mgmt", "shared",
                 ("nonprod", "Workload clusters (non-prod and prod)"), "gov"],
                FLOWS,
            ),
        )
    return diagram


if __name__ == "__main__":
    publish(build(), NAME)
