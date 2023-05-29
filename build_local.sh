# Remove old build
rm -rf build
rm -rf dist

# Active venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller

# Build
pyinstaller krr.py
cd dist
zip -r "krr-macos-v1.1.0.zip" krr