"""Component diagrams for the EKS cluster layers (mgmt and wl-nonprod).

Each diagram shows what the layer creates now with Terraform (solid boxes) and what is
installed later through Argo CD (dashed boxes, labelled with the roadmap phase).

Requirements: Python with `diagrams` and `pillow`, and Graphviz (`dot`) on PATH.
On Windows the default Graphviz install path is added automatically.

Run from the repository root:
    python docs/diagrams/platform/cluster_diagrams.py

Writes:
    docs/platform/images/eks-mgmt-components.png
    docs/platform/images/eks-wl-nonprod-components.png
"""

from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent  # the .github repository
IMAGES = REPO / "docs/platform/images"  # rendered pictures, embedded in docs/platform
os.chdir(HERE)  # icon paths are relative to this folder

_GRAPHVIZ_WIN = Path(r"C:\Program Files\Graphviz\bin")
if _GRAPHVIZ_WIN.is_dir() and str(_GRAPHVIZ_WIN) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_GRAPHVIZ_WIN}{os.pathsep}{os.environ.get('PATH', '')}"

from diagrams import Cluster, Diagram, Edge  # noqa: E402
from diagrams.aws.compute import EC2Instances, EC2SpotInstance, ElasticKubernetesService  # noqa: E402
from diagrams.aws.network import ElbApplicationLoadBalancer, VPCElasticNetworkInterface  # noqa: E402
from diagrams.aws.security import IdentityAndAccessManagementIamAWSSts, IdentityAndAccessManagementIamRole  # noqa: E402
from diagrams.aws.storage import ElasticBlockStoreEBSVolume  # noqa: E402
from diagrams.custom import Custom  # noqa: E402
from diagrams.generic.network import VPN  # noqa: E402
from diagrams.k8s.compute import DS  # noqa: E402
from diagrams.k8s.controlplane import KProxy  # noqa: E402
from diagrams.k8s.ecosystem import ExternalDns  # noqa: E402
from diagrams.k8s.group import NS  # noqa: E402
from diagrams.onprem.ci import GithubActions  # noqa: E402
from diagrams.onprem.client import User  # noqa: E402
from diagrams.onprem.container import Gvisor  # noqa: E402
from diagrams.onprem.dns import Coredns  # noqa: E402
from diagrams.onprem.gitops import Argocd  # noqa: E402
from diagrams.onprem.logging import Loki  # noqa: E402
from diagrams.onprem.mlops import Mlflow  # noqa: E402
from diagrams.onprem.monitoring import Grafana, Prometheus  # noqa: E402

FONT = "Segoe UI"

GRAPH = {
    "bgcolor": "white",
    "pad": "0.5",
    "nodesep": "0.45",
    "ranksep": "0.9",
    "fontname": FONT,
    "fontsize": "28",
    "labelloc": "t",
    "compound": "true",
    "dpi": "110",
}
NODE = {"fontname": FONT, "fontsize": "12", "fontcolor": "#212121"}
EDGE = {"fontname": FONT, "fontsize": "11", "color": "#757575", "fontcolor": "#424242"}


def icon(name: str) -> str:
    # Absolute path: Graphviz resolves relative image paths from the output folder, not this one.
    return str(HERE.parent / "icons" / f"{name}.png")  # shared docs/diagrams/icons


def box(title: str, fill: str, border: str, dashed: bool = False, fontsize: str = "14") -> Cluster:
    """A labelled group. Solid = created by this layer now; dashed = installed later."""
    return Cluster(
        title,
        graph_attr={
            "bgcolor": fill,
            "pencolor": border,
            "penwidth": "2",
            "style": "rounded,dashed" if dashed else "rounded",
            "fontname": f"{FONT} Semibold",
            "fontsize": fontsize,
            "fontcolor": "#212121",
            "labeljust": "l",
            "margin": "16",
        },
    )


NOW = ("#E8F5E9", "#2E7D32")      # green: created by this layer now (Terraform)
LATER = ("#FAFAFA", "#9E9E9E")    # grey dashed: installed later through Argo CD
AWS = ("#FFF8E1", "#FF9900")      # AWS account / VPC
ACCESS = ("#E3F2FD", "#1565C0")   # who connects


def access_lane():
    with box("Who connects", *ACCESS):
        operator = User("Operator\n(Identity Center admin)")
        tailscale = VPN("Tailscale tunnel\n(ADR-0011)")
        ci = GithubActions("GitHub Actions\n(CI apply role)")
    return operator, tailscale, ci


def core_cluster(cluster: str, vpc: str, cidr: str):
    """Control plane, system nodes, core add-ons and the add-on IAM role: created now."""
    with box(f"VPC {vpc} · {cidr} · private subnets in 2 AZs", *AWS, fontsize="16"):
        with box(f"EKS cluster: {cluster} (Kubernetes 1.36)", "#FFFFFF", "#FF9900", fontsize="16"):
            with box("Created by this layer (Terraform)", *NOW):
                control_plane = ElasticKubernetesService("EKS control plane\n(AWS-managed)\nprivate API endpoint")
                with box("System node group", "#FFFFFF", "#2E7D32", fontsize="12"):
                    nodes = EC2SpotInstance("2 spot nodes\nt3.large-class · AL2023")
                with box("Managed add-ons", "#FFFFFF", "#2E7D32", fontsize="12"):
                    cni = VPCElasticNetworkInterface("VPC CNI\nprefix delegation\nnetwork policy")
                    dns = Coredns("CoreDNS")
                    proxy = KProxy("kube-proxy")
                    pod_identity = IdentityAndAccessManagementIamAWSSts("Pod Identity\nagent")
                    ebs = ElasticBlockStoreEBSVolume("EBS CSI driver")
    with box("IAM (created by this layer)", *NOW, fontsize="12"):
        ebs_role = IdentityAndAccessManagementIamRole(f"{cluster}-ebs-csi\n(Pod Identity role)")
    return control_plane, nodes, cni, dns, proxy, pod_identity, ebs, ebs_role


def wire_access(operator, tailscale, ci, control_plane, ebs, ebs_role):
    operator >> Edge(label="kubectl", color="#1565C0") >> tailscale
    tailscale >> Edge(label="private endpoint", color="#1565C0") >> control_plane
    ci >> Edge(xlabel="creates via\nAWS APIs", color="#1565C0", style="dashed") >> control_plane
    ebs >> Edge(label="temporary credentials", color="#6A1B9A", style="dashed") >> ebs_role


def legend(diagram: Diagram) -> None:
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
            '<tr><td colspan="2" align="left"><b>Legend</b></td></tr>'
            f'<tr><td width="30" height="16" bgcolor="{NOW[0]}" color="{NOW[1]}" border="2"></td>'
            '<td align="left">Created by this layer now (Terraform)</td></tr>'
            f'<tr><td width="30" height="16" bgcolor="{LATER[0]}" color="{LATER[1]}" border="2" style="dashed"></td>'
            '<td align="left">Installed later through Argo CD (phase in the box title)</td></tr>'
            "</table>>"
        ),
    )


def mgmt() -> None:
    out = IMAGES / "eks-mgmt-components"
    with Diagram(
        "mgmt cluster: the platform's control plane (no tenant workloads)",
        filename=str(out),
        outformat="png",
        show=False,
        direction="TB",
        graph_attr=GRAPH,
        node_attr=NODE,
        edge_attr=EDGE,
    ) as d:
        operator, tailscale, ci = access_lane()
        control_plane, nodes, cni, dns, proxy, pod_identity, ebs, ebs_role = core_cluster(
            "mgmt", "mlqube-mgmt", "10.10.0.0/16"
        )
        with box("Later · Phase 1 · platform add-ons (both clusters)", *LATER, dashed=True):
            first_later = Custom("Karpenter", icon("karpenter"))
            ElbApplicationLoadBalancer("AWS Load Balancer\nController")
            ExternalDns("ExternalDNS")
            Custom("cert-manager", icon("cert-manager"))
            Custom("External Secrets", icon("external-secrets"))
            Custom("Kyverno", icon("kyverno"))
        with box("Later · mgmt only", *LATER, dashed=True):
            with box("Phase 1 · GitOps hub", "#FFFFFF", "#9E9E9E", dashed=True, fontsize="12"):
                mgmt_first = Argocd("Argo CD\n(manages both clusters)")
            with box("Phase 1 · central observability", "#FFFFFF", "#9E9E9E", dashed=True, fontsize="12"):
                Prometheus("Prometheus")
                Grafana("Grafana")
                Loki("Loki")
                Custom("OpenTelemetry\nCollector", icon("opentelemetry"))
            with box("Phase 2 · platform APIs", "#FFFFFF", "#9E9E9E", dashed=True, fontsize="12"):
                Custom("Crossplane\nTenant · MLProject", icon("crossplane"))
            with box("Phase 4 · tracking", "#FFFFFF", "#9E9E9E", dashed=True, fontsize="12"):
                Mlflow("MLflow (shared)")
            with box("Phase 6 · portal & cost", "#FFFFFF", "#9E9E9E", dashed=True, fontsize="12"):
                Custom("Backstage", icon("backstage"))
                Custom("OpenCost", icon("opencost"))
        wire_access(operator, tailscale, ci, control_plane, ebs, ebs_role)
        nodes >> Edge(style="invis") >> first_later >> Edge(style="invis") >> mgmt_first
        legend(d)


def wl_nonprod() -> None:
    out = IMAGES / "eks-wl-nonprod-components"
    with Diagram(
        "wl-nonprod cluster: where tenants' ML work runs",
        filename=str(out),
        outformat="png",
        show=False,
        direction="TB",
        graph_attr=GRAPH,
        node_attr=NODE,
        edge_attr=EDGE,
    ) as d:
        operator, tailscale, ci = access_lane()
        control_plane, nodes, cni, dns, proxy, pod_identity, ebs, ebs_role = core_cluster(
            "wl-nonprod", "mlqube-nonprod", "10.20.0.0/16"
        )
        with box("Later · Phase 1 · platform add-ons (both clusters)", *LATER, dashed=True):
            first_later = Custom("Karpenter", icon("karpenter"))
            ElbApplicationLoadBalancer("AWS Load Balancer\nController")
            ExternalDns("ExternalDNS")
            Custom("cert-manager", icon("cert-manager"))
            Custom("External Secrets", icon("external-secrets"))
            Custom("Kyverno", icon("kyverno"))
        with box("Later · wl-nonprod only", *LATER, dashed=True):
            with box("Phase 1 · Karpenter NodePools", "#FFFFFF", "#9E9E9E", dashed=True, fontsize="12"):
                wl_first = EC2Instances("CPU nodes")
                EC2SpotInstance("GPU nodes per tenant\n(spot)")
                DS("NVIDIA GPU Operator\n(DaemonSet)")
            with box("Phase 1a / 3 · ML jobs", "#FFFFFF", "#9E9E9E", dashed=True, fontsize="12"):
                Custom("Argo Workflows\n(Python + Hera)", icon("argo"))
                Custom("Kueue\nGPU queues per tenant", icon("kueue"))
            with box("Phase 2 · tenancy", "#FFFFFF", "#9E9E9E", dashed=True, fontsize="12"):
                NS("Tenant namespaces\nretail-1042-*")
                Custom("Capsule", icon("capsule"))
                Gvisor("gVisor sandboxed\nCPU nodes")
            with box("Phase 5–6 · notebooks & staging", "#FFFFFF", "#9E9E9E", dashed=True, fontsize="12"):
                Custom("Notebooks", icon("jupyter"))
                Custom("KServe staging\nendpoints", icon("kserve"))
        wire_access(operator, tailscale, ci, control_plane, ebs, ebs_role)
        nodes >> Edge(style="invis") >> first_later >> Edge(style="invis") >> wl_first
        legend(d)


if __name__ == "__main__":
    mgmt()
    wl_nonprod()
    for name in ("mgmt", "wl-nonprod"):
        p = IMAGES / f"eks-{name}-components.png"
        print(f"wrote {p} ({p.stat().st_size // 1024} KB)")
