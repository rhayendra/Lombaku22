"""
Entrypoint Serverless Vercel untuk aplikasi Flask Lombaku.
Vercel akan mengarahkan seluruh request (melalui vercel.json) ke variabel `app` di file ini.
"""
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app  # noqa: E402, F401
