#!/usr/bin/env python3

import sys
import os


# Add the project root directory to the Python path
# This allows importing the 'thunderstruck' package
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from thunderstruck import main
except ImportError as e:
    print(f"Error importing thunderstruck package: {e}", file=sys.stderr)
    print("Please ensure the script is run from the project root directory", file=sys.stderr)
    print("or that the 'thunderstruck' package is correctly installed.", file=sys.stderr)
    sys.exit(1)
from gi.repository import Gio

# Load and register the compiled resource
resource = Gio.Resource.load("thunderstruck.gresource")
Gio.resources_register(resource)

if __name__ == "__main__":
    # Run the main application function
    # Pass command-line arguments, excluding the script name itself
    sys.exit(main.run(sys.argv))