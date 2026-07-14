import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///erp.db")
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

    # Serverless/Vercel check: if we can't write to CWD, use in-memory SQLite as ultimate fallback
    _fallback_to_memory = False
    if not SQLALCHEMY_DATABASE_URI or "sqlite" in SQLALCHEMY_DATABASE_URI:
        test_path = os.path.join(os.getcwd(), ".vercel_write_test")
        try:
            with open(test_path, "w") as f:
                f.write("test")
            os.remove(test_path)
        except (OSError, IOError):
            _fallback_to_memory = True

    # Neon/Postgres: resolve DNS to IP + add endpoint option (skip if already present)
    if "neon.tech" in (SQLALCHEMY_DATABASE_URI or ""):
        try:
            import urllib.parse, socket
            parsed = urllib.parse.urlparse(SQLALCHEMY_DATABASE_URI)
            hostname = parsed.hostname
            if hostname:
                ip = socket.gethostbyname(hostname)
                endpoint = hostname.split(".")[0]
                # Only replace hostname with IP if the URL uses pooler
                if "pooler" in hostname:
                    new_netloc = parsed.netloc.replace(hostname, ip)
                    SQLALCHEMY_DATABASE_URI = parsed._replace(netloc=new_netloc).geturl()
                # Add endpoint option only if not already present
                if f"endpoint={endpoint}" not in SQLALCHEMY_DATABASE_URI and f"endpoint%3D{endpoint}" not in SQLALCHEMY_DATABASE_URI:
                    sep = "&" if "?" in SQLALCHEMY_DATABASE_URI else "?"
                    SQLALCHEMY_DATABASE_URI += f"{sep}options=endpoint%3D{endpoint}"
                # Add sslmode=require only if not already present
                if "sslmode" not in SQLALCHEMY_DATABASE_URI.lower():
                    sep2 = "&" if "?" in SQLALCHEMY_DATABASE_URI else "?"
                    SQLALCHEMY_DATABASE_URI += f"{sep2}sslmode=require"
        except Exception:
            import traceback; traceback.print_exc()
            print("    DNS/Neon config failed, trying SQLite fallback")
            if _fallback_to_memory:
                SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            else:
                SQLALCHEMY_DATABASE_URI = "sqlite:///erp_dev.db"
    elif _fallback_to_memory:
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
