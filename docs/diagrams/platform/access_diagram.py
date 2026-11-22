"""Access diagram: how the operator's laptop reaches the clusters and their URLs through Tailscale.

Solid = works once network + clusters are applied (kubectl); dashed = arrives with later phases
(portals behind the internal ALBs, installed through Argo CD).

Run from the repository root:
    python docs/diagrams/platform/access_diagram.py

Writes:
    docs/platform/images/tailscale-access.png
"""

from __future__ import annotations

from cluster_diagrams import EDGE, FONT, IMAGES, NODE, box, icon  # also sets PATH and the working directory

from diagrams import Diagram, Edge
from diagrams.aws.compute import EC2Instance, ElasticKubernetesService
from diagrams.aws.network import ElbApplicationLoadBalancer, Route53, Route53HostedZone
from diagrams.aws.security import CertificateManager
from diagrams.custom import Custom
from diagrams.generic.network import VPN
from diagrams.k8s.controlplane import API
from diagrams.onprem.client import Client
from diagrams.onprem.gitops import Argocd
from diagrams.onprem.mlops import Mlflow
from diagrams.onprem.monitoring import Grafana

GRAPH = {
    "bgcolor": "white",
    "pad": "0.5",
    "nodesep": "0.5",
    "ranksep": "1.0",
    "fontname": FONT,
    "fontsize": "26",
    "labelloc": "t",
    "dpi": "110",
    # curved lines: Graphviz can't place labels on orthogonal (right-angle) edges
    "splines": "spline",
}

LAPTOP = ("#ECEFF1", "#455A64")
TAILNET = ("#EDE7F6", "#5E35B1")
AWS = ("#FFF8E1", "#FF9900")
MGMT = ("#E8F5E9", "#43A047")
NONPROD = ("#FFF3E0", "#FB8C00")
WHITE = ("#FFFFFF", "#9E9E9E")

TUNNEL = {"color": "#5E35B1", "penwidth": "2.5"}
DNS = {"color": "#00838F", "style": "dashed", "penwidth": "1.5"}
LATER = {"color": "#9E9E9E", "style": "dashed"}
KUBECTL = {"color": "#1565C0", "penwidth": "1.8"}
CERT = {"color": "#00695C", "style": "dotted"}
SETUP = {"color": "#9575CD", "style": "dotted"}

LEGEND_ROWS = [
    ("#5E35B1", "━━━", "Encrypted WireGuard tunnel: laptop to router (all your traffic)"),
    ("#1565C0", "━━━", "kubectl to the private EKS API endpoints (works right after apply)"),
    ("#00838F", "╍╍╍", "DNS: mlqube.click questions to the VPC resolver and private zone"),
    ("#9E9E9E", "╍╍╍", "HTTPS to the portals through the internal ALBs (later phases)"),
    ("#00695C", "┈┈┈", "TLS certificate used by the internal ALBs"),
    ("#9575CD", "┈┈┈", "Setup only: keys, routes and DNS rules (no traffic)"),
]


def legend(diagram) -> None:
    cells = "".join(
        f'<tr><td><font color="{c}" point-size="16"><b>{line}</b></font></td>'
        f'<td align="left"><font point-size="13">{text}</font></td></tr>'
        for c, line, text in LEGEND_ROWS
    )
    diagram.dot.node(
        "legend",
        shape="plaintext",
        fixedsize="false",
        width="0",
        height="0",
        image="",
        labelloc="c",
        label=(
            '<<table border="1" color="#BDBDBD" cellborder="0" cellspacing="4" cellpadding="3" bgcolor="white">'
            '<tr><td colspan="2" align="left"><b>Legend</b></td></tr>' + cells + "</table>>"
        ),
    )


def access() -> None:
    out = IMAGES / "tailscale-access"
    with Diagram(
        "How you reach the clusters and their URLs through Tailscale",
        filename=str(out),
        outformat="png",
        show=False,
        direction="LR",
        graph_attr=GRAPH,
        node_attr=NODE,
        edge_attr=EDGE,
    ) as d:
        # ---------------------------------------------------------------- laptop
        with box("Your laptop", *LAPTOP, fontsize="15"):
            browser = Client("Browser\nhttps://argocd.mlqube.click")
            kubectl = API("kubectl\n(EKS API, private IPs)")
            ts_client = VPN("Tailscale client\nsplit DNS: mlqube.click → 10.10.0.2\nroutes: 10.10/16, 10.20/16")

        # ---------------------------------------------------------------- tailscale control plane
        with box("Tailscale (internet)", *TAILNET, fontsize="15"):
            control = VPN("Control plane\nkeys · routes · DNS rules\n(no traffic)")

        # ---------------------------------------------------------------- AWS
        with box("AWS us-west-2", *AWS, fontsize="16"):
            cert = CertificateManager("ACM certificate\n*.mlqube.click\n*.nonprod.mlqube.click")

            with box("VPC mlqube-mgmt · 10.10.0.0/16", *MGMT, fontsize="14"):
                router = EC2Instance("mlqube-router\n(Tailscale subnet router)\nt4g.micro, no public IP")
                resolver = Route53("VPC resolver\n10.10.0.2")
                zone = Route53HostedZone("Private zone mlqube.click\n(records by ExternalDNS)")
                mgmt_api = ElasticKubernetesService("mgmt API\nprivate endpoint")
                mgmt_alb = ElbApplicationLoadBalancer("Internal ALB (mgmt)\nHTTPS 443")
                with box("mgmt cluster · later phases", *WHITE, fontsize="12"):
                    argocd = Argocd("argocd.mlqube.click\n(Phase 1)")
                    grafana = Grafana("grafana.mlqube.click\n(Phase 1)")
                    mlflow = Mlflow("mlflow.mlqube.click\n(Phase 4)")
                    backstage = Custom("backstage.mlqube.click\n(Phase 6)", icon("backstage"))

            with box("VPC mlqube-nonprod · 10.20.0.0/16", *NONPROD, fontsize="14"):
                np_api = ElasticKubernetesService("wl-nonprod API\nprivate endpoint")
                np_alb = ElbApplicationLoadBalancer("Internal ALB (wl-nonprod)\nHTTPS 443")
                with box("wl-nonprod cluster · later phases", *WHITE, fontsize="12"):
                    workflows = Custom("workflows.nonprod.mlqube.click\n(Argo Workflows UI)", icon("argo"))
                    models = Custom("<model>.nonprod.mlqube.click\n(KServe staging)", icon("kserve"))

        # ---------------------------------------------------------------- edges
        browser >> Edge(label="1. look up name,\nthen open HTTPS", color="#455A64") >> ts_client
        kubectl >> Edge(label="API calls to\n10.x private IPs", color="#455A64") >> ts_client

        ts_client >> Edge(label="2. WireGuard tunnel (encrypted)\nall 10.10.x / 10.20.x traffic", **TUNNEL) >> router
        ts_client >> Edge(label="gets keys, routes,\nsplit DNS rule", **SETUP) >> control
        router >> Edge(label="joins with auth key,\nadvertises routes", **SETUP) >> control

        router >> Edge(label="3. DNS question\nfor *.mlqube.click", **DNS) >> resolver
        resolver >> Edge(label="looks up record,\nreturns ALB private IP", **DNS) >> zone

        router >> Edge(label="kubectl → API (443)", **KUBECTL) >> mgmt_api
        router >> Edge(label="4. HTTPS to\nALB private IP", **LATER) >> mgmt_alb
        mgmt_alb >> Edge(label="5. routes by host name", **LATER) >> argocd
        mgmt_alb >> Edge(**LATER) >> [grafana, mlflow, backstage]

        # wl-nonprod is reached through the VPC peering between the two VPCs
        router >> Edge(label="kubectl → API (443)\nvia VPC peering", **KUBECTL) >> np_api
        router >> Edge(label="HTTPS via\nVPC peering", **LATER) >> np_alb
        np_alb >> Edge(label="routes by host name", **LATER) >> workflows
        np_alb >> Edge(**LATER) >> models

        cert >> Edge(label="TLS for *.mlqube.click", **CERT) >> mgmt_alb
        cert >> Edge(label="TLS for *.nonprod.mlqube.click", **CERT) >> np_alb

        legend(d)


if __name__ == "__main__":
    access()
    p = IMAGES / "tailscale-access.png"
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")
