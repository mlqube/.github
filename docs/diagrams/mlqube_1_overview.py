"""MlQube view 1: high-level architecture.

One node per major building block and the main relationships between them.
Run: python docs/diagrams/mlqube_1_overview.py  ->  mlqube_1_overview.png / .svg
"""

from __future__ import annotations

from mlqube_style import (
    BLUE, GREEN, ORANGE, PURPLE, RED, TEAL,
    icon, lane, legend, link, new_diagram, place_columns, plain, publish,
)

from diagrams.aws.compute import ElasticKubernetesService as EKS
from diagrams.aws.general import Client
from diagrams.aws.storage import SimpleStorageServiceS3
from diagrams.custom import Custom
from diagrams.onprem.client import User, Users
from diagrams.onprem.iac import Terraform
from diagrams.onprem.vcs import Github
from diagrams.aws.security import SingleSignOn

NAME = "mlqube_1_overview"

FLOWS = [
    (None, TEAL, "dashed", "Identity: single sign-on through IAM Identity Center (a corporate directory can feed it)"),
    (None, BLUE, "bold", "Code: ML engineers push Python (Hera) pipelines to GitHub"),
    (None, ORANGE, "bold", "Delivery: the management cluster deploys and provisions everything through GitOps"),
    (None, PURPLE, "bold", "Models: promotion from non-prod to prod, then serving to applications"),
    (None, GREEN, "bold", "Data: clusters use shared S3, ECR, RDS and Secrets Manager"),
    (None, RED, "dotted", "Control: policies, audit and cost per business unit"),
]


def build():
    diagram = new_diagram(
        NAME,
        "MlQube: Enterprise ML Platform on AWS",
        "1 · High-level architecture · internal developer platform for ML/AI on Amazon EKS",
        ranksep="2.1",
        nodesep="1.7",
    )
    with diagram:
        # inside a column, declaration order runs bottom to top
        with lane("People & business units", "people"):
            finops = User("Finance / FinOps")
            platform_team = User("Platform team")
            bus = Users("Business units = tenants\nretail-1042\nrisk-analytics-2001\nmarketing-3007\n(ML engineers, data scientists)")

        with lane("Corporate edge & identity", "edge"):
            terraform = Terraform("Terraform\ninfrastructure as code")
            github = Github("GitHub\ncode · GitOps repos · Actions")
            idp = SingleSignOn("IAM Identity Center\nSSO · groups per tenant\n(fed by the corporate\ndirectory in an enterprise)")

        with lane("AWS account · region", "aws", fontsize="20"):
            with lane("Shared AWS services", "shared"):
                shared = SimpleStorageServiceS3("S3 · ECR · RDS PostgreSQL\nSecrets Manager\nRoute 53 · ACM · ALB")
            with lane("Shared-services VPC", "mgmt"):
                mgmt = EKS("Management cluster (EKS)\nplatform control plane\nArgo CD · Crossplane · Backstage\nshared MLflow · observability")
            with lane("Prod VPC", "prod"):
                prod = EKS("Prod workload cluster (EKS)\nserve models · scheduled retraining\nKServe · vLLM · CronWorkflows")
            with lane("Non-prod VPC", "nonprod"):
                nonprod = EKS("Non-prod workload cluster (EKS)\nexperiment · train · test\nnotebooks · Argo Workflows · staging")

        with lane("Consumers of models", "consumers"):
            apps = Client("Business applications\n(inference API calls)")

        with lane("Governance & FinOps", "gov"):
            cost = Custom("Cost showback /\nchargeback per BU", icon("opencost"))
            policy = Custom("Policies & audit\nKyverno in every cluster\nCloudTrail · MLflow lineage", icon("kyverno"))

        # identity
        bus >> link("sign in", TEAL, "dashed") >> idp
        idp >> link("SAML SSO via Dex\n(portals · UIs)", TEAL, "dashed") >> mgmt

        # code and delivery
        bus >> link("Python + Hera", BLUE) >> github
        platform_team >> plain() >> terraform
        terraform >> link("provisions VPCs · EKS · RDS", "#757575", "bold", lhead="cluster_AWS account · region") >> mgmt
        github >> link("GitOps", ORANGE) >> mgmt
        mgmt >> link("GitOps deploy", ORANGE) >> nonprod
        mgmt >> link("GitOps deploy", ORANGE) >> prod

        # models
        nonprod >> link("promote model\n(GitOps PR)", PURPLE) >> prod
        prod >> link("predictions", PURPLE) >> apps

        # data
        mgmt >> link("metadata · artifacts", GREEN) >> shared

        # control
        mgmt >> link("usage → cost per BU", RED, "dotted") >> cost
        cost >> link("reports", RED, "dotted") >> finops

        place_columns(
            diagram,
            [
                [bus, platform_team, finops],
                [idp, github, terraform],
                [mgmt, shared],
                [nonprod, prod],
                [apps],
                [policy, cost],
            ],
            legend(["people", "edge", "mgmt", "nonprod", "prod", "shared", "consumers", "gov"], FLOWS,
                   flows_title="Relationships"),
        )
    return diagram


if __name__ == "__main__":
    publish(build(), NAME)
