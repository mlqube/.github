"""Single sign-on to Argo CD through the standalone Dex and AWS IAM Identity Center: every hop
of one sign-in, and where the configuration comes from.

Requirements: Python with `diagrams`, and Graphviz (`dot`) on PATH.

Run from the repository root:
    python docs/diagrams/platform/sso_diagram.py

Writes:
    docs/platform/images/sso-flow.png
"""

from __future__ import annotations

from addon_diagrams import AWS, CLUSTER, GITOPS, LAPTOP, NS, TERRAFORM, diagram, legend
from app_of_apps import box  # also sets PATH for Graphviz

from diagrams import Edge
from diagrams.aws.management import SystemsManagerParameterStore
from diagrams.aws.network import ElbApplicationLoadBalancer
from diagrams.aws.security import SingleSignOn
from diagrams.k8s.podconfig import Secret
from diagrams.onprem.client import Client
from diagrams.onprem.gitops import Argocd
from diagrams.onprem.iac import Terraform
from diagrams.onprem.identity import Dex
from diagrams.programming.flowchart import Decision

BROWSER = {"color": "#5E35B1", "penwidth": "2.2"}  # what the browser does (redirects, posts)
SIGNIN = {"color": "#FF9900", "penwidth": "2.2"}  # at Identity Center
BACKEND = {"color": "#2E7D32", "penwidth": "2.2", "style": "bold"}  # server to server
CONFIG = {"color": "#6A1B9A", "style": "dashed"}
DEPLOY = {"color": "#9E9E9E", "style": "dashed"}


def sso_flow() -> None:
    with diagram(
        "Signing in to https://argocd.mlqube.click: IAM Identity Center (SAML) → Dex → Argo CD (OIDC)",
        "sso-flow",
    ) as d:
        with box("Your laptop (Tailscale on)", *LAPTOP, fontsize="13"):
            browser = Client("Browser")

        with box("AWS IAM Identity Center (AWS sign-in portal, over the internet)", *AWS, fontsize="13"):
            idc = SingleSignOn("\n\nIAM Identity Center\nassigned to\n\"Argo CD (MlQube)\"?")

        with box("AWS us-west-2 · VPC mlqube-mgmt", *AWS, fontsize="15"):
            alb = ElbApplicationLoadBalancer(
                "Internal ALB (group mlqube-mgmt)\nargocd.mlqube.click\ndex.mlqube.click\nTLS *.mlqube.click"
            )

            with box("EKS cluster mgmt", *CLUSTER, fontsize="15"):
                with box("namespace argocd", *NS, fontsize="12"):
                    argocd = Argocd("argocd-server\nOIDC client \"argo-cd\"")
                    rbac = Decision("\n\nRBAC: group ID of\nmlqube-platform-admins\n→ role:admin")
                    client_secret = Secret("Secret\nargocd-dex-client\n(client secret)")
                with box("namespace dex", *NS, fontsize="12"):
                    dex = Dex("Dex\nissuer https://dex.mlqube.click\nSAML → OIDC")
                    dex_config = Secret(
                        "Secret dex-config\nIdentity Center connector\n(sign-in URL, certificate)\n+ client argo-cd"
                    )

            with box("Set up once / every build", *TERRAFORM, fontsize="13"):
                ssm = SystemsManagerParameterStore(
                    "SSM Parameter Store\n/mlqube/argocd/sso-url\n/mlqube/argocd/sso-ca\n/mlqube/argocd/sso-admin-group-id"
                )
                tf = Terraform("\n\naddons-mgmt (sso.tf):\nconfig, namespace,\nrandom client secret")

        with box("gitops (applied by Argo CD)", *GITOPS, fontsize="13"):
            dex_app = Argocd("Application mgmt-dex\nDex chart 0.26.0,\nIngress dex.mlqube.click")

        # The sign-in. Every browser request goes through the internal ALB (over Tailscale); only the
        # sign-in page itself is at Identity Center, on the internet. Each server answers with a
        # redirect ("go there next"), shown on the arrow into that server.
        browser >> Edge(
            label="1. argocd.mlqube.click\n3. dex.mlqube.click/auth\n5. dex.mlqube.click/callback\n"
            "7. argocd.mlqube.click/auth/callback",
            **BROWSER,
        ) >> alb
        alb >> Edge(
            label="1 → 2. not signed in:\nredirect to Dex\n7 → code received (step 8)", **BROWSER
        ) >> argocd
        alb >> Edge(
            label="3 → 4. redirect to Identity Center\n5 → 6. signature checked;\nredirect to Argo CD with a one-time code",
            **BROWSER,
        ) >> dex
        browser >> Edge(label="4. sign in: password, MFA", **SIGNIN) >> idc
        idc >> Edge(
            label="5. SAML answer (email + group IDs), signed;\nthe browser posts it to dex.mlqube.click/callback",
            constraint="false",
            **SIGNIN,
        ) >> browser
        argocd >> Edge(label="8. code → ID token\n(server to server,\nclient secret)", **BACKEND) >> dex
        argocd >> Edge(label="9. email + group IDs", **BACKEND) >> rbac

        # configuration
        ssm >> Edge(**CONFIG) >> tf
        tf >> Edge(label="writes", **CONFIG) >> dex_config
        tf >> Edge(label="writes", **CONFIG) >> client_secret
        dex_config >> Edge(**CONFIG) >> dex
        client_secret >> Edge(**CONFIG) >> argocd
        dex_app >> Edge(label="deploys", **DEPLOY) >> dex

        legend(
            d,
            [
                ("#5E35B1", "━━━", "Browser requests, all through the internal ALB (over Tailscale)"),
                ("#FF9900", "━━━", "At IAM Identity Center: sign-in, and its SAML answer"),
                ("#2E7D32", "━━━", "Argo CD ↔ Dex, server to server inside the VPC"),
                ("#6A1B9A", "╍╍╍", "Configuration (Terraform, from SSM)"),
                ("#9E9E9E", "╍╍╍", "Deployed by Argo CD from gitops"),
            ],
        )


if __name__ == "__main__":
    sso_flow()
    print("wrote docs/platform/images/sso-flow.png")
