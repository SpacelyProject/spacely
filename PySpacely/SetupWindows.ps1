##################################################################
# This script is a shortcut to configure the Spacely environment #
##################################################################


# Go to the directory where this script is located
$scriptpath = $MyInvocation.MyCommand.Path
$dir = Split-Path $scriptpath
Push-Location "$dir"

# Activate Python's virtual environment if not active
if (-Not (Test-Path env:VIRTUAL_ENV)) {
    echo "Python virtual environment not active - activating"

    if (-Not (Test-Path -Path ".\venv\Scripts\activate" -PathType Leaf)) {
        echo "Python virtual environment not found - creating"
        python -m venv venv
    }

	.\venv\Scripts\activate
}	
	

# First, make sure pip is upgraded to the latest version.
python -m pip install --upgrade pip

echo "Installing general Python dependencies..."
python -m pip install -r .\requirements\requirements-python.txt

echo "Installing py-libs-common using HTTPS..."
python -m pip install --upgrade --force-reinstall -r .\requirements\requirements-py-libs-common.txt

echo "Now you should be able to run Spacely"