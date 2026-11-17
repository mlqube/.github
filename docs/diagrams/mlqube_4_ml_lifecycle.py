"""MlQube view 4: training, testing and serving.

How one tenant's model goes from Python code to a GPU training job, through
tests in non-prod, and to a canary deployment in prod, with scheduled retraining.
Example tenant: retail-1042, project namespace retail-1042-churn.

Run: python docs/diagrams/mlqube_4_ml_lifecycle.py  ->  mlqube_4_ml_lifecycle.png / .svg
"""

from __future__ import annotations

from mlqube_style import (
    BLUE, GREEN, ORANGE, PURPLE, SLATE,
    box, icon, lane, legend, new_diagram, place_columns, plain, publish, step,
)

from diagrams.aws.compute import EC2ContainerRegistry, EC2Instances, EC2SpotInstance
from diagrams.aws.general import Client
from diagrams.aws.storage import SimpleStorageServiceS3Bucket
from diagrams.custom import Custom
from diagrams.k8s.compute import Pod
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import User, Users
from diagrams.onprem.gitops import Argocd
from diagrams.onprem.mlops import Mlflow
from diagrams.onprem.vcs import Github

NAME = "mlqube_4_ml_lifecycle"

FLOWS = [
    (1, BLUE, "bold", "Develop: explore data in a notebook, write the pipeline in Python with the Hera SDK"),
    (2, BLUE, "bold", "Build: push to GitHub; GitHub Actions runs tests and pushes training / serving images to ECR"),
    (3, BLUE, "bold", "Submit: the Hera code submits a workflow (golden template train-evaluate-register) to Argo Workflows"),
    (4, BLUE, "bold", "Schedule: Kueue admits it to the tenant's GPU queue; Karpenter starts a tenant-dedicated spot GPU node"),
    (5, GREEN, "bold", "Train and track: read data from the tenant bucket; log runs and register the model version in MLflow"),
    (6, SLATE, "bold", "Test: evaluate against the baseline, then deploy the candidate to a staging endpoint for integration tests"),
    (7, PURPLE, "bold", "Promote: the model owner promotes the version in MLflow; MlQube opens a GitOps PR (ModelDeployment)"),
    (8, ORANGE, "bold", "Deploy: after approval and merge, Argo CD rolls out a KServe canary in prod (vLLM for LLMs)"),
    (9, PURPLE, "bold", "Serve: business applications call the endpoint through the internal ALB"),
    (10, GREEN, "dotted", "Retrain: CronWorkflows retrain on a schedule and register a new version, which goes back to step ⑥"),
]


def build():
    diagram = new_diagram(
        NAME,
        "MlQube: Training, testing and serving",
        "4 · Model lifecycle for one tenant (retail-1042, project namespace retail-1042-churn)",
        ranksep="1.2",
        nodesep="0.7",
    )
    with diagram:
        # inside a column, declaration order runs bottom to top
        with lane("People", "people"):
            owner = User("Model owner /\ntenant admin")
            dev = Users("ML engineer\nretail-1042")

        with lane("Corporate edge", "edge"):
            actions = GithubActions("GitHub Actions\ntests · image build")
            github = Github("GitHub\napp repo")
            hera = Custom("Python code\n+ Hera SDK", icon("hera"))

        with lane("AWS account · region", "aws", fontsize="20"):
            with lane("Non-prod cluster · namespace retail-1042-churn", "nonprod"):
                with box("Test"):
                    staging = Custom("Staging endpoint\n(KServe)\nintegration · load tests", icon("kserve"))
                    evaluate = Pod("Evaluate step\nmetrics vs baseline")
                with box("Train"):
                    gpu = EC2SpotInstance("GPU node (spot)\ndedicated to retail-1042\ntraining pods")
                    karpenter = Custom("Karpenter\nGPU NodePool", icon("karpenter"))
                    kueue = Custom("Kueue\nretail-1042 GPU queue", icon("kueue"))
                    argo_wf = Custom("Argo Workflows\ntrain-evaluate-register", icon("argo"))
                with box("Develop"):
                    notebook = Custom("Notebook\n(Jupyter)", icon("jupyter"))

            with lane("Shared AWS services", "shared"):
                s3_mlflow = SimpleStorageServiceS3Bucket("S3: MLflow artifacts\ntenants/retail-1042/")
                ecr = EC2ContainerRegistry("ECR\ntraining · serving images")
                s3_tenant = SimpleStorageServiceS3Bucket("S3: retail-1042-<env>\ntraining data")

            with lane("Management cluster", "mgmt"):
                argocd = Argocd("Argo CD")
                mlflow = Mlflow("MLflow (shared)\nruns · model versions\ncandidate → champion")

            with lane("GitHub · GitOps repo", "edge"):
                gitops = Github("GitOps repo\nModelDeployment PR\n(owner approves · merges)")

            with lane("Prod cluster · namespace retail-1042-churn", "prod"):
                cron = Custom("CronWorkflow\nscheduled retraining", icon("argo"))
                gpu_inf = EC2Instances("GPU inference\nNodePool (Karpenter)")
                vllm = Custom("vLLM runtime\n(LLM models)", icon("vllm"))
                kserve = Custom("KServe InferenceService\ncanary: v3 10% · v2 90%", icon("kserve"))

        with lane("Consumers of models", "consumers"):
            app = Client("Business application")

        # ① develop
        dev >> step(1, BLUE, "explore data") >> notebook
        dev >> step(1, BLUE, "write pipeline") >> hera

        # ② build
        hera >> step(2, BLUE, "push") >> github
        github >> step(2, BLUE, "CI") >> actions
        actions >> step(2, BLUE, "push images") >> ecr

        # ③ submit and ④ schedule
        hera >> step(3, BLUE, "submit workflow") >> argo_wf
        argo_wf >> step(4, BLUE, "queue") >> kueue
        kueue >> step(4, BLUE, "admit") >> karpenter
        karpenter >> step(4, BLUE, "GPU node") >> gpu

        # ⑤ train and track
        s3_tenant >> step(5, GREEN, "training data") >> gpu
        gpu >> step(5, GREEN, "log runs · register v3") >> mlflow
        mlflow >> step(5, GREEN, "artifacts") >> s3_mlflow
        ecr >> plain() >> gpu

        # ⑥ test
        gpu >> step(6, SLATE, "evaluate") >> evaluate
        evaluate >> step(6, SLATE, "deploy candidate") >> staging

        # ⑦ promote
        owner >> step(7, PURPLE, "promote v3") >> mlflow
        mlflow >> step(7, PURPLE, "opens PR") >> gitops

        # ⑧ deploy
        gitops >> step(8, ORANGE, "merge") >> argocd
        argocd >> step(8, ORANGE, "canary rollout") >> kserve
        kserve >> plain() >> vllm
        vllm >> plain() >> gpu_inf

        # ⑨ serve
        app >> step(9, PURPLE, "inference via internal ALB") >> kserve

        # ⑩ retrain
        cron >> step(10, GREEN, "new version", style="dotted") >> mlflow

        place_columns(
            diagram,
            [
                [dev, owner],
                [hera, github, actions],
                [notebook, argo_wf],
                [kueue, evaluate],
                [karpenter, staging],
                [gpu],
                [mlflow, argocd, s3_tenant, ecr, s3_mlflow],
                [gitops],
                [kserve, vllm, gpu_inf, cron],
                [app],
            ],
            legend(
                [("people", "People"), ("edge", "Corporate edge (GitHub)"), "nonprod", "mgmt", "shared", "prod",
                 "consumers"],
                FLOWS,
                flows_title="Steps",
                note="Runtime dependency",
            ),
        )
    return diagram


if __name__ == "__main__":
    publish(build(), NAME)
