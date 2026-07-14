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

    # Use SQLite for local dev unless explicitly set to Neon
    if "neon.tech" in (SQLALCHEMY_DATABASE_URI or ""):
        try:
            import urllib.parse, socket
            parsed = urllib.parse.urlparse(SQLALCHEMY_DATABASE_URI)
            hostname = parsed.hostname
            if hostname:
                ip = socket.gethostbyname(hostname)
                endpoint = hostname.split(".")[0]
                new_netloc = parsed.netloc.replace(hostname, ip)
                SQLALCHEMY_DATABASE_URI = parsed._replace(netloc=new_netloc).geturl()
                sep = "&" if "?" in SQLALCHEMY_DATABASE_URI else "?"
                SQLALCHEMY_DATABASE_URI += f"{sep}options=endpoint%3D{endpoint}"
                print(f"    DNS: {hostname} -> {ip}")
        except Exception:
            print("    DNS failed, trying SQLite fallback")
            SQLALCHEMY_DATABASE_URI = "sqlite:///erp_dev.db"
