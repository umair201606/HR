import os
os.environ["DATABASE_URL"] = "sqlite:///erp_dev.db"
os.environ["SECRET_KEY"] = "local-dev-secret-key-2026"

from app import app

if __name__ == "__main__":
    app.run(port=5000, debug=True)
