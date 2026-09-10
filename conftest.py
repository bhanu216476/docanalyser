"""
Root pytest configuration for the repository.

Ensures both ``rag-service`` and ``hybrid-rag/rag-service`` are accessible
to pytest when run from the workspace root (e.g. in GitHub Actions CI).
Primary package hierarchy belongs to ``rag-service``, with ``hybrid-rag``
submodules bridged into ``app`` and ``app.ingestion`` search paths.
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.resolve()
_RAG_SERVICE = str(_ROOT / "rag-service")
_HYBRID_RAG_SERVICE = str(_ROOT / "hybrid-rag" / "rag-service")

# Insert hybrid-rag first, then rag-service, so rag-service is at index 0
for p in (_HYBRID_RAG_SERVICE, _RAG_SERVICE):
    if os.path.isdir(p):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)

# Primary 'app' package is from rag-service
try:
    import app

    hybrid_app_dir = os.path.join(_HYBRID_RAG_SERVICE, "app")
    if os.path.isdir(hybrid_app_dir) and hybrid_app_dir not in app.__path__:
        app.__path__.append(hybrid_app_dir)

    import app.ingestion

    hybrid_ing_dir = os.path.join(hybrid_app_dir, "ingestion")
    if (
        os.path.isdir(hybrid_ing_dir)
        and hybrid_ing_dir not in app.ingestion.__path__
    ):
        app.ingestion.__path__.append(hybrid_ing_dir)

except ImportError:
    pass
