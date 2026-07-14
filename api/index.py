import sys, os, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = None

try:
    from app import app as application
    app = application
    print("INIT OK", file=sys.stderr)
except Exception:
    _tb = traceback.format_exc()
    print("INIT FAILED:", _tb, file=sys.stderr)
    from flask import Flask
    app = Flask(__name__)
    _debug = {
        "cwd": os.getcwd(),
        "python": sys.version,
        "databases_url": os.environ.get("DATABASE_URL", "(not set)"),
        "vercel_env": os.environ.get("VERCEL_ENV", "(not set)"),
    }
    _info = "<br>".join(f"<b>{k}:</b> {v}" for k, v in _debug.items())

    @app.route("/")
    @app.route("/<path:path>")
    def error_route(path=""):
        return f"""<pre style='background:#fef2f2;padding:20px;border:2px solid #ef4444;
border-radius:8px;font-size:13px;overflow:auto;max-height:90vh;'>
<h2>App Initialization Failed</h2>
{_info}
<hr><pre>{_tb}</pre></pre>""", 500

if app is None:
    from flask import Flask
    app = Flask(__name__)

    @app.route("/")
    @app.route("/<path:path>")
    def error_route(path=""):
        return "<h1>App failed to initialize</h1>", 500

upload_dir = app.config.get("UPLOAD_FOLDER", "")
if upload_dir:
    os.makedirs(os.path.join(upload_dir, "avatars"), exist_ok=True)
