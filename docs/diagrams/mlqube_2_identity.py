"""MlQube view 2: identity - how people are authenticated and authorized.

People sign in once through the corporate IdP (OIDC). Their IdP groups
(mlqube-<tenant>-admins / -developers / -viewers) decide what they can do in each
tool and in the tenant's namespaces. Workloads never use static keys: they get a
per-tenant IAM role through EKS Pod Identity.

Run: python docs/diagrams/mlqube_2_identity.py  ->  mlqube_2_identity.png / .svg
"""

from __future__ import annotations

from mlqube_style import (
    GREEN, SLATE, TEAL,
    box, icon, lane, legend, new_diagram, place_columns, plain, publish, step,
)

from diagrams.aws.compute import EC2ContainerRegistry
from diagrams.aws.network import ElbApplicationLoadBalancer, Route53
from diagrams.aws.security import (
    CertificateManager,
    IdentityAndAccessManagementIamAWSSts,
    IdentityAndAccessManagementIamRole,
    SecretsManager,
)
from diagrams.aws.storage import SimpleStorageServiceS3Bucket
from diagrams.custom import Custom
from diagrams.generic.network import VPN
from diagrams.k8s.compute import Pod
from diagrams.k8s.controlplane import API
from diagrams.k8s.rbac import RB, Group
from diagrams.onprem.client import User, Users
from diagrams.onprem.gitops import Argocd
from diagrams.onprem.mlops import Mlflow
from diagrams.onprem.monitoring import Grafana
from diagrams.saas.identity import Okta

NAME = "mlqube_2_identity"

FLOWS = [
    (1, TEAL, "dashed", "Users reach the portals over the corporate network / VPN, through a private ALB (TLS from ACM)"),
    (2, TEAL, "dashed", "Each tool signs the user in with the corporate IdP (OIDC + MFA); the ID token carries the user's groups"),
    (3, SLATE, "bold", "Each tool maps groups to tenant roles: admins / developers / viewers of their own tenant only"),
    (4, SLATE, "bold", "kubectl uses the same OIDC token; RBAC + Capsule limit users to their tenant's namespaces"),
    (5, SLATE, "bold", "Every object is checked at admission by Kyverno and Capsule (tenant labels, quotas, allowed images)"),
    (6, GREEN, "bold", "Workloads: tenant ServiceAccount → EKS Pod Identity → per-tenant IAM role → only that tenant's AWS resources"),
]


def build():
    diagram = new_diagram(
        NAME,
        "MlQube: Identity, authentication and authorization",
        "2 · Single sign-on with the corporate IdP · groups per tenant · no static cloud keys for workloads",
        ranksep="1.5",
        nodesep="0.8",
    )
    with diagram:
        # inside a column, declaration order runs bottom to top
        with lane("People", "people"):
            admin = User("Platform admin\nmlqube-platform-admins")
            viewer = User("Viewer / FinOps\nmlqube-retail-1042-viewers")
            dev = Users("ML engineer (retail-1042)\nmlqube-retail-1042-developers")

        with lane("Corporate edge & identity", "edge"):
            vpn = VPN("Corporate network / VPN")
            groups = Group(
                "IdP groups per tenant\nmlqube-<tenant>-admins\nmlqube-<tenant>-developers\n"
                "mlqube-<tenant>-viewers\ne.g. tenant = retail-1042"
            )
            idp = Okta("Corporate IdP\n(Entra ID / Okta)\nOIDC · MFA · conditional access")

        with lane("AWS account · region", "aws", fontsize="20"):
            with lane("Private entry (shared services)", "shared"):
                acm = CertificateManager("ACM\nTLS certificates")
                route53 = Route53("Route 53\nprivate hosted zone")
                alb = ElbApplicationLoadBalancer("Internal ALB\n(AWS Load Balancer\nController)")

            with lane("Workload clusters (non-prod · prod)", "nonprod"):
                with box("Sign-in points "):
                    eks_api = API("EKS API server\nOIDC identity provider\n(kubectl)")
                    argo_wf = Custom("Argo Workflows\nserver + UI (SSO)", icon("argo"))
                with box("Authorization in the cluster"):
                    kyverno = Custom("Kyverno + Capsule\nadmission policies", icon("kyverno"))
                    k8s_rbac = RB("Kubernetes RBAC\nCapsule tenant owners\n= IdP groups")
                    argo_rbac = Custom("Argo Workflows SSO RBAC\ngroup → tenant\nServiceAccount", icon("argo"))
                with box("Workload identity (no static keys)"):
                    pod = Pod("Tenant pod\nServiceAccount in\nretail-1042-churn")
                    pod_identity = IdentityAndAccessManagementIamAWSSts("EKS Pod Identity\n(temporary credentials)")

            with lane("Management cluster", "mgmt"):
                with box("Sign-in points"):
                    argocd = Argocd("Argo CD UI\nplatform admins only")
                    grafana = Grafana("Grafana\ndashboards per tenant")
                    mlflow = Mlflow("MLflow (shared)")
                    backstage = Custom("Backstage\ndeveloper portal", icon("backstage"))
                with box("Authorization in the tools"):
                    grafana_perm = Group("Grafana teams\nper tenant")
                    mlflow_perm = RB("MLflow permissions\nper-tenant experiments\n& registered models")
                    backstage_perm = RB("Backstage permissions\nownership = tenant group")

            with lane("Tenant AWS resources (shared services)", "shared"):
                iam_role = IdentityAndAccessManagementIamRole("IAM role per tenant\nmlqube-retail-1042")
                with box("Only this tenant's"):
                    secrets = SecretsManager("Secrets Manager\n(tenant path)")
                    ecr = EC2ContainerRegistry("ECR repos")
                    s3 = SimpleStorageServiceS3Bucket("S3 bucket\nretail-1042-<env>")

        # ① network path
        dev >> step(1, TEAL, "corporate network", style="dashed") >> vpn
        vpn >> step(1, TEAL, "HTTPS", style="dashed") >> alb
        alb >> step(1, TEAL, "portals", style="dashed") >> backstage
        alb >> step(1, TEAL, "Argo UI", style="dashed") >> argo_wf
        route53 >> plain() >> alb
        acm >> plain() >> alb
        viewer >> plain() >> vpn
        admin >> plain() >> vpn

        # ② OIDC sign-in with group claims
        groups >> plain() >> idp
        for app in (backstage, mlflow, grafana, argocd, argo_wf):
            idp >> step(2, TEAL, "OIDC ID token + groups", style="dashed") >> app

        # ③ tools map groups to tenant roles
        backstage >> step(3, SLATE, "owner / member") >> backstage_perm
        mlflow >> step(3, SLATE, "READ / EDIT / MANAGE") >> mlflow_perm
        grafana >> step(3, SLATE, "team") >> grafana_perm
        argo_wf >> step(3, SLATE, "group → SA") >> argo_rbac

        # ④ kubectl / Kubernetes API
        dev >> step(4, SLATE, "kubectl with OIDC token") >> eks_api
        eks_api >> step(4, SLATE, "group → RoleBinding") >> k8s_rbac

        # ⑤ admission
        eks_api >> step(5, SLATE, "admission") >> kyverno
        argo_rbac >> step(5, SLATE, "creates pods") >> pod

        # ⑥ workload identity
        pod >> step(6, GREEN, "ServiceAccount") >> pod_identity
        pod_identity >> step(6, GREEN, "assume role") >> iam_role
        iam_role >> step(6, GREEN) >> s3
        iam_role >> step(6, GREEN) >> ecr
        iam_role >> step(6, GREEN) >> secrets

        place_columns(
            diagram,
            [
                [dev, viewer, admin],
                [idp, groups, vpn],
                [alb, route53, acm],
                [backstage, mlflow, grafana, argocd, argo_wf, eks_api],
                [backstage_perm, mlflow_perm, grafana_perm, argo_rbac, k8s_rbac, kyverno],
                [pod],
                [pod_identity],
                [iam_role],
                [s3, ecr, secrets],
            ],
            legend(
                [
                    ("people", "People"),
                    "edge",
                    ("shared", "Shared AWS services (entry · tenant resources)"),
                    "mgmt",
                    ("nonprod", "Workload clusters (non-prod and prod)"),
                ],
                FLOWS,
                note="Supporting connection",
            ),
        )
    return diagram


if __name__ == "__main__":
    publish(build(), NAME)
