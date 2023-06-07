################################################################
# This script is a shortcut to run PySpacely within venv       #
#                                                              #
# It will be slow this way - you should activate venv yourself #
#  if you're planning on running it multiple times.            #
################################################################

# Go to the directory where this script is located
$scriptpath = $MyInvocation.MyCommand.Path
$dir = Split-Path $scriptpath
Push-Location "$dir"

# Activate Python's virtual environment if not active
if (-Not (Test-Path env:VIRTUAL_ENV)) {
    if (-Not (Test-Path -Path ".\venv\Scripts\activate" -PathType Leaf)) {
        echo "Python virtual environment not found - you should probably run SetupWindows.ps1 first"
        exit
    }

    echo "Python virtual environment not active - activating"
	.\venv\Scripts\activate
}

Invoke-Expression "python .\Spacely.py $args"