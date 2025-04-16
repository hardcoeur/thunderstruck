import gi
import sys
import logging

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio, GLib, Gdk # Import Gdk for Display

# Placeholder imports for components we will create later
from .components.main_window.window import MainWindow
from .components.shortcut_listener import ShortcutListener
from .mode_manager import ModeManager 
from .components.preferences_window.preferences import PreferencesDialog 
from .components.welcome_screen.welcome_screen import WelcomeWindow 
from .components.gnome_status_icon.status_icon import GnomeStatusIcon 
class Application(Adw.Application):
    """
    The main Thunderstruck GTK Application class.
    """
    def __init__(self, output_capture=None, **kwargs):
        """
        Initializes the Thunderstruck Application.

        Args:
            output_capture (OutputRedirector, optional): An instance of OutputRedirector to capture stdout/stderr. Defaults to None.
            **kwargs: Additional keyword arguments for Adw.Application.
        """
        # Call the parent class constructor
        super().__init__(**kwargs)
        self.output_capture = output_capture # Store the redirector instance

        # Application-level state (will be initialized later)
        self.main_window = None
        self.welcome_window = None # Add attribute for the welcome window
        # self.tray_icon = None # Removed
        self.shortcut_listener = None
        self.mode_manager = None
        self.settings = None
        self.preferences_window = None
        self.status_icon = None # Add attribute for the status icon

        # Connect signals
        self.connect('activate', self.on_activate)
        self.connect('startup', self.on_startup) # Use for initializing components
        self.connect('shutdown', self.on_shutdown) # Use if cleanup is needed

        # Connect to the output capture signal
        if self.output_capture:
            self.output_capture.connect("message-captured", self._on_message_captured)
            print("Connected to output_capture signal 'message-captured'.")
        else:
            print("Warning: No output_capture instance provided to Application.", file=sys.stderr)


        print(f"Thunderstruck Application initialized (ID: {self.get_application_id()})")


    def on_activate(self, app):
        """
        Called when the application is activated. Shows the WelcomeWindow.
        The MainWindow creation is deferred.
        """
        print("Application activated.")

        # Create and show the Welcome Window instead of the Main Window
        if not self.welcome_window:
            print("Creating welcome window...")
            # Ensure ModeManager is ready if WelcomeWindow needs it (it doesn't currently)
            # if not self.mode_manager:
            #     print("Error: ModeManager not initialized!", file=sys.stderr)
            #     return # Or handle error
            self.welcome_window = WelcomeWindow(application=self)
            # Add a destroy handler if needed later to know when it closes
            # self.welcome_window.connect("destroy", self.on_welcome_window_destroy)

        # Always present the welcome window on activation for now
        # (Later, logic might check if main window is already running)
        if self.welcome_window:
            print("Presenting welcome window.")
            self.welcome_window.present()
        else:
            print("Error: Welcome window could not be created.", file=sys.stderr)

    def _on_message_captured(self, emitter, message):
        """Handles messages captured by the OutputRedirector."""
        # print(f"DEBUG App received message: {message}") # Uncomment for debugging
        if self.welcome_window and not self.welcome_window.is_destroyed():
            # Forward the message to the welcome window's handler
            self.welcome_window.add_status_message(message)
        # Optionally, log messages even if welcome window is gone
        # logging.debug(f"Captured Output: {message}")

    def show_main_window(self):
        """Creates (if necessary) and presents the main application window."""
        print("Application: show_main_window called.")
        if not self.main_window or self.main_window.is_destroyed():
            print("Creating main window...")
            if not self.mode_manager:
                 print("Error: ModeManager not initialized before creating MainWindow!", file=sys.stderr)
                 logging.error("ModeManager not initialized before creating MainWindow!")
                 # Handle error appropriately, maybe exit or fallback
                 return # Prevent crash
            # Create the main window instance, passing the application reference and mode manager
            self.main_window = MainWindow(application=self, mode_manager=self.mode_manager)
            # Handle potential creation failure (though less likely now)
            if not self.main_window:
                print("Error: Main window could not be created.", file=sys.stderr)
                logging.error("Failed to create MainWindow instance.")
                return

        print("Presenting main window.")
        self.main_window.present()

    def on_startup(self, app):
        """Called once when the application first starts."""
        print("Application starting up.")
        logging.info("Application starting up.")
        # Perform initial setup like loading settings, initializing components
        # self.settings = Settings()
        print("Initializing Mode Manager...")
        self.mode_manager = ModeManager() # Initialize ModeManager

        # Tray Icon initialization removed due to GTK3/GTK4 incompatibility
        logging.warning("Tray icon functionality has been removed.")
        # Define application actions
        self._setup_actions()

        # Initialize Shortcut Listener
        print("Initializing Shortcut Listener...")
        logging.info("Initializing Shortcut Listener...")
        try:
            self.shortcut_listener = ShortcutListener(self)
            self.shortcut_listener.start()
        except Exception as e:
            logging.error(f"Failed to initialize ShortcutListener: {e}", exc_info=True)
            self.shortcut_listener = None # Ensure it's None if init fails

        # Load custom CSS
        self._load_css()

        # Initialize GNOME Status Icon
        print("Initializing GNOME Status Icon...")
        logging.info("Initializing GNOME Status Icon...")
        try:
            # Pass the application instance to the status icon
            self.status_icon = GnomeStatusIcon(self)
            logging.info("GnomeStatusIcon initialized.")
        except Exception as e:
            logging.error(f"Failed to initialize GnomeStatusIcon: {e}", exc_info=True)
            self.status_icon = None # Ensure it's None if init fails

        logging.info("Application startup complete.")
    def on_shutdown(self, app):
        """Called when the application is shutting down."""
        print("Application shutting down.")
        logging.info("Application shutting down.")
        # Perform cleanup tasks
        if self.shortcut_listener:
            self.shortcut_listener.stop()
        if self.status_icon:
            logging.info("Cleaning up GnomeStatusIcon.")
            self.status_icon.cleanup()
    #     # if self.settings:
    #     #     self.settings.save() # Example
        pass

    def _setup_actions(self):
        """Define application-level actions."""
        # --- Toggle Window Action ---
        action = Gio.SimpleAction.new("toggle_window", None)
        action.connect("activate", self.on_toggle_window_action)
        self.add_action(action)
        logging.debug("Added 'toggle_window' action.")

        # --- Quit Action (already provided by Gtk.Application) ---
        # We connect the tray menu directly to "app.quit"

        # --- Preferences Action ---
        prefs_action = Gio.SimpleAction.new("preferences", None)
        prefs_action.connect("activate", self.on_preferences)
        self.add_action(prefs_action)
        logging.debug("Added 'preferences' action.")

        # --- About Action ---
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about)
        self.add_action(about_action)
        logging.debug("Added 'about' action.")

    def on_toggle_window_action(self, action, param):
        """Handles the 'toggle_window' action activation."""
        logging.debug("on_toggle_window_action handler called.") # Added for debugging status icon click
        logging.debug("Toggle window action triggered.")
        if not self.main_window:
            logging.warning("Toggle action called but main window does not exist.")
            # Optionally, activate the app to create the window if it was closed
            # self.activate()
            return

        if self.main_window.is_visible():
            logging.info("Hiding main window.")
            self.main_window.hide()
            # Optionally update tray icon state if needed
            # Tray icon reference removed
        else:
            logging.info("Showing main window.")
            self.main_window.present() # 'present' brings to front and shows
            # Optionally update tray icon state if needed
            # Tray icon reference removed

    def on_preferences(self, action, param):
        """Handles the 'preferences' action activation."""
        logging.debug("Preferences action triggered.")
        # Create the preferences window if it doesn't exist or has been destroyed
        # Using 'transient_for' and 'modal' ensures it behaves like a dialog
        # Check if the window reference is None (meaning it was closed or never opened)
        if self.preferences_window is None:
             # Pass the main window as transient parent if it exists, otherwise None
            parent = self.main_window if self.main_window else None
            self.preferences_window = PreferencesDialog()
            # Connect the destroy signal to clear the reference
            self.preferences_window.connect("destroy", self._on_preferences_window_destroy)
            logging.info("Created new PreferencesDialog instance.")

        self.preferences_window.present()

    def on_about(self, action, param):
        """Handles the 'about' action activation."""
        logging.debug("About action triggered.")
        about_window = Adw.AboutWindow(
            application_name="Thunderstruck",
            application_icon="org.example.Thunderstruck", # Make sure this icon name is defined
            developer_name="copyleft by Robert Renling", # Placeholder
            version="0.1.0", # Placeholder
            # transient_for=self.get_active_window(), # Use active window as parent
            modal=True,
        )
        # Set transient_for if a window exists
        active_window = self.get_active_window()
        if active_window:
             about_window.set_transient_for(active_window)

        about_window.present()
        logging.info("Presented About window.")
    def _on_preferences_window_destroy(self, widget):
        """Callback function for when the preferences window is destroyed."""
        print("Preferences window destroyed, clearing reference.")
        self.preferences_window = None


    def _load_css(self):
        """Loads the custom CSS file."""
        css_provider = Gtk.CssProvider()
        resource_path = '/org/example/Thunderstruck/css/style.css'

        try:
            css_provider.load_from_resource(resource_path)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), # Gdk is already imported
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            logging.info(f"Loaded custom CSS from resource: {resource_path}")
            print(f"Loaded custom CSS from resource: {resource_path}")
        except GLib.Error as e:
            # GLib.Error is raised if the resource doesn't exist
            logging.error(f"Failed to load CSS from resource {resource_path}: {e}", exc_info=True)
            print(f"Error loading CSS from resource {resource_path}: {e}", file=sys.stderr)
        except Exception as e:
            # Catch other potential errors during loading/applying
            logging.error(f"Unexpected error loading CSS from resource {resource_path}: {e}", exc_info=True)
            print(f"Unexpected error loading CSS from resource {resource_path}: {e}", file=sys.stderr)
