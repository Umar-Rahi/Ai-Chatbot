"""
Application entry point.
Run with:  python run.py
"""
import sys
import os

# Ensure the project root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(__file__))

from backend.app import app

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
