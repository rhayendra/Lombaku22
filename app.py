"""
Titik masuk utama (Entry Point) aplikasi web Lombaku.
Dapat dijalankan langsung di komputer lokal (`python app.py`)
maupun sebagai Serverless Function di Vercel (melalui `api/index.py`).
"""
import os
from flask import Flask, render_template, session, jsonify, request
from config import Config, BASE_DIR
from database.db import init_db, close_db, get_db
from database.seed import seed_demo_data
from routes.public import public_bp
from routes.admin import admin_bp
from routes.api import api_bp
from services.events import get_settings

_db_initialized = False


def ensure_database_ready():
    """Inisialisasi skema & data demo secara lazy agar startup/import di Vercel tidak pernah gagal."""
    global _db_initialized
    if Config.USE_POSTGRES:
        if not _db_initialized:
            init_db()
            seed_demo_data(force_reset=False)
            _db_initialized = True
        return

    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    if not _db_initialized or not os.path.exists(Config.DATABASE_PATH):
        init_db()
        seed_demo_data(force_reset=False)
        _db_initialized = True


def create_app() -> Flask:
    """Factory function untuk membuat dan mengonfigurasi instance Flask."""
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )
    app.config.from_object(Config)

    # Tutup koneksi database otomatis setiap request berakhir
    app.teardown_appcontext(close_db)

    # Daftarkan seluruh Blueprint (Public, Admin, API)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    @app.route("/health")
    def health_check():
        """Endpoint diagnostik cepat untuk mengecek status server & koneksi database di Vercel."""
        engine = "Supabase PostgreSQL" if Config.USE_POSTGRES else "SQLite"
        try:
            ensure_database_ready()
            db = get_db()
            ev_count = db.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
            return jsonify({
                "ok": True,
                "app": Config.APP_NAME,
                "engine": engine,
                "vercel": Config.IS_VERCEL,
                "events_count": ev_count,
            })
        except Exception as exc:
            return jsonify({
                "ok": False,
                "engine": engine,
                "vercel": Config.IS_VERCEL,
                "error": str(exc),
                "hint": "Pastikan DATABASE_URL memakai URI Transaction Pooler Supabase (port 6543) dengan password yang benar.",
            }), 500

    @app.before_request
    def _ensure_db_before_request():
        # Lewati pengecekan DB untuk file static dan endpoint /health
        if request.path.startswith("/static/") or request.path == "/health":
            return None
        try:
            ensure_database_ready()
        except Exception as exc:
            engine = "Supabase PostgreSQL" if Config.USE_POSTGRES else "SQLite"
            return (
                render_template(
                    "error.html",
                    code=503,
                    title=f"Koneksi Database ({engine}) Belum Tersambung",
                    message=(
                        f"Detail: {exc}. "
                        "Jika deploy di Vercel + Supabase, pastikan Environment Variable DATABASE_URL "
                        "menggunakan URL Transaction Pooler (port 6543) dan password database sudah benar."
                    ),
                ),
                503,
            )

    # Variabel global yang tersedia di semua template HTML
    @app.context_processor
    def inject_globals():
        defaults = {
            "app_name": Config.APP_NAME,
            "is_admin": bool(session.get("admin_id")),
            "admin_name": session.get("admin_name", ""),
            "school_settings": {
                "school_name": "SMA Negeri Nusantara 01",
                "school_tagline": "Pusat Digital Perlombaan & Turnamen Sekolah",
                "committee_contact": "Sekretariat OSIS",
                "announcement": "",
            },
            "global_live_count": 0,
            "sound_cue": session.pop("sound_cue", ""),
            "celebrate_mode": session.pop("celebrate_mode", ""),
        }
        try:
            if _db_initialized:
                db = get_db()
                defaults["school_settings"] = get_settings(db)
                defaults["global_live_count"] = db.execute(
                    "SELECT COUNT(*) AS c FROM matches WHERE status = 'LIVE'"
                ).fetchone()["c"]
        except Exception:
            pass
        return defaults

    @app.errorhandler(404)
    def not_found(error):
        return (
            render_template(
                "error.html",
                code=404,
                title="Halaman Tidak Ditemukan",
                message="Halaman atau event yang Anda cari tidak tersedia.",
            ),
            404,
        )

    @app.errorhandler(500)
    def server_error(error):
        return (
            render_template(
                "error.html",
                code=500,
                title="Terjadi Kesalahan Sistem",
                message="Mohon maaf, terjadi gangguan tak terduga. Silakan cek /health atau muat ulang halaman.",
            ),
            500,
        )

    return app


app = create_app()

if __name__ == "__main__":
    ensure_database_ready()
    db_mode = "Supabase PostgreSQL" if Config.USE_POSTGRES else f"SQLite ({Config.DATABASE_PATH})"
    print("=" * 60)
    print("  LOMBAKU — Liquid Glass School Competition Platform")
    print(f"  Database        : {db_mode}")
    print("  Buka di browser : http://127.0.0.1:5000")
    print("  Login Panitia   : http://127.0.0.1:5000/admin/login")
    print("  Akun Default    : admin / admin123")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=True)
