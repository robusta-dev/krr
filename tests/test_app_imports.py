import os
import pytest

KRR_EXPECTED_LINES = [
    "import os\n",
    "\n",
    "from robusta_krr.common.ssl_utils import add_custom_certificate\n",
    "\n",
    'ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")\n',
    "\n",
    "if add_custom_certificate(ADDITIONAL_CERTIFICATE):\n",
    '    print("added custom certificate")\n',
    "\n",
    "# DO NOT ADD ANY CODE ABOVE THIS\n",
    "# ADDING IMPORTS BEFORE ADDING THE CUSTOM CERTS MIGHT INIT HTTP CLIENTS THAT DOESN'T RESPECT THE CUSTOM CERT\n",
]

ENFORCER_EXPECTED_LINES = [
    "import sys\n",
    "import os\n",
    "\n",
    "# Add parent directory to Python path so we can import enforcer modules\n",
    "sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n",
    "\n",
    "from enforcer.utils import add_custom_certificate\n",
    "\n",
    'ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")\n',
    "\n",
    "if add_custom_certificate(ADDITIONAL_CERTIFICATE):\n",
    '    print("added custom certificate")\n',
    "\n",
    "# DO NOT ADD ANY CODE ABOVE THIS\n",
    "# ADDING IMPORTS BEFORE ADDING THE CUSTOM CERTS MIGHT INIT HTTP CLIENTS THAT DOESN'T RESPECT THE CUSTOM CERT\n",
]
@pytest.mark.parametrize(
    "file_path,file_name,expected_lines",
    [
        ("krr.py", "krr.py", KRR_EXPECTED_LINES),
        ("enforcer/enforcer_main.py", "enforcer_main.py", ENFORCER_EXPECTED_LINES),
    ],
)
def test_app_files_have_correct_initial_lines(file_path, file_name, expected_lines):
    """Test that app files start with the required certificate handling code."""
    full_path = os.path.join(os.path.dirname(__file__), "..", file_path)

    with open(full_path, "r") as f:
        lines = f.readlines()

    for i, expected_line in enumerate(expected_lines):
        assert (
            lines[i] == expected_line
        ), f"Line {i + 1} should be: {expected_line.strip()!r}, but got: {lines[i].strip()!r}. This tests make sure the import order in {file_name} file is correct, if you see this, go to {file_name} file and move your imports code to lower lines."
