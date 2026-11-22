"""Diagrams for the mgmt add-ons: how Karpenter manages nodes, and how an Ingress becomes an
internal ALB with a private DNS name (AWS Load Balancer Controller + ExternalDNS).

Requirements: Python with `diagrams`, and Graphviz (`dot`) on PATH.

Run from the repository root:
    python docs/diagrams/platform/addon_diagrams.py

Writes:
    docs/platform/images/karpenter-flow.png
    docs/platform/images/ingress-flow.png
    docs/platform/images/dns-lookup.png
"""

from __future__ import annotations

from app_of_apps import EDGE, FONT, IMAGES, NODE, box, icon  # also sets PATH for Graphviz

from diagrams import Diagram, Edge
from diagrams.aws.compute import EC2Ami, EC2SpotInstance
from diagrams.aws.integration import Eventbridge, SimpleQueueServiceSqs
from diagrams.aws.network import ElbApplicationLoadBalancer, Route53, Route53HostedZone, VPCElasticNetworkInterface
from diagrams.aws.security import CertificateManager, IdentityAndAccessManagementIamRole
from diagrams.custom import Custom
from diagrams.generic.network import VPN
from diagrams.k8s.compute import Pod
from diagrams.k8s.ecosystem import ExternalDns
from diagrams.k8s.infra import Node
from diagrams.k8s.network import Ing, SVC
from diagrams.k8s.others import CRD
from diagrams.onprem.client import Client
from diagrams.onprem.gitops import Argocd

GRAPH = {
    "bgcolor": "white",
    "pad": "0.5",
    "nodesep": "0.45",
    "ranksep": "1.0",
    "fontname": FONT,
    "fontsize": "26",
    "labelloc": "t",
    "dpi": "90",
    "splines": "spline",
}

AWS = ("#FFF8E1", "#FF9900")
TERRAFORM = ("#ECEFF1", "#455A64")
GITOPS = ("#F3E5F5", "#6A1B9A")
CLUSTER = ("#E8F5E9", "#43A047")
NS = ("#FFFFFF", "#9E9E9E")
RUNTIME = ("#E3F2FD", "#1565C0")
LAPTOP = ("#ECEFF1", "#455A64")

FLOW = {"color": "#2E7D32", "penwidth": "2.0"}
IDENTITY = {"color": "#FF9900", "style": "dotted", "penwidth": "1.6"}
CONFIG = {"color": "#6A1B9A", "style": "dashed"}
INTERRUPT = {"color": "#C62828", "style": "dashed", "penwidth": "1.6"}
CONSOLIDATE = {"color": "#757575", "style": "dashed"}
DNS = {"color": "#00838F", "style": "dashed", "penwidth": "1.6"}
USER = {"color": "#5E35B1", "penwidth": "2.0"}


def legend(diagram, rows: list[tuple[str, str, str]]) -> None:
    cells = "".join(
        f'<tr><td><font color="{c}" point-size="16"><b>{line}</b></font></td>'
        f'<td align="left"><font point-size="13">{text}</font></td></tr>'
        for c, line, text in rows
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


def diagram(title: str, out: str) -> Diagram:
    return Diagram(
        title,
        filename=str(IMAGES / out),
        outformat="png",
        show=False,
        direction="LR",
        graph_attr=GRAPH,
        node_attr=NODE,
        edge_attr=EDGE,
    )


# ------------------------------------------------------------------------------------- Karpenter
def karpenter_flow() -> None:
    with diagram("Karpenter in mgmt: how a node is started, replaced and removed", "karpenter-flow") as d:
        with box("gitops (applied by Argo CD)", *GITOPS, fontsize="13"):
            nodepool = CRD("NodePool general\nCPU c/m/r gen 6+, spot first,\nmax 16 vCPU, consolidate after 1 min")
            nodeclass = CRD("EC2NodeClass default\nAL2023, node role, subnets and\nsecurity group by tag, 30 GiB gp3")

        with box("AWS us-west-2", *AWS, fontsize="16"):
            with box("Created by Terraform (addons-mgmt), every build", *TERRAFORM, fontsize="13"):
                ctrl_role = IdentityAndAccessManagementIamRole("Controller role\n(Pod Identity:\nkarpenter/karpenter)")
                node_role = IdentityAndAccessManagementIamRole("Node role\nkarpenter-node-mgmt\n+ EKS access entry")
                rules = Eventbridge("EventBridge rules\nspot interruption, rebalance,\nstate change, AWS Health")
                queue = SimpleQueueServiceSqs("SQS queue\nkarpenter-mgmt")

            with box("EKS cluster mgmt", *CLUSTER, fontsize="15"):
                with box("any namespace", *NS, style="rounded,dashed", fontsize="12"):
                    pending = Pod("Pending pod\n(doesn't fit on\nthe system nodes)")
                with box("namespace karpenter", *NS, fontsize="12"):
                    karpenter = Custom("Karpenter controller", icon("karpenter"))
                    nodeclaim = CRD("NodeClaim\n(one per node)")
                new_node = Node("New node\nRegistered → Ready")

            with box("Created by Karpenter at runtime (private subnets of mlqube-mgmt)", *RUNTIME, fontsize="13"):
                template = EC2Ami("Launch template\n+ AL2023 AMI (from SSM)")
                profile = IdentityAndAccessManagementIamRole("Instance profile\n(wraps the node role)")
                instance = EC2SpotInstance("EC2 instance\ne.g. m6i.large, spot")

        # provisioning
        pending >> Edge(label="1. unschedulable", **FLOW) >> karpenter
        nodepool >> Edge(label="2. rules and limits", **CONFIG) >> karpenter
        nodeclass >> Edge(**CONFIG) >> karpenter
        karpenter >> Edge(label="3. creates", **FLOW) >> nodeclaim
        karpenter >> Edge(label="credentials", **IDENTITY) >> ctrl_role
        karpenter >> Edge(label="4. creates", **FLOW) >> template
        karpenter >> Edge(**FLOW) >> profile
        karpenter >> Edge(label="5. CreateFleet\n(cheapest spot that fits)", **FLOW) >> instance
        profile >> Edge(label="iam:PassRole", **IDENTITY) >> node_role
        instance >> Edge(label="6. boots, joins\n(access entry)", **FLOW) >> new_node
        new_node >> Edge(label="7. pod scheduled", **FLOW) >> pending

        # interruption
        instance >> Edge(label="2-minute spot warning", **INTERRUPT) >> rules
        rules >> Edge(**INTERRUPT) >> queue
        queue >> Edge(label="cordon, drain,\nstart replacement", **INTERRUPT) >> karpenter

        # consolidation
        karpenter >> Edge(label="terminates empty or\nunderused nodes", **CONSOLIDATE) >> instance

        legend(
            d,
            [
                ("#2E7D32", "━━━", "Provisioning: a pending pod gets a new node (steps 1–7)"),
                ("#6A1B9A", "╍╍╍", "Configuration from gitops: what Karpenter may start"),
                ("#FF9900", "• • •", "AWS identity: Pod Identity for the controller, node role for the machine"),
                ("#C62828", "╍╍╍", "Spot interruption: replace the node before AWS takes it back"),
                ("#757575", "╍╍╍", "Consolidation: remove nodes that are empty or can be packed tighter"),
            ],
        )


# ------------------------------------------------------------------------------------- Ingress
def ingress_flow() -> None:
    with diagram(
        "From Ingress to https://argocd.mlqube.click: AWS Load Balancer Controller + ExternalDNS",
        "ingress-flow",
    ) as d:
        with box("Your laptop (Tailscale on)", *LAPTOP, fontsize="13"):
            browser = Client("Browser\nhttps://argocd.mlqube.click")

        with box("AWS us-west-2", *AWS, fontsize="16"):
            with box("Created by Terraform", *TERRAFORM, fontsize="13"):
                lbc_role = IdentityAndAccessManagementIamRole("Role: load balancer\ncontroller (Pod Identity)")
                dns_role = IdentityAndAccessManagementIamRole("Role: ExternalDNS\n(Pod Identity, private zone only)")
                cert = CertificateManager("ACM certificate\n*.mlqube.click\n(base layer)")
                zone = Route53HostedZone("Private zone\nmlqube.click\n(network layer)")
                router = VPN("Tailscale router\n(network layer)")

            with box("EKS cluster mgmt", *CLUSTER, fontsize="15"):
                with box("namespace argocd (example app)", *NS, fontsize="12"):
                    ingress = Ing("Ingress argocd\nhost argocd.mlqube.click\nscheme internal")
                    svc = SVC("Service\nargocd-server")
                    pods = Argocd("argocd-server pods")
                with box("namespace kube-system", *NS, fontsize="12"):
                    lbc = ElbApplicationLoadBalancer("AWS Load Balancer\nController")
                    edns = ExternalDns("ExternalDNS")

            with box("Created by the add-ons at runtime", *RUNTIME, fontsize="13"):
                alb = ElbApplicationLoadBalancer("Internal ALB\nHTTPS 443, target group,\nsecurity group")
                record = Route53HostedZone("Record\nargocd.mlqube.click → ALB\n(+ TXT owner record)")

        ingress >> Edge(label="1. watches", **FLOW) >> lbc
        lbc >> Edge(label="credentials", **IDENTITY) >> lbc_role
        lbc >> Edge(label="2. creates / updates", **FLOW) >> alb
        cert >> Edge(label="TLS", **CONFIG) >> alb
        ingress >> Edge(label="3. watches", **DNS) >> edns
        edns >> Edge(label="credentials", **IDENTITY) >> dns_role
        edns >> Edge(label="4. writes record", **DNS) >> record
        record >> Edge(style="dotted", color="#00838F") >> zone

        browser >> Edge(label="5. Tailscale tunnel", **USER) >> router
        router >> Edge(label="DNS: resolves the name\nin the private zone", **DNS) >> zone
        router >> Edge(label="6. HTTPS", **USER) >> alb
        alb >> Edge(label="7. forwards (pod IPs)", **USER) >> svc
        svc >> Edge(**USER) >> pods

        legend(
            d,
            [
                ("#2E7D32", "━━━", "Load balancer controller: Ingress → internal ALB"),
                ("#00838F", "╍╍╍", "ExternalDNS: Ingress host → record in the private zone"),
                ("#FF9900", "• • •", "AWS identity through EKS Pod Identity (no keys)"),
                ("#6A1B9A", "╍╍╍", "Certificate attached to the ALB listener"),
                ("#5E35B1", "━━━", "You opening the URL through Tailscale"),
            ],
        )


# ------------------------------------------------------------------------------------- DNS
def dns_lookup() -> None:
    with diagram(
        "How argocd.mlqube.click becomes a private IP: the record is written, then looked up",
        "dns-lookup",
    ) as d:
        with box("Your laptop", *LAPTOP, fontsize="13"):
            browser = Client("Browser\nargocd.mlqube.click ?")
            ts = VPN("Tailscale client\nsplit DNS: *.mlqube.click\n→ ask 10.10.0.2")

        with box("Internet", *NS, style="rounded,dashed", fontsize="12"):
            public = Route53HostedZone("Public zone mlqube.click\nonly certificate validation;\nno argocd record")

        with box("AWS us-west-2 · VPC mlqube-mgmt 10.10.0.0/16", *AWS, fontsize="15"):
            router = VPN("mlqube-router\n(forwards the DNS question\ninto the VPC)")
            resolver = Route53("VPC resolver 10.10.0.2\n(Route 53 Resolver,\nVPC base + 2)")
            zone = Route53HostedZone(
                "Private zone mlqube.click\n(attached to both VPCs)\nargocd  A alias → internal-k8s-…elb\nargocd  TXT owner=mgmt"
            )

            with box("EKS cluster mgmt", *CLUSTER, fontsize="14"):
                ingress = Ing("Ingress argocd-server\nhost: argocd.mlqube.click\nstatus: internal-k8s-…elb")
                lbc = ElbApplicationLoadBalancer("AWS Load Balancer\nController")
                edns = ExternalDns("ExternalDNS")

            with box("Internal ALB (private subnets, 2 AZs)", *RUNTIME, fontsize="13"):
                alb = ElbApplicationLoadBalancer("ALB DNS name\ninternal-k8s-mlqubemgmt-…\n.elb.amazonaws.com")
                ip_a = VPCElasticNetworkInterface("10.10.12.34\n(us-west-2a)")
                ip_b = VPCElasticNetworkInterface("10.10.45.67\n(us-west-2b)")

        # write path: who puts the record there
        lbc >> Edge(label="W1. creates", **FLOW) >> alb
        lbc >> Edge(label="W2. writes ALB name\ninto Ingress status", **FLOW) >> ingress
        ingress >> Edge(label="W3. host + ALB name", **DNS) >> edns
        edns >> Edge(label="W4. Route 53 API: alias + TXT", **DNS) >> zone
        alb >> Edge(style="dotted", color="#1565C0") >> [ip_a, ip_b]

        # read path: the lookup
        browser >> Edge(label="1. what is\nargocd.mlqube.click?", **USER) >> ts
        ts >> Edge(label="2. tunnel to 10.10.0.2", **USER) >> router
        router >> Edge(label="3. asks from inside the VPC", **USER) >> resolver
        resolver >> Edge(label="4. zone attached to this VPC?\nyes → record argocd", **USER) >> zone
        resolver >> Edge(label="5. alias → ALB's current IPs", **USER) >> alb
        public >> Edge(label="not asked for *.mlqube.click", style="dashed", color="#9E9E9E") >> ts

        legend(
            d,
            [
                ("#2E7D32", "━━━", "W1–W2: the load balancer controller creates the ALB and records its DNS name"),
                ("#00838F", "╍╍╍", "W3–W4: ExternalDNS writes argocd → ALB (alias) into the private zone"),
                ("#5E35B1", "━━━", "1–5: the lookup; answer = 10.10.12.34, 10.10.45.67 (back the same way)"),
                ("#9E9E9E", "╍╍╍", "The public zone is never asked for these names"),
            ],
        )


if __name__ == "__main__":
    karpenter_flow()
    ingress_flow()
    dns_lookup()
    for p in (
        "karpenter-flow.png",
        "ingress-flow.png",
        "dns-lookup.png",
    ):
        f = IMAGES / p
        print(f"wrote {f} ({f.stat().st_size // 1024} KB)")
