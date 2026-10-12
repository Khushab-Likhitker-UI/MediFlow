"""
Convenience entry point for running the Smart Health Sentinel evaluation suite.

Usage:
    cd backend
    python run_evaluation.py [--output evaluation_report.json]
"""

from app.ml.evaluation.runner import main

if __name__ == "__main__":
    main()
