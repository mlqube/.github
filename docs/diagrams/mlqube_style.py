"""Shared style and rendering helpers for the MlQube architecture diagrams.

Every view script (mlqube_1_*.py ... mlqube_5_*.py) imports this module, so all
views share swimlane colours, edge styles, legend layout and the render pipeline.

Requirements:
    python -m venv .venv && .venv/Scripts/pip install diagrams pillow   # Windows
    python -m venv .venv && .venv/bin/pip install diagrams pillow       # macOS/Linux
    Graphviz (`dot`, `neato`) installed. On Windows the default install path is
    added to PATH below.

Rendering (see `publish`):
    1. `dot` places nodes and swimlanes from a column skeleton only. Every view
       lists its nodes in columns, left to right; each column is one Graphviz
       rank. Inside a column, nodes declared first are drawn lowest.
    2. `neato -n2` keeps those positions and routes the semantic edges as
       direct splines that avoid nodes. (`dot` alone routes long edges around
       whole swimlanes, which produces loops across the slide.)
    3. PNG at 200 dpi, plus an SVG with the icons embedded as data URIs so it
       renders anywhere (e.g. on GitHub).
"""

from __future__ import annotations

import base64
import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)  # Graphviz resolves the relative icon paths from here

_GRAPHVIZ_WIN = Path(r"C:\Program Files\Graphviz\bin")
if _GRAPHVIZ_WIN.is_dir() and str(_GRAPHVIZ_WIN) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_GRAPHVIZ_WIN}{os.pathsep}{os.environ.get('PATH', '')}"

from diagrams import Cluster, Diagram, Edge, Node  # noqa: E402

FONT = "Segoe UI"
GREY = "#9E9E9E"

# Swimlane colours (fill, border); the same lane keeps its colour in every view.
LANE = {
    "people": ("#FFF8E1", "#F9A825"),
    "edge": ("#E3F2FD", "#1E88E5"),
    "aws": ("#FAFAFA", "#FF9900"),
    "mgmt": ("#E8F5E9", "#43A047"),
    "nonprod": ("#FFF3E0", "#FB8C00"),
    "prod": ("#FCE4EC", "#D81B60"),
    "shared": ("#EDE7F6", "#5E35B1"),
    "gov": ("#E0F2F1", "#00897B"),
    "consumers": ("#F3F4F6", "#607D8B"),
    "inner": ("#FFFFFF", "#9E9E9E"),
}

LANE_NAMES = {
    "people": "People &amp; business units",
    "edge": "Corporate edge &amp; identity",
    "aws": "AWS account · region",
    "mgmt": "Management cluster (shared-services VPC)",
    "nonprod": "Workload cluster: non-prod",
    "prod": "Workload cluster: prod",
    "shared": "Shared AWS services",
    "gov": "Governance &amp; FinOps",
    "consumers": "Consumers of models",
}

# Flow colours, shared by all views (the enterprise view numbers them ①-⑦).
BLUE = "#1565C0"    # jobs / training
GREEN = "#2E7D32"   # MLflow tracking and registry
PURPLE = "#6A1B9A"  # promotion and serving
ORANGE = "#EF6C00"  # GitOps
BROWN = "#6D4C41"   # Crossplane provisioning
TEAL = "#00838F"    # identity / SSO
RED = "#C62828"     # metrics and cost
SLATE = "#455A64"   # authorization and policy

CIRCLED = {i: chr(0x2460 + i - 1) for i in range(1, 21)}
LINE_SAMPLE = {"bold": "━━━━", "solid": "━━━━", "dashed": "╍╍╍╍", "dotted": "• • • •"}


def icon(name: str) -> str:
    return f"icons/{name}.png"


def lane(title: str, key: str, fontsize: str = "18", **extra: str) -> Cluster:
    fill, border = LANE[key]
    attrs = {
        "bgcolor": fill,
        "pencolor": border,
        "penwidth": "2",
        "fontname": f"{FONT} Semibold",
        "fontsize": fontsize,
        "fontcolor": "#212121",
        "labeljust": "l",
        "style": "rounded",
        # extra vertical margin: node labels hang below the icons
        "margin": "20,44",
    }
    attrs.update(extra)
    return Cluster(title, graph_attr=attrs)


def box(title: str, fontsize: str = "14") -> Cluster:
    """A white inner group inside a swimlane."""
    return lane(title, "inner", fontsize=fontsize)


def step(n: int, colour: str, tooltip: str = "", style: str = "bold", **extra: str) -> Edge:
    """A numbered flow edge; the legend spells out what each number means."""
    attrs = {
        "color": colour,
        "fontcolor": colour,
        "style": style,
        "penwidth": "2.4",
        "fontname": f"{FONT} Bold",
        "fontsize": "20",
        "label": CIRCLED[n],
        "tooltip": f"{CIRCLED[n]} {' '.join(tooltip.split())}".strip(),
        "constraint": "false",
    }
    attrs.update(extra)
    return Edge(**attrs)


def link(text: str, colour: str, style: str = "bold", **extra: str) -> Edge:
    """A flow edge with a short text label (for the high-level view)."""
    attrs = {
        "color": colour,
        "fontcolor": colour,
        "style": style,
        "penwidth": "2.4",
        "fontname": f"{FONT} Semibold",
        "fontsize": "15",
        "label": text,
        "constraint": "false",
    }
    attrs.update(extra)
    return Edge(**attrs)


def plain(**extra: str) -> Edge:
    attrs = {"color": GREY, "penwidth": "1.2", "arrowsize": "0.7", "constraint": "false"}
    attrs.update(extra)
    return Edge(**attrs)


GRAPH_ATTR = {
    "bgcolor": "white",
    "rankdir": "LR",
    "splines": "spline",
    "nodesep": "0.55",
    "ranksep": "1.3",
    "pad": "0.6",
    "fontname": FONT,
    "fontsize": "16",
    "compound": "true",
    "newrank": "true",
    "dpi": "200",
}
NODE_ATTR = {
    "fontname": FONT,
    "fontsize": "13",
    "fontcolor": "#212121",
    "height": "1.15",
    "width": "1.15",
    "imagescale": "true",
}
EDGE_ATTR = {"fontname": FONT, "fontsize": "12", "arrowsize": "0.8"}


def new_diagram(name: str, title: str, subtitle: str, **graph_attr: str) -> Diagram:
    """Create a diagram; `publish` renders it (diagrams' own render is skipped)."""
    diagram = Diagram(
        title,
        filename=name,
        outformat="png",
        show=False,
        direction="LR",
        graph_attr={**GRAPH_ATTR, **graph_attr},
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    )
    diagram.render = lambda: Path(diagram.filename).write_text(diagram.dot.source, encoding="utf-8")
    # Graph attributes, not a body statement: `legend_below` wraps the whole body in a frame.
    diagram.dot.graph_attr.update(
        label=(
            f'<<font point-size="40" face="{FONT} Semibold">{title}</font><br/>'
            f'<font point-size="18" color="#616161">{subtitle}</font><br/> >'
        ),
        labelloc="t",
        labeljust="c",
    )
    return diagram


def legend_below(dot, legend_html: str) -> None:
    """Put the legend under the whole picture, centred, instead of beside it.

    Wraps everything drawn so far in an invisible frame (a cluster) whose label is the legend,
    at the bottom. The pictures are wide, so a legend at the side shrinks them; below, it uses
    the width that is already there. Call it last, after every node and edge is declared.
    """
    dot.body[:] = [
        "\tsubgraph cluster_legend_frame {\n",
        *dot.body,
        # Attributes last: nested clusters copy their parent's attributes when they are declared,
        # so set before the body, labelloc=b would move every lane title to the bottom.
        f"\t\tlabel={legend_html}\n",
        "\t\tlabelloc=b labeljust=c pencolor=white style=solid margin=16 fontsize=14\n",
        "\t}\n",
    ]


def legend(
    lanes: list[str | tuple[str, str]],
    flows: list[tuple[int | None, str, str, str]],
    flows_title: str = "Numbered flows",
    note: str | None = "Access, data and runtime dependencies",
) -> str:
    """HTML legend, laid out wide for the bottom of the picture: swimlane keys (or (key, name))
    in the first column, then the flows as (number, colour, style, text) in one or two columns."""

    def heading(text: str) -> str:
        return f'<tr><td colspan="2" align="left"><font point-size="15" color="#424242"><b>{text}</b></font></td></tr>'

    def column(rows: list[str]) -> str:
        return (
            '<td valign="top"><table border="0" cellborder="0" cellspacing="4" cellpadding="3">'
            + "".join(rows)
            + "</table></td>"
        )

    lane_rows = [heading("Swimlanes")]
    for item in lanes:
        key, name = item if isinstance(item, tuple) else (item, LANE_NAMES[item])
        fill, border = LANE[key]
        lane_rows.append(
            f'<tr><td width="34" height="20" bgcolor="{fill}" color="{border}" border="2"></td>'
            f'<td align="left"><font point-size="14">{name}</font></td></tr>'
        )

    flow_rows = []
    for n, colour, style, text in flows:
        number = f"<b>{CIRCLED[n]}</b> " if n else ""
        flow_rows.append(
            f'<tr><td align="center"><font color="{colour}" point-size="16"><b>{LINE_SAMPLE[style]}</b></font></td>'
            f'<td align="left"><font color="{colour}" point-size="14">{number}{text}</font></td></tr>'
        )
    if note:
        flow_rows.append(
            '<tr><td align="center"><font color="#9E9E9E" point-size="16">────</font></td>'
            f'<td align="left"><font color="#616161" point-size="14">{note}</font></td></tr>'
        )
    # Long flow lists go in two columns, so the legend stays short.
    half = (len(flow_rows) + 1) // 2 if len(flow_rows) > len(lane_rows) else len(flow_rows)
    flow_cols = [column([heading(flows_title)] + flow_rows[:half])]
    if flow_rows[half:]:
        flow_cols.append(column([heading("&#160;")] + flow_rows[half:]))

    return (
        '<<table border="1" color="#BDBDBD" cellborder="0" cellspacing="8" cellpadding="4" bgcolor="white">'
        '<tr><td colspan="9" align="left"><font point-size="20"><b>Legend</b></font></td></tr>'
        "<tr>" + column(lane_rows) + "".join(flow_cols) + "</tr></table>>"
    )


def place_columns(diagram: Diagram, columns: list[list[Node]], legend_label: str | None = None) -> None:
    """Pin nodes to columns (ranks), left to right; the legend goes under the whole picture."""
    dot = diagram.dot
    for col in columns:
        dot.body.append("{rank=same; " + " ".join(f'"{n.nodeid}";' for n in col) + "}")
    for left, right in zip(columns, columns[1:]):
        dot.edge(left[0].nodeid, right[0].nodeid, style="invis", weight="10")
    if legend_label:
        legend_below(dot, legend_label)


# --------------------------------------------------------------------------- render
_NODE_STMT = re.compile(r'^(\s*)("?[0-9a-f]{32}"?) \[(.*?)\]$', re.M | re.S)
_ATTR = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|[^\s\]]+)')
ICON_PT = 78  # icon cell size in points


def _html(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "<br/>".join(text.replace("\\n", "\n").splitlines())


def _fit_labels(source: str) -> str:
    """Turn icon nodes into HTML tables: a fixed-size icon cell above a text cell.

    `diagrams` draws labels inside fixed-size icon nodes, so long labels spill
    out of their swimlanes. As an HTML table, Graphviz sizes each node from both
    the icon and the text, and swimlanes enclose the whole label.
    """

    def repl(match: re.Match[str]) -> str:
        attrs = dict(_ATTR.findall(match.group(3)))
        image = attrs.get("image", "").strip('"')
        label = attrs.get("label", '""')
        if not image or not label.startswith('"'):
            return match.group(0)
        text = _html(label[1:-1])
        html = (
            '<<table border="0" cellborder="0" cellspacing="0" cellpadding="2">'
            f'<tr><td fixedsize="true" width="{ICON_PT}" height="{ICON_PT}">'
            f'<img src="{image}" scale="true"/></td></tr>'
            f'<tr><td>{text}</td></tr></table>>'
        )
        keep = {k: v for k, v in attrs.items() if k not in {"label", "image", "height", "width", "shape",
                                                            "fixedsize", "labelloc", "imagescale"}}
        rest = " ".join(f"{k}={v}" for k, v in keep.items())
        return (
            f"{match.group(1)}{match.group(2)} [label={html} shape=plain fixedsize=false "
            f'width=0 height=0 image="" {rest}]'
        )

    return _NODE_STMT.sub(repl, source)


def _two_pass_source(diagram: Diagram) -> str:
    body = diagram.dot.body
    semantic = [line for line in body if "->" in line and "constraint=false" in line]
    diagram.dot.body = [line for line in body if line not in semantic]
    skeleton = _fit_labels(diagram.dot.source)
    diagram.dot.body = body
    laid = subprocess.run(
        ["dot", "-Tdot"], input=skeleton.encode("utf-8"), capture_output=True, check=True
    ).stdout.decode("utf-8")
    cut = laid.rstrip().rfind("}")
    return laid[:cut] + "".join(semantic) + "\n}\n"


def _embed_images(svg_path: Path) -> None:
    text = svg_path.read_text(encoding="utf-8")

    def repl(match: re.Match[str]) -> str:
        ref = match.group(2)
        if ref.startswith("data:"):
            return match.group(0)
        path = Path(ref)
        if not path.is_absolute():
            path = HERE / path
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'{match.group(1)}="data:image/png;base64,{data}"'

    svg_path.write_text(re.sub(r'(xlink:href|href)="([^"]+\.png)"', repl, text), encoding="utf-8")


def publish(diagram: Diagram, name: str) -> None:
    """Render `<name>.png` (200 dpi) and a self-contained `<name>.svg` next to this file."""
    source = _two_pass_source(diagram)
    for fmt, dpi in (("png", "200"), ("svg", "72")):
        out = HERE / f"{name}.{fmt}"
        subprocess.run(
            ["neato", "-n2", f"-Gdpi={dpi}", f"-T{fmt}", "-o", str(out)],
            input=source.encode("utf-8"),
            capture_output=True,
            check=True,
        )
        if fmt == "svg":
            _embed_images(out)
        print(f"wrote {out}")
