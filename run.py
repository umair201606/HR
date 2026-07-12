import subprocess
import sys
import os
import webbrowser
import time
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, "venv")
REQUIREMENTS = os.path.join(BASE_DIR, "requirements.txt")
APP = os.path.join(BASE_DIR, "app.py")

BIN = "Scripts" if sys.platform == "win32" else "bin"
PYTHON = os.path.join(VENV_DIR, BIN, "python")
PIP = os.path.join(VENV_DIR, BIN, "pip")


def log(msg):
    print(f"  >> {msg}")


def check_venv():
    if not os.path.isdir(VENV_DIR):
        log("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
        log("Virtual environment created.")
    else:
        log("Virtual environment found.")


def install_deps():
    log("Installing dependencies...")
    subprocess.check_call([PIP, "install", "-r", REQUIREMENTS])
    log("Dependencies installed.")


def run_app():
    log("Starting Salary Slip Builder...")
    env = os.environ.copy()
    env["PORT"] = "5000"
    env["HOST"] = "127.0.0.1"
    proc = subprocess.Popen([PYTHON, APP], env=env, cwd=BASE_DIR)

    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000")
    log("Press Ctrl+C to stop the server.")

    def shutdown(sig, frame):
        log("Shutting down...")
        proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    proc.wait()


if __name__ == "__main__":
    print()
    print("=" * 50)
    print("   Salary Slip Builder")
    print("=" * 50)
    print()

    check_venv()
    install_deps()
    run_app()
