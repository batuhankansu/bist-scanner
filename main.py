import os
import sys

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, base_dir)

if __name__ == "__main__":
    from streamlit.web.cli import main as st_main

    app_path = os.path.join(base_dir, "app.py")
    port = os.environ.get("PORT", "8501")
    sys.argv = [
        "streamlit", "run", app_path,
        f"--server.port={port}",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    st_main()
