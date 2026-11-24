"""The golden path v0 from the ML engineer's point of view (docs/golden-path.md), in the style of
the architecture views:

    golden_1_developer_flow   trunk-based: feature branch → own test run → merge → main run
    golden_2_cleanup          what happens to a feature branch's images and runs afterwards

Run: python docs/diagrams/golden_path_diagrams.py  ->  golden_*.png / .svg next to this file
"""

from __future__ import annotations

from mlqube_style import (
    BLUE, GREEN, GREY, ORANGE, PURPLE, RED, TEAL,
    box, icon, lane, legend, new_diagram, place_columns, plain, publish, step,
)

from diagrams.aws.compute import ECR, EC2SpotInstance
from diagrams.aws.storage import SimpleStorageServiceS3Bucket
from diagrams.custom import Custom
from diagrams.generic.network import VPN
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import User
from diagrams.onprem.mlops import Mlflow
from diagrams.onprem.vcs import Git, Github
from diagrams.programming.flowchart import Document

DEV = BLUE  # the feature-branch path: the engineer's own test run
MAIN = GREEN  # the main-branch path: the official run
CLEAN = RED  # cleanup after the branch is deleted


def esc(flows):
    """The legend is an HTML label: escape <placeholders> in the texts."""
    return [(n, c, st, t.replace("<", "&lt;").replace(">", "&gt;")) for n, c, st, t in flows]


# ------------------------------------------------------------------------------- 1. developer flow
FLOW = [
    (1, PURPLE, "bold", "Once per project: create it in Backstage. You get a repository from ml-project-template, an ECR repository, a namespace and GPU queues"),
    (2, DEV, "bold", "git checkout -b feat/…, change the code, git push. Every push to a feature branch starts your own test run"),
    (3, DEV, "bold", "CI builds the image feat-<branch>-<sha> and pushes it to ECR"),
    (4, DEV, "bold", "CI submits the workflow over Tailscale: dev queue (low priority), sample data, a smaller GPU budget"),
    (5, DEV, "bold", "Karpenter starts a GPU node; the run logs to MLflow, experiment …/dev. You compare runs in MLflow; CI comments the numbers on the PR"),
    (6, MAIN, "bold", "Review, then squash-merge to main. CI builds main-<sha>: immutable, kept"),
    (7, MAIN, "bold", "The official run: main queue, full data → MLflow experiment …/main → a registered model version"),
    (8, CLEAN, "dashed", "The feature branch is deleted: its images go now; its runs expire later (second picture)"),
]


def developer_flow():
    diagram = new_diagram(
        "golden_1_developer_flow",
        "The golden path: from a feature branch to a registered model",
        "Trunk-based · test your change on your own branch · main makes the official run · what an ML engineer does, and what happens",
        ranksep="1.05",
        nodesep="0.55",
    )
    with diagram:
        with lane("You", "people"):
            engineer = User("ML engineer\nretail-1042 · project churn\n(laptop, Tailscale on)")

        with lane("Developer portal (mgmt)", "mgmt"):
            backstage = Custom("Backstage\n“New ML project”", icon("backstage"))

        with lane("GitHub · retail-1042-churn repository", "edge"):
            main = Git("main\nprotected · squash-merge only")
            pr = Github("Pull request\nreview + CI's metrics comment")
            feat = Git("feat/better-features\nyour branch")

        with lane("GitHub Actions (CI)", "consumers"):
            ci_clean = GithubActions("On branch delete\ncleanup")
            ci_main = GithubActions("On push to main\nbuild · submit · register")
            ci_feat = GithubActions("On push to feat/*\nbuild · submit")
            tailscale = VPN("Tailscale\n(job joins the tailnet)")

        with lane("Shared AWS services", "shared"):
            img_main = ECR("ECR main-<sha>\nimmutable, kept")
            img_feat = ECR("ECR feat-<branch>-<sha>\ntemporary")

        with lane("Workload cluster non-prod", "nonprod"):
            with box("Namespace retail-1042-churn"):
                workflows = Custom("Argo Workflows\nyour training workflow\n(Python, Hera)", icon("argo"))
                kueue = Custom("Kueue\nqueue dev: low priority\nqueue main: normal", icon("kueue"))
            gpu = EC2SpotInstance("GPU node\nstarted by Karpenter,\nremoved when idle")

        with lane("Tracking (mgmt)", "mgmt"):
            artifacts = SimpleStorageServiceS3Bucket("S3 artifacts\nmlflow/dev/ · mlflow/main/")
            ml_main = Mlflow("MLflow …/churn/main\n+ registered model version")
            ml_dev = Mlflow("MLflow …/churn/dev\nyour runs, tagged with\nbranch, commit, PR")

        engineer >> step(1, PURPLE, "create project (once)") >> backstage
        backstage >> step(1, PURPLE, "repository from template") >> main
        engineer >> step(2, DEV, "git push") >> feat
        feat >> step(3, DEV, "push event") >> ci_feat
        ci_feat >> step(3, DEV, "docker push") >> img_feat
        ci_feat >> step(4, DEV, "submit") >> tailscale
        tailscale >> step(4, DEV, "Argo API") >> workflows
        workflows >> plain() >> kueue
        kueue >> step(5, DEV, "admitted → GPU") >> gpu
        img_feat >> plain(style="dashed") >> gpu
        workflows >> step(5, DEV, "metrics, params") >> ml_dev
        ml_dev >> step(5, DEV, "compare, PR comment", style="dashed") >> pr
        feat >> plain() >> pr
        pr >> step(6, MAIN, "squash-merge") >> main
        main >> step(6, MAIN, "push event") >> ci_main
        ci_main >> step(6, MAIN, "docker push") >> img_main
        ci_main >> step(7, MAIN, "submit") >> tailscale
        workflows >> step(7, MAIN, "full run") >> ml_main
        ml_main >> plain() >> artifacts
        ml_dev >> plain() >> artifacts
        pr >> step(8, CLEAN, "branch deleted", style="dashed") >> ci_clean
        ci_clean >> step(8, CLEAN, "delete images", style="dashed") >> img_feat

        place_columns(
            diagram,
            [
                [engineer],
                [backstage],
                [main, pr, feat],
                [ci_clean, ci_main, ci_feat],
                [tailscale],
                [img_main, img_feat],
                [gpu, kueue, workflows],
                [artifacts, ml_main, ml_dev],
            ],
            legend(
                [("people", "You"), ("mgmt", "Management cluster (portal, tracking)"), ("edge", "GitHub"),
                 ("consumers", "CI (GitHub Actions)"), ("shared", "Shared AWS services"),
                 ("nonprod", "Workload cluster non-prod")],
                esc(FLOW),
                note="Supporting connection (image pull, artifacts)",
            ),
        )
    return diagram


# ------------------------------------------------------------------------------- 2. cleanup
CLEANUP = [
    (1, CLEAN, "bold", "The feature branch is deleted (after the merge, or abandoned): GitHub sends a delete event"),
    (2, CLEAN, "bold", "The cleanup job deletes the branch's images from ECR at once and tags its MLflow runs with the deletion date"),
    (3, ORANGE, "dashed", "A daily job removes feature runs 30 days after their branch was deleted (metadata: parameters, metrics, tags)"),
    (4, ORANGE, "dashed", "An S3 lifecycle rule deletes dev artifacts (weights, checkpoints) after 14 days"),
    (5, GREY, "dotted", "Safety nets: an ECR lifecycle rule expires feat-* images after 14 days; Argo removes finished workflows after a few days"),
    (6, GREEN, "bold", "Kept: main images, main runs and registered models, the record of what was trained and shipped"),
]


def cleanup():
    diagram = new_diagram(
        "golden_2_cleanup",
        "What happens to a feature branch afterwards",
        "Metadata is small and useful: kept for a while · artifacts and images are big: deleted soon · main is the record: kept",
        ranksep="1.1",
        nodesep="0.55",
    )
    with diagram:
        with lane("GitHub", "edge"):
            deleted = Git("feat/better-features\ndeleted")

        with lane("Automation", "consumers"):
            rules = Document("Lifecycle rules\nS3 dev/: 14 days · ECR feat-*: 14 days\nArgo finished workflows: a few days")
            nightly = Document("Daily job (scheduled)\nremoves expired\nfeature runs")
            clean_job = GithubActions("Cleanup job\n(on branch delete)")

        with lane("Deleted now", "prod"):
            imgs = ECR("ECR images\nfeat-better-features-*")

        with lane("Expires later", "nonprod"):
            wf = Custom("Argo workflow records\nfinished workflows: a few days", icon("argo"))
            dev_art = SimpleStorageServiceS3Bucket("Dev artifacts\ns3://…/mlflow/dev/\n14 days (S3 lifecycle)")
            dev_runs = Mlflow("Feature runs …/dev\nparameters, metrics, tags\n30 days after branch delete")

        with lane("Kept (the record)", "mgmt"):
            reg = Mlflow("Registered model versions\n(from main only)")
            main_runs = Mlflow("Main runs …/main\nlinked to commit + image")
            main_imgs = ECR("ECR main-<sha>\nimmutable")

        deleted >> step(1, CLEAN, "delete event") >> clean_job
        clean_job >> step(2, CLEAN, "delete now") >> imgs
        clean_job >> step(2, CLEAN, "tag: deleted on <date>") >> dev_runs
        nightly >> step(3, ORANGE, "after 30 days", style="dashed") >> dev_runs
        rules >> step(4, ORANGE, "after 14 days", style="dashed") >> dev_art
        rules >> step(5, GREY, "safety net", style="dotted") >> imgs
        rules >> step(5, GREY, "workflow TTL", style="dotted") >> wf
        main_runs >> step(6, GREEN, "registered from") >> reg
        main_imgs >> step(6, GREEN, "trained with") >> main_runs

        place_columns(
            diagram,
            [
                [deleted],
                [rules, nightly, clean_job],
                [imgs],
                [wf, dev_art, dev_runs],
                [main_imgs, main_runs, reg],
            ],
            legend(
                [("edge", "GitHub"), ("consumers", "Automation"), ("prod", "Deleted at once"),
                 ("nonprod", "Expires after a while"), ("mgmt", "Kept long-term")],
                esc(CLEANUP),
                note=None,
            ),
        )
    return diagram


if __name__ == "__main__":
    publish(developer_flow(), "golden_1_developer_flow")
    publish(cleanup(), "golden_2_cleanup")
