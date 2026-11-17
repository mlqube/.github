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
]

for name in VIEWS:
    module = importlib.import_module(name)
    mlqube_style.publish(module.build(), module.NAME)
