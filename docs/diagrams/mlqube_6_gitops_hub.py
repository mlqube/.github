"""MlQube view 6: GitOps hub and spoke, one Argo CD for every cluster.

A single Argo CD runs in the management cluster (the hub). Workload clusters (the spokes) run
no Argo CD: they are registered as destinations, and Argo CD applies to them over private
networking with an IAM identity that each spoke trusts through an EKS access entry.

Run: python docs/diagrams/mlqube_6_gitops_hub.py  ->  mlqube_6_gitops_hub.png / .svg
"""

from __future__ import annotations

from mlqube_style import (
    GREY, ORANGE, SLATE, TEAL,
    box, icon, lane, legend, new_diagram, place_columns, plain, publish, step,
)

from diagrams.aws.compute import ElasticKubernetesService as EKS
from diagrams.aws.network import ElbApplicationLoadBalancer, VPCPeering
from diagrams.aws.security import IdentityAndAccessManagementIamRole
from diagrams.custom import Custom
from diagrams.k8s.ecosystem import ExternalDns
from diagrams.k8s.group import NS
from diagrams.k8s.others import CRD
from diagrams.k8s.podconfig import Secret
from diagrams.onprem.client import User
from diagrams.onprem.gitops import Argocd
from diagrams.onprem.iac import Terraform
from diagrams.onprem.vcs import Github

NAME = "mlqube_6_gitops_hub"

FLOWS = [
    (1, SLATE, "bold", "Terraform installs Argo CD in the hub and registers each workload cluster: a cluster secret in Argo CD, an EKS access entry in the spoke"),
    (2, ORANGE, "bold", "Argo CD pulls the GitOps repository (read-only deploy key): the desired state of every cluster"),
    (3, ORANGE, "dashed", "An ApplicationSet (cluster generator) creates one Application per add-on per registered cluster, with that cluster's values"),
    (4, ORANGE, "bold", "Argo CD applies the hub's own add-ons and platform tools in-cluster"),
    (5, ORANGE, "bold", "Argo CD applies to the spoke: Pod Identity credentials, private API over VPC peering, authorized by the access entry"),
    (6, GREY, "dotted", "Prod (later) is registered the same way; in a separate AWS account through a cross-account role"),
    (7, TEAL, "dashed", "The platform team sees and operates every cluster in one Argo CD UI (private URL, single sign-on later)"),
]


def build():
    diagram = new_diagram(
        NAME,
        "MlQube: GitOps hub and spoke",
        "6 · One Argo CD in the management cluster deploys to every cluster · workload clusters run no Argo CD",
        ranksep="1.3",
        nodesep="0.6",
    )
    with diagram:
        # inside a column, declaration order runs bottom to top
        with lane("People", "people"):
            platform_team = User("Platform team")

        with lane("Source of truth & bootstrap", "edge"):
            terraform = Terraform("Terraform\nbootstrap layer\n(every platform build)")
            github = Github("GitHub · GitOps repo\nclusters/<cluster>/\nplatform/ · tenants/")

        with lane("AWS account · region", "aws", fontsize="20"):
            with lane("Management cluster: the hub (shared-services VPC)", "mgmt"):
                with box("Argo CD: the only one"):
                    role = IdentityAndAccessManagementIamRole("IAM role for Argo CD\n(EKS Pod Identity)")
                    clusters = Secret("Cluster secrets\nin-cluster · wl-nonprod\n(prod later)")
                    appset = CRD("ApplicationSet\ncluster generator\none app per cluster")
                    argocd = Argocd("Argo CD\ncontroller · repo server · UI\n(app of apps: root)")
                with box("Applied in-cluster"):
                    tools = Custom("Platform tools (later)\nBackstage · MLflow ·\nCrossplane · Grafana", icon("backstage"))
                    karp_m = Custom("Karpenter\nCPU NodePool", icon("karpenter"))
                    edns_m = ExternalDns("ExternalDNS\n*.mlqube.click")
                    albc_m = ElbApplicationLoadBalancer("AWS Load Balancer\nController")

            peering = VPCPeering("VPC peering\nhub ↔ spoke\nprivate API :443")

            with lane("Workload cluster: prod (Phase 5)", "prod"):
                api_p = EKS("Prod cluster (EKS)\nregistered the same way\nno Argo CD")

            with lane("Workload cluster: non-prod, a spoke (no Argo CD)", "nonprod"):
                api_np = EKS("EKS API (private)\naccess entry:\nArgo CD's role = admin")
                with box("Workloads (later)"):
                    tenants = NS("Tenant namespaces\nquotas · policies")
                    kserve = Custom("KServe\nstaging endpoints", icon("kserve"))
                    workflows = Custom("Argo Workflows\n+ Kueue (ML jobs)", icon("argo"))
                with box("Add-ons (same templates, own values)"):
                    karp_n = Custom("Karpenter\nCPU + GPU NodePools", icon("karpenter"))
                    edns_n = ExternalDns("ExternalDNS\n*.nonprod.mlqube.click")
                    albc_n = ElbApplicationLoadBalancer("AWS Load Balancer\nController")

        # ① bootstrap and registration
        terraform >> step(1, SLATE, "install Argo CD") >> argocd
        terraform >> step(1, SLATE, "register clusters") >> clusters
        terraform >> step(1, SLATE, "access entry for Argo CD's role") >> api_np

        # ② desired state
        github >> step(2, ORANGE, "git pull (deploy key)") >> argocd

        # ③ one Application per cluster
        argocd >> step(3, ORANGE, "ApplicationSet", style="dashed") >> appset
        appset >> step(3, ORANGE, "reads the cluster list", style="dashed") >> clusters

        # ④ the hub itself
        argocd >> step(4, ORANGE, "in-cluster") >> albc_m
        argocd >> plain() >> edns_m
        argocd >> plain() >> karp_m
        argocd >> plain(style="dashed") >> tools

        # ⑤ the spoke
        argocd >> step(5, ORANGE, "credentials") >> role
        argocd >> step(5, ORANGE, "apply") >> peering
        peering >> step(5, ORANGE, "private API") >> api_np
        api_np >> plain() >> albc_n
        api_np >> plain() >> edns_n
        api_np >> plain() >> karp_n
        api_np >> plain(style="dashed") >> workflows
        api_np >> plain(style="dashed") >> kserve
        api_np >> plain(style="dashed") >> tenants

        # ⑥ prod later
        argocd >> step(6, GREY, "later", style="dotted") >> api_p

        # ⑦ one UI
        platform_team >> step(7, TEAL, "one UI for all clusters", style="dashed") >> argocd

        place_columns(
            diagram,
            [
                [platform_team],
                [terraform, github],
                [role, clusters, appset, argocd],
                [tools, karp_m, edns_m, albc_m],
                [peering],
                [api_p, api_np],
                [tenants, kserve, workflows, karp_n, edns_n, albc_n],
            ],
            legend(
                [("people", "People"), ("edge", "Source of truth &amp; bootstrap"),
                 ("mgmt", "Management cluster (hub)"), ("nonprod", "Workload cluster: non-prod (spoke)"),
                 ("prod", "Workload cluster: prod (spoke, later)")],
                FLOWS,
                note="Applied by Argo CD (dashed: later phases)",
            ),
        )
    return diagram


if __name__ == "__main__":
    publish(build(), NAME)
