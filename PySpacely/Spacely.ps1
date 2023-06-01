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
    echo "Python virtual environment not active - activating"

    if (-Not (Test-Path -Path C:\temp\important_file.txt -PathType Leaf)) {
        echo "Python virtual environment not found - creating"
        python -m venv venv
        python -m pip install -r requirements.txt
    }

	.\venv\Scripts\activate
}

Invoke-Expression "python .\Spacely.py $args"