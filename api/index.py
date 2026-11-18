"""
Entrypoint Serverless Vercel untuk aplikasi Flask Lombaku.
Menyertakan WSGI middleware ringan untuk memulihkan PATH_INFO asli
ketika Vercel melakukan rewrite request ke `/api/index`.
"""
import os
import sys
from urllib.parse import parse_qsl, urlencode

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app as flask_app  # noqa: E402


class VercelPathFixMiddleware:
    """Memulihkan PATH_INFO dan QUERY_STRING asli dari rewrite vercel.json."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "/")
        raw_qs = environ.get("QUERY_STRING", "")

        qs_pairs = parse_qsl(raw_qs, keep_blank_values=True)
        vpath = None
        cleaned_pairs = []
        for k, v in qs_pairs:
            if k == "__vpath" and vpath is None:
                vpath = v
            else:
                cleaned_pairs.append((k, v))

        # Hapus parameter internal __vpath dari query string Flask
        if vpath is not None:
            environ["QUERY_STRING"] = urlencode(cleaned_pairs, doseq=True)

        # Jika Vercel meneruskan PATH_INFO sebagai /api/index(.py), pulihkan ke path asli
        if path in ("/api/index", "/api/index.py") or path.startswith("/api/index/"):
            restored = vpath
            if not restored:
                orig = (
                    environ.get("HTTP_X_VERCEL_ORIGINAL_PATH")
                    or environ.get("HTTP_X_FORWARDED_URI")
                    or "/"
                )
                restored = orig.split("?", 1)[0]
            if not restored.startswith("/"):
                restored = "/" + restored
            # Hindari double slash seperti "//events"
            while restored.startswith("//"):
                restored = restored[1:]
            environ["PATH_INFO"] = restored or "/"

        return self.wsgi_app(environ, start_response)


flask_app.wsgi_app = VercelPathFixMiddleware(flask_app.wsgi_app)
app = flask_app
