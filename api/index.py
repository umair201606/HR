import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as application

app = application

upload_dir = application.config.get("UPLOAD_FOLDER", "")
if upload_dir:
    os.makedirs(os.path.join(upload_dir, "avatars"), exist_ok=True)
