#!/bin/bash

# Check if Python virtual environment is active
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Virtual environment is not active."
    # Check if activate script exists
    if [[ -f "./venv/Scripts/activate" ]]; then
        echo "Activating existing virtual environment."
        # Run activate script
        source ./venv/bin/activate
    else
        echo "Creating and activating new virtual environment."
        # Create virtual environment
        python3.12 -m venv venv
        # Activate virtual environment
        source ./venv/bin/activate
    fi
else
    echo "Virtual environment is already active."
fi

# Upgrade pip to the latest version
echo "Upgrading pip to the latest version."
pip install --upgrade pip

# Install dependencies from requirements.txt
echo "Installing general Python requirements..."
pip install -r ./requirements/requirements-python.txt

echo "Installing py-libs-common via HTTPS..."
python -m pip install --upgrade --force-reinstall -r ./requirements/requirements-py-libs-common.txt 

echo "Setup complete."
