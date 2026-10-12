"""
Routes package exports for Smart Health Sentinel.
"""

from app.routes import alerts, evaluations, facility, inventory, predictions, replenishment, stock_movements, transfers, users

__all__ = [
    "alerts",
    "evaluations",
    "facility",
    "inventory",
    "predictions",
    "replenishment",
    "stock_movements",
    "transfers",
    "users",
]

