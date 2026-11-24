"""Render all MlQube architecture views (PNG + SVG) in docs/diagrams/.

Run: python docs/diagrams/render_all.py
"""

import importlib

import mlqube_style  # sets PATH and the working directory

VIEWS = [
    "mlqube_1_overview",
    "mlqube_2_identity",
    "mlqube_3_management",
    "mlqube_4_ml_lifecycle",
    "mlqube_5_enterprise",
    "mlqube_6_gitops_hub",
]

for name in VIEWS:
    module = importlib.import_module(name)
    mlqube_style.publish(module.build(), module.NAME)

# The glue pictures (docs/glue.md), same style
import glue_diagrams  # noqa: E402

mlqube_style.publish(glue_diagrams.overview(), "glue_1_overview")
mlqube_style.publish(glue_diagrams.tenant(), "glue_2_tenant")
mlqube_style.publish(glue_diagrams.apis(), "glue_3_apis")
