# Remove old build
rm -rf build
rm -rf dist

# MacOS Build first

# Active venv
# python -m pip install -r requirements.txt
pip install pyinstaller
apt-get install binutils

# source .venv/bin/activate

# Build
pyinstaller krr.py
cd dist
# zip -r "krr-linux-v1.1.0.zip" krr

# Deactivate venv
# deactivate