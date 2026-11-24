"""App-of-apps diagram: how Argo CD in the mgmt cluster installs everything from this repository.

Solid = exists after the first platform apply (Argo CD and the root Application);
dashed = add-ons that arrive as files are added under clusters/mgmt.

Requirements: Python with `diagrams`, and Graphviz (`dot`) on PATH
(on Windows the default Graphviz install path is added automatically).

Run from the repository root:
    python docs/diagrams/platform/app_of_apps.py

Writes:
    docs/platform/images/app-of-apps.png
"""

from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent  # the .github repository
IMAGES = REPO / "docs/platform/images"  # rendered pictures, embedded in docs/platform

_GRAPHVIZ_WIN = Path(r"C:\Program Files\Graphviz\bin")
if _GRAPHVIZ_WIN.is_dir() and str(_GRAPHVIZ_WIN) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_GRAPHVIZ_WIN}{os.pathsep}{os.environ.get('PATH', '')}"

from diagrams import Cluster, Diagram, Edge  # noqa: E402
from diagrams.aws.compute import EC2SpotInstance, ElasticKubernetesService  # noqa: E402
from diagrams.aws.network import ElbApplicationLoadBalancer, Route53HostedZone  # noqa: E402
from diagrams.custom import Custom  # noqa: E402
from diagrams.k8s.ecosystem import ExternalDns, Helm  # noqa: E402
from diagrams.k8s.others import CRD  # noqa: E402
from diagrams.onprem.ci import GithubActions  # noqa: E402
from diagrams.onprem.gitops import Argocd  # noqa: E402
from diagrams.onprem.iac import Terraform  # noqa: E402
from diagrams.onprem.logging import Loki  # noqa: E402
from diagrams.onprem.monitoring import Grafana, Prometheus  # noqa: E402
from diagrams.onprem.vcs import Github  # noqa: E402

FONT = "Segoe UI"
GRAPH = {
    "bgcolor": "white",
    "pad": "0.5",
    "nodesep": "0.4",
    "ranksep": "0.9",
    "fontname": FONT,
    "fontsize": "26",
    "labelloc": "t",
    "dpi": "86",
    # curved lines: Graphviz can't place labels on orthogonal (right-angle) edges
    "splines": "spline",
}
NODE = {"fontname": FONT, "fontsize": "12", "fontcolor": "#212121"}
EDGE = {"fontname": FONT, "fontsize": "11", "color": "#757575", "fontcolor": "#424242"}

INFRA = ("#ECEFF1", "#455A64")
GITHUB = ("#F3E5F5", "#6A1B9A")
FOLDER = ("#FFFFFF", "#8E24AA")
UPSTREAM = ("#E3F2FD", "#1565C0")
AWS = ("#FFF8E1", "#FF9900")
CLUSTER = ("#E8F5E9", "#43A047")
ARGO_NS = ("#FFF3E0", "#EF6C00")
ADDON_NS = ("#FFFFFF", "#9E9E9E")

ONCE = {"color": "#455A64", "penwidth": "1.8"}
PULL = {"color": "#6A1B9A", "penwidth": "2.2"}
CREATE = {"color": "#EF6C00", "penwidth": "1.8"}
NEXT = {"color": "#EF6C00", "style": "dashed"}
CHART = {"color": "#1565C0", "style": "dashed"}
AWSAPI = {"color": "#FF9900", "style": "dotted"}

LEGEND_ROWS = [
    ("#455A64", "━━━", "Once per platform build: Terraform installs Argo CD and the root Application"),
    ("#6A1B9A", "━━━", "Argo CD pulls this repository every few minutes (read-only deploy key)"),
    ("#EF6C00", "━━━", "root applies every file in clusters/mgmt (exists now)"),
    ("#EF6C00", "╍╍╍", "Child Applications and the add-ons they install (as files are added)"),
    ("#1565C0", "╍╍╍", "Helm charts fetched from upstream, at the pinned version"),
    ("#FF9900", "• • •", "Add-ons manage AWS resources (load balancers, DNS records, nodes)"),
]


def box(label: str, fill: str, line: str, style: str = "rounded", fontsize: str = "14") -> Cluster:
    return Cluster(
        label,
        graph_attr={
            "bgcolor": fill,
            "pencolor": line,
            "penwidth": "1.6",
            "style": style,
            "fontname": FONT,
            "fontsize": fontsize,
            "labeljust": "l",
            "margin": "18",
        },
    )


def icon(name: str) -> str:
    return str(HERE.parent / "icons" / f"{name}.png")  # shared docs/diagrams/icons


def legend_below(diagram, cells: list[str], columns: int = 2) -> None:
    """Draw the legend under the whole picture, centred, with its entries in `columns` columns.

    Each cell is an HTML `<td>…</td><td>…</td>` pair (sample, text). Everything declared so far is
    wrapped in an invisible frame (a cluster) whose bottom label is the legend: a legend beside a
    wide picture makes the picture smaller, below it uses width that is already there.
    Call it last, after every node and edge is declared. Shared by every platform diagram.
    """
    per_col = -(-len(cells) // columns)
    cols = [cells[i:i + per_col] for i in range(0, len(cells), per_col)]
    body = "".join(
        '<td valign="top"><table border="0" cellborder="0" cellspacing="4" cellpadding="3">'
        + "".join(f"<tr>{c}</tr>" for c in col)
        + "</table></td>"
        for col in cols
    )
    label = (
        '<<table border="1" color="#BDBDBD" cellborder="0" cellspacing="4" cellpadding="4" bgcolor="white">'
        f'<tr><td colspan="{len(cols)}" align="left"><font point-size="15"><b>Legend</b></font></td></tr>'
        f"<tr>{body}</tr></table>>"
    )
    dot = diagram.dot
    dot.body[:] = [
        "\tsubgraph cluster_legend_frame {\n",
        *dot.body,
        # Attributes last: nested clusters copy their parent's attributes when they are declared,
        # so set before the body, labelloc=b would move every box title to the bottom.
        f"\t\tlabel={label}\n",
        f'\t\tlabelloc=b labeljust=c pencolor=white style=solid margin=12 fontsize=13 fontname="{FONT}"\n',
        "\t}\n",
    ]


def line_cells(rows: list[tuple[str, str, str]]) -> list[str]:
    """Legend cells for edge styles: (colour, line sample, text)."""
    return [
        f'<td><font color="{c}" point-size="16"><b>{line}</b></font></td>'
        f'<td align="left"><font point-size="13">{text}</font></td>'
        for c, line, text in rows
    ]


def legend(diagram) -> None:
    legend_below(diagram, line_cells(LEGEND_ROWS))


def app_of_apps() -> None:
    with Diagram(
        "App of apps: how Argo CD installs the mgmt cluster from this repository",
        filename=str(IMAGES / "app-of-apps"),
        outformat="png",
        show=False,
        direction="LR",
        graph_attr=GRAPH,
        node_attr=NODE,
        edge_attr=EDGE,
    ) as d:
        # ------------------------------------------------------------ infrastructure (once)
        with box("mlqube/infrastructure · layer addons-mgmt", *INFRA):
            gha = GithubActions("GitHub Actions\nplatform: all / addons-mgmt\n(joins the tailnet)")
            tf = Terraform("Terraform\nlive/platform/addons/mgmt")

        # ------------------------------------------------------------ this repository
        with box("mlqube/gitops (this repository, branch main)", *GITHUB):
            repo = Github("git@github.com:mlqube/gitops.git")
            with box("clusters/mgmt/  (one folder per add-on)", *FOLDER, style="rounded,dashed", fontsize="12"):
                small = {"width": "0.7", "height": "0.95", "fontsize": "11"}
                f_lbc = CRD("aws-load-balancer-controller/", **small)
                f_dns = CRD("external-dns/", **small)
                f_karp = CRD("karpenter/", **small)
                f_obs = CRD("observability/ (later)", **small)

        # ------------------------------------------------------------ upstream charts
        with box("Upstream Helm chart repositories", *UPSTREAM):
            charts = Helm("Pinned chart versions\n(aws/eks-charts, kubernetes-sigs,\nkarpenter, prometheus-community, grafana)")

        # ------------------------------------------------------------ AWS / mgmt cluster
        with box("AWS us-west-2", *AWS, fontsize="16"):
            with box("EKS cluster mgmt", *CLUSTER, fontsize="15"):
                with box("namespace argocd", *ARGO_NS, fontsize="13"):
                    argocd = Argocd("Argo CD\n(controller, repo server, UI)")
                    root = Argocd("Application root\nsource: clusters/mgmt\nauto-sync · prune · self-heal")
                    a_lbc = Argocd("Application\naws-load-balancer-controller")
                    a_dns = Argocd("Application\nexternal-dns")
                    a_karp = Argocd("Application\nkarpenter")
                    a_obs = Argocd("Applications\nprometheus · grafana · loki")

                with box("namespace kube-system", *ADDON_NS, style="rounded,dashed", fontsize="12"):
                    lbc = ElbApplicationLoadBalancer("AWS Load Balancer\nController")
                    dns = ExternalDns("ExternalDNS")
                with box("namespace karpenter", *ADDON_NS, style="rounded,dashed", fontsize="12"):
                    karp = Custom("Karpenter", icon("karpenter"))
                with box("namespace monitoring (Phase 1)", *ADDON_NS, style="rounded,dashed", fontsize="12"):
                    prom = Prometheus("Prometheus")
                    graf = Grafana("Grafana")
                    loki = Loki("Loki")

            api = ElasticKubernetesService("mgmt API\n(private)")
            alb = ElbApplicationLoadBalancer("Internal ALB\nargocd.mlqube.click …")
            zone = Route53HostedZone("Private zone\nmlqube.click")
            nodes = EC2SpotInstance("Nodes on demand\n(CPU, GPU)")

        # ------------------------------------------------------------ edges
        gha >> Edge(label="1. terraform apply", **ONCE) >> tf
        tf >> Edge(label="2. helm install argo-cd\n+ root Application\n(through Tailscale)", **ONCE) >> api
        api >> Edge(**ONCE) >> argocd

        # data flows from Git into the cluster (Argo CD fetches it)
        repo >> Edge(label="3. fetched by Argo CD every ~3 min\n(read-only deploy key)", **PULL) >> argocd
        argocd >> Edge(label="runs", **CREATE) >> root
        f_dns >> Edge(label="4. root reads every file\nin clusters/mgmt", **CREATE) >> root
        for f in (f_lbc, f_karp, f_obs):
            f >> Edge(**CREATE) >> root

        root >> Edge(label="5. one child Application per file", **NEXT) >> a_lbc
        root >> Edge(**NEXT) >> [a_dns, a_karp, a_obs]

        a_lbc >> Edge(label="6. installs chart", **NEXT) >> lbc
        a_dns >> Edge(**NEXT) >> dns
        a_karp >> Edge(**NEXT) >> karp
        a_obs >> Edge(**NEXT) >> [prom, graf, loki]

        charts >> Edge(label="chart + pinned version", **CHART) >> a_karp
        charts >> Edge(**CHART) >> [a_lbc, a_dns, a_obs]

        lbc >> Edge(label="creates", **AWSAPI) >> alb
        dns >> Edge(label="writes records", **AWSAPI) >> zone
        karp >> Edge(label="starts / stops", **AWSAPI) >> nodes

        legend(d)


if __name__ == "__main__":
    app_of_apps()
    p = IMAGES / "app-of-apps.png"
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")
