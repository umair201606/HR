import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hr_app.app import create_app

app = create_app()

# Ensure upload directories exist
upload_dir = app.config.get("UPLOAD_FOLDER", "")
if upload_dir:
    os.makedirs(os.path.join(upload_dir, "avatars"), exist_ok=True)
