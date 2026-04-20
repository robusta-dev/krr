# Remove old build
rm -rf build
rm -rf dist

# Active venv
source .env/bin/activate
pip install -r requirements.txt
pip install pyinstaller

# Build
pyinstaller --onefile --target-architecture arm64 krr.py
cd dist
# zip -r "krr-macos-v1.1.0.zip" krr