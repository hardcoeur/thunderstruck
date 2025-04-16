import sys
import os
import gi

# Set the Gtk version to 4.0 and Adwaita to 1
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gio, GLib # Import only Gio and GLib initially
import logging # For basic logging configuration

# Now import Gtk and Adw after resources are registered
from gi.repository import Gtk, Adw # Import Gtk/Adw

# --- Load and register compiled resources ---
try:
    # Assume resource file is in the parent directory relative to main.py
    resource_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'thunderstruck.gresource'))
    print(f"Attempting to load resource file: {resource_path}")
    if os.path.exists(resource_path):
        resource = Gio.Resource.load(resource_path)
        Gio.resources_register(resource)
        print("Resources loaded successfully.")
        # --- BEGIN DIAGNOSTIC CHECK ---
        try:
            lookup_path = '/org/example/Thunderstruck/ui/main_window.ui' # Check one template path
            print(f"Attempting manual lookup for: {lookup_path}")
            data_bytes = Gio.resources_lookup_data(lookup_path, Gio.ResourceLookupFlags.NONE)
            if data_bytes:
                print(f"MANUAL LOOKUP SUCCESS: Found resource {lookup_path}, size: {data_bytes.get_size()}")
            else:
                print(f"MANUAL LOOKUP FAILED: Resource {lookup_path} not found (returned None).")
                sys.exit(1) # Exit if lookup fails here
        except GLib.Error as e:
            print(f"MANUAL LOOKUP FAILED: Resource {lookup_path} not found. Error: {e}")
            sys.exit(1) # Exit if lookup fails here
        # --- END DIAGNOSTIC CHECK ---
    else:
        print(f"Resource file not found at {resource_path}. Please compile it using glib-compile-resources.", file=sys.stderr)
        sys.exit(1) # Indicate failure
except GLib.Error as e:
    print(f"Error loading/registering resource file {resource_path}: {e}", file=sys.stderr)
    sys.exit(1) # Indicate failure
# --- End Resource Loading ---
# from .components.welcome_screen.welcome_screen import OutputRedirector # Import needed for redirection block below


# # --- Output Redirection ---
# # Store original streams BEFORE redirecting
# original_stdout = sys.stdout
# original_stderr = sys.stderr
#
# # Instantiate the redirector, passing the original stdout
# # Instantiate the redirector (now takes no arguments)
# output_capture = OutputRedirector()
#
# # Redirect stdout and stderr to our capture object
# sys.stdout = output_capture
# sys.stderr = output_capture
#
# # Configure basic logging to use the redirected streams
# logging.basicConfig(level=logging.INFO, stream=sys.stdout) # Use redirected stdout
# print("--- Stdout/Stderr redirected ---") # Message to confirm redirection setup
# # --- End Output Redirection ---


# Define a unique application ID (replace with your actual ID)
# Follows reverse domain name notation
APP_ID = "org.example.Thunderstruck" # TODO: Replace with a real ID later


def run(argv):
    """
    Initializes and runs the Thunderstruck GTK application.

    Args:
        argv (list): Command line arguments passed to the application.

    Returns:
        int: The exit status of the application.
    """
    print("Starting Thunderstruck...") # Basic startup message

    # TODO: Replace placeholder Application instantiation when the class is created
    # Import Application class just before instantiation
    from .application import Application

    # Pass the output_capture instance to the Application
    # Pass the output_capture instance to the Application
    # app = Application(application_id=APP_ID, output_capture=output_capture) # flags=Gio.ApplicationFlags.FLAGS_NONE - Add if needed
    app = Application(application_id=APP_ID) # Instantiate without output_capture for now
    return app.run(argv)
