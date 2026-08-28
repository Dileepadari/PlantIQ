"""WSGI entry point.

Local development:   python src/wsgi.py
Production (gunicorn): gunicorn --chdir src wsgi:app
PythonAnywhere: point the WSGI file at ``src.wsgi:app``.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plantiq import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("PLANTIQ_HOST", "127.0.0.1"),
        port=int(os.environ.get("PLANTIQ_PORT", 5000)),
        debug=os.environ.get("PLANTIQ_DEBUG", "1") == "1",
    )
