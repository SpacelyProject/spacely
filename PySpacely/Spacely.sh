#!/bin/bash

# Check if Python virtual environment is active
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Virtual environment is not active."
    # Check if activate script exists
    if [[ -f "./venv/bin/activate" ]]; then
        echo "Activating existing virtual environment."
        # Run activate script
        source ./venv/bin/activate
    else
        echo "Your virtual environment has not been set up! You should probably run SetupLinux.sh first."
	exit 1
    fi
else
    echo "Virtual environment is already active."
fi





python ./Spacely.py "$@"
