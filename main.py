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
    sys.argv = [
        "streamlit", "run", app_path,
        "--server.port=8501",
        "--server.headless=false",
        "--global.developmentMode=false",
    ]
    st_main()
