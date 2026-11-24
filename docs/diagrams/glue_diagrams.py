"""The MlQube glue: the thin layer of our own code that ties the open-source components together
into one platform (docs/glue.md). Three pictures, in the style of the architecture views:

    glue_1_overview   what the glue is, and what it connects
    glue_2_tenant     one Tenant resource → every object it creates
    glue_3_apis       the four platform APIs and what each expands into

Run: python docs/diagrams/glue_diagrams.py  ->  glue_*.png / .svg next to this file
"""

from __future__ import annotations

from mlqube_style import (
    GREEN, GREY, LANE, ORANGE, PURPLE, RED, TEAL,
    box, icon, lane, legend, link, new_diagram, place_columns, plain, publish, step,
)

from diagrams.aws.compute import ECR
from diagrams.aws.security import IdentityAndAccessManagementIamRole, SecretsManager, SingleSignOn
from diagrams.aws.storage import SimpleStorageServiceS3Bucket
from diagrams.custom import Custom
from diagrams.k8s.clusterconfig import Quota
from diagrams.k8s.group import NS
from diagrams.k8s.network import Ing, Netpol
from diagrams.k8s.others import CRD
from diagrams.k8s.rbac import SA, Group
from diagrams.onprem.client import User, Users
from diagrams.onprem.gitops import Argocd
from diagrams.onprem.identity import Dex
from diagrams.onprem.mlops import Mlflow
from diagrams.onprem.monitoring import Grafana
from diagrams.onprem.vcs import Github
from diagrams.programming.flowchart import Document

# The glue's own colour: everything we write is in a magenta box (prod is not in these views).
LANE["glue"] = ("#FCE4EC", "#AD1457")
GLUE = "#AD1457"


def glue_box(title: str):
    """A box of MlQube glue (our code) inside a cluster lane."""
    return lane(title, "glue", fontsize="15", penwidth="3")


def oss_box(title: str):
    """A box of upstream open source: installed and upgraded, not written by us."""
    return box(title)


# ------------------------------------------------------------------------------- 1. overview
OVERVIEW_FLOWS = [
    (1, PURPLE, "bold", "Someone asks for something in Backstage: a new tenant, a new ML project, a model in production"),
    (2, GLUE, "bold", "A glue template turns the form into a short YAML file and opens a pull request; a person reviews it"),
    (3, ORANGE, "bold", "Merged: Argo CD applies the file, like everything else in the platform"),
    (4, GLUE, "bold", "Crossplane runs the glue's Composition: the file expands into every object it implies"),
    (5, GLUE, "bold", "The objects land in the open-source components and AWS; MLflow through a small glue function"),
    (6, TEAL, "dashed", "Glue policies in Kyverno check every object: tenant label, names within the tenant prefix"),
    (7, RED, "dotted", "Glue metering: the tenant label on everything → OpenCost → a cost report per business unit"),
]


def overview():
    diagram = new_diagram(
        "glue_1_overview",
        "The MlQube glue",
        "Our thin layer of code (magenta) that turns open-source components (white boxes) into one platform · built on Crossplane",
        ranksep="1.1",
        nodesep="0.5",
    )
    with diagram:
        with lane("People", "people"):
            admin = User("Business-unit admin\nretail-1042")
            engineer = Users("ML engineers\nretail-1042")

        with lane("Source of truth", "edge"):
            github = Github("GitHub · gitops repo\ntenants/retail-1042.yaml")

        with lane("Management cluster", "mgmt", fontsize="20"):
            with oss_box("Developer portal"):
                backstage = Custom("Backstage", icon("backstage"))
            with glue_box("Glue A: templates"):
                templates = Document("A · Backstage software templates\n“New tenant” · “New ML project”\n“Deploy a model”\nform → YAML → pull request")
            with oss_box("Delivery"):
                argocd = Argocd("Argo CD\n(GitOps hub)")
            with oss_box("Crossplane: the engine (CNCF)"):
                crossplane = Custom("Crossplane core\n+ providers (AWS, Kubernetes)\n+ functions", icon("crossplane"))
            with glue_box("Glue B–E: our code"):
                metering = Document("E · Metering rules\ntenant label everywhere,\nreport per business unit")
                policies = Document("D · Kyverno policies\nmlqube/tenant label,\nname prefixes, images")
                mlflow_fn = Document("C · MLflow permissions\nfunction / small controller\n(no Crossplane provider)")
                apis = CRD("B · Platform APIs\nXRDs: Tenant · MLProject ·\nWorkspace · ModelDeployment\n+ Compositions")
            with oss_box("Shared tools"):
                opencost = Custom("OpenCost", icon("opencost"))
                kyverno = Custom("Kyverno", icon("kyverno"))
                mlflow = Mlflow("MLflow (shared)")

        with lane("Shared AWS services", "shared"):
            aws = SimpleStorageServiceS3Bucket("S3 bucket · IAM role ·\nECR · Secrets Manager\nper tenant")

        with lane("Workload clusters (non-prod, prod)", "nonprod"):
            with oss_box("What a tenant gets"):
                kserve = Custom("KServe\nmodel endpoints", icon("kserve"))
                workflows = Custom("Argo Workflows\nML jobs", icon("argo"))
                kueue = Custom("Kueue\nGPU queue + quota", icon("kueue"))
                capsule = Custom("Capsule tenant\nnamespaces, quotas", icon("capsule"))

        engineer >> step(1, PURPLE, "fills a form") >> backstage
        admin >> step(1, PURPLE, "fills a form") >> backstage
        backstage >> step(2, GLUE, "runs the template") >> templates
        templates >> step(2, GLUE, "pull request") >> github
        github >> step(3, ORANGE, "merged → synced") >> argocd
        argocd >> step(3, ORANGE, "applies the Tenant") >> crossplane
        crossplane >> step(4, GLUE, "runs our Composition") >> apis
        apis >> step(5, GLUE, "creates") >> capsule
        apis >> step(5, GLUE, "creates") >> kueue
        apis >> plain(color=GLUE) >> workflows
        apis >> plain(color=GLUE) >> kserve
        apis >> step(5, GLUE, "creates") >> aws
        apis >> step(5, GLUE, "permissions") >> mlflow_fn
        mlflow_fn >> step(5, GLUE, "MLflow API") >> mlflow
        policies >> step(6, TEAL, "loaded into", style="dashed") >> kyverno
        kyverno >> step(6, TEAL, "checks every object", style="dashed") >> capsule
        metering >> step(7, RED, "label rules", style="dotted") >> opencost
        opencost >> step(7, RED, "cost per business unit", style="dotted") >> admin

        place_columns(
            diagram,
            [
                [admin, engineer],
                [backstage],
                [templates],
                [github],
                [argocd],
                [crossplane],
                [metering, policies, mlflow_fn, apis],
                [opencost, kyverno, mlflow],
                [aws, kserve, workflows, kueue, capsule],
            ],
            legend(
                [("people", "People"), ("edge", "Source of truth"), ("mgmt", "Management cluster"),
                 ("glue", "MlQube glue: our code"), ("inner", "Open-source component (not ours)"),
                 ("shared", "Shared AWS services"), ("nonprod", "Workload clusters")],
                OVERVIEW_FLOWS,
                note=None,
            ),
        )
    return diagram


# ------------------------------------------------------------------------------- 2. one Tenant
TENANT_FLOWS = [
    (1, ORANGE, "bold", "The Tenant file is merged in the gitops repository; Argo CD applies it to the management cluster"),
    (2, GLUE, "dashed", "The glue's XRD validates it: required fields, tenant ID format, at most 30 characters"),
    (3, GLUE, "bold", "The glue's Composition renders every object with a pipeline of Crossplane functions"),
    (4, GLUE, "bold", "Crossplane's providers create them: Kubernetes objects in the workload clusters, AWS resources"),
    (5, GLUE, "bold", "The glue's MLflow function grants the tenant's groups their experiments and models"),
    (6, GREEN, "dashed", "The Tenant turns Ready when every object exists; Backstage shows it to the requester"),
]


def tenant():
    diagram = new_diagram(
        "glue_2_tenant",
        "One Tenant, every object it creates",
        "What the glue does with a few lines of YAML for business unit retail-1042 · magenta = our code · white = upstream",
        ranksep="1.0",
        nodesep="0.45",
    )
    with diagram:
        with lane("Source of truth", "edge"):
            yaml = Document(
                "tenants/retail-1042.yaml\n\napiVersion: platform.mlqube.click/v1alpha1\nkind: Tenant\n"
                "metadata: {name: retail-1042}\nspec:\n  gpuQuota: 4\n  groups: admins / developers /\n"
                "    viewers (Identity Center IDs)"
            )

        with lane("Management cluster", "mgmt", fontsize="20"):
            argocd = Argocd("Argo CD")
            with oss_box("Crossplane (upstream engine)"):
                xr = CRD("Tenant retail-1042\ncomposite resource (XR)\nstatus: Ready")
                with glue_box("Glue: XRD + Composition “tenant”"):
                    xrd = CRD("XRD Tenant\nthe schema: what a\nrequest may contain")
                    pipeline = Custom(
                        "Composition pipeline\n1. go-templating: render objects\n2. checks and defaults\n3. auto-ready: status",
                        icon("crossplane"),
                    )
                aws_provider = Custom("provider-aws\nS3 · IAM · Pod Identity\n· Secrets Manager", icon("crossplane"))
                k8s_provider = Custom("provider-kubernetes\nobjects in the\nworkload clusters", icon("crossplane"))
            with glue_box("Glue: MLflow permissions"):
                mlflow_fn = Document("function / controller\ngroup IDs → MLflow\npermissions")
            mlflow = Mlflow("MLflow (shared)\nexperiments /retail-1042/*\nmodels retail-1042.*")

        with lane("Workload cluster non-prod (prod the same, later)", "nonprod", fontsize="18"):
            rbac = Group("RoleBindings\ndevelopers: edit\nviewers: view")
            sa = SA("ServiceAccount\nretail-1042-workloads")
            netpol = Netpol("NetworkPolicy\ndefault deny\nbetween tenants")
            queue = Custom("Kueue queues\nClusterQueue + LocalQueue\n4 GPUs, fair share", icon("kueue"))
            capsule = Custom("Capsule Tenant\nowners = the tenant's\nIdentity Center groups", icon("capsule"))
            quota = Quota("ResourceQuota\nCPU · memory · storage")
            namespaces = NS("Namespaces retail-1042-*\nlabel mlqube/tenant")

        with lane("Shared AWS services", "shared"):
            secrets = SecretsManager("Secrets Manager\nmlqube/tenants/retail-1042/*")
            pia = IdentityAndAccessManagementIamRole("Pod Identity association\nServiceAccount → role")
            role = IdentityAndAccessManagementIamRole("IAM role mlqube-retail-1042\nonly this tenant's bucket,\nECR repos and secrets")
            bucket = SimpleStorageServiceS3Bucket("S3 bucket\nmlqube-retail-1042-nonprod")

        yaml >> step(1, ORANGE, "merged → synced") >> argocd
        argocd >> step(1, ORANGE, "applies") >> xr
        xrd >> step(2, GLUE, "validates", style="dashed") >> xr
        xr >> step(3, GLUE, "rendered by") >> pipeline
        pipeline >> step(4, GLUE, "Kubernetes objects") >> k8s_provider
        pipeline >> step(4, GLUE, "AWS resources") >> aws_provider
        pipeline >> step(5, GLUE, "permissions") >> mlflow_fn
        mlflow_fn >> step(5, GLUE, "MLflow API") >> mlflow
        for target in (capsule, queue, netpol, sa, rbac):
            k8s_provider >> plain(color=GLUE, penwidth="1.8") >> target
        for target in (bucket, role, pia, secrets):
            aws_provider >> plain(color=GLUE, penwidth="1.8") >> target
        capsule >> plain() >> namespaces
        capsule >> plain() >> quota
        pia >> plain(color="#FF9900", style="dotted") >> sa
        xr >> step(6, GREEN, "Ready", style="dashed") >> yaml

        place_columns(
            diagram,
            [
                [yaml],
                [argocd],
                [xr],
                [xrd, pipeline],
                [aws_provider, k8s_provider, mlflow_fn],
                [mlflow],
                [rbac, sa, netpol, queue, capsule],
                [quota, namespaces],
                [secrets, pia, role, bucket],
            ],
            legend(
                [("edge", "Source of truth"), ("mgmt", "Management cluster"), ("glue", "MlQube glue: our code"),
                 ("inner", "Crossplane (upstream engine)"), ("nonprod", "Workload cluster"),
                 ("shared", "Shared AWS services")],
                TENANT_FLOWS,
                note="Objects created by the providers; grey: created by Capsule; orange dots: workload identity",
            ),
        )
    return diagram


# ------------------------------------------------------------------------------- 3. the four APIs
API_FLOWS = [
    (None, GLUE, "bold", "Expanded by the glue: a Crossplane Composition, plus a small controller where no provider exists"),
    (None, GREY, "dashed", "Ownership: a project belongs to a tenant; workspaces and deployments belong to a project"),
]


def apis():
    diagram = new_diagram(
        "glue_3_apis",
        "The four platform APIs",
        "What you ask for (one short YAML, usually through a Backstage form) · what the glue builds from it",
        ranksep="1.0",
        nodesep="0.45",
    )
    with diagram:
        with glue_box("You ask for (the glue's APIs)"):
            m = CRD("ModelDeployment\na served model\n(through promotion)")
            w = CRD("Workspace\na notebook or IDE")
            p = CRD("MLProject\none per project")
            t = CRD("Tenant\none per business unit")

        with lane("The glue builds (open-source components and AWS, set up for you)", "consumers", fontsize="18"):
            with oss_box("for a ModelDeployment"):
                m1 = Custom("KServe InferenceService\ncanary rollout", icon("kserve"))
                m2 = Ing("Route\nprivate URL")
                m3 = Grafana("Dashboards\nlatency · errors")
                m4 = Mlflow("Model version\nfrom the registry")
            with oss_box("for a Workspace"):
                w1 = Custom("Notebook / IDE\nwith a GPU limit", icon("jupyter"))
                w2 = Quota("Storage volume\n+ idle shutdown")
                w3 = Custom("GPU from the tenant's\nKueue queue", icon("kueue"))
                w4 = Dex("Sign-in through Dex\n(tenant groups)")
            with oss_box("for an MLProject"):
                p1 = NS("Namespace\nretail-1042-churn")
                p2 = ECR("ECR repository\n+ CI role (OIDC)")
                p3 = Mlflow("MLflow experiment\n/retail-1042/churn/*")
                p4 = Custom("Starter Argo\nWorkflowTemplates", icon("argo"))
            with oss_box("for a Tenant"):
                t1 = Custom("Capsule tenant\nquotas · Kueue queue", icon("capsule"))
                t2 = Netpol("Network policies\nRBAC from groups")
                t3 = SimpleStorageServiceS3Bucket("S3 bucket · IAM role\nPod Identity")
                t4 = SingleSignOn("Identity Center groups\nadmins · developers ·\nviewers (mapped)")

        t >> link("expands into", GLUE) >> t1
        p >> link("expands into", GLUE) >> p1
        w >> link("expands into", GLUE) >> w1
        m >> link("expands into", GLUE) >> m1
        t >> plain(style="dashed", label="owns", fontcolor=GREY) >> p
        p >> plain(style="dashed", label="owns", fontcolor=GREY) >> w
        p >> plain(style="dashed") >> m

        place_columns(
            diagram,
            [
                [m, w, p, t],
                [m1, w1, p1, t1],
                [m2, w2, p2, t2],
                [m3, w3, p3, t3],
                [m4, w4, p4, t4],
            ],
            legend(
                [("glue", "MlQube glue: the APIs (our code)"), ("consumers", "What gets built"),
                 ("inner", "Open-source component or AWS service")],
                API_FLOWS,
                flows_title="Lines",
                note=None,
            ),
        )
    return diagram


if __name__ == "__main__":
    publish(overview(), "glue_1_overview")
    publish(tenant(), "glue_2_tenant")
    publish(apis(), "glue_3_apis")
