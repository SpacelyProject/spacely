##################################################################
# This script is a shortcut to configure the Spacely environment #
##################################################################

param (
    [switch]$lite = $false
)

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

if ($lite) {
    echo "Installing dependencies (LITE)..."
    python -m pip install -r requirements_lite.txt
}else {
    echo "Installing dependencies..."
    python -m pip install -r requirements.txt
}




echo "Now you should be able to run Spacely"