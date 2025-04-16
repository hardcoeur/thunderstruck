import gi
# import os # No longer needed for filename path

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio, GLib, GObject, Gdk # Import Gdk

# Import ModeManager
from ...mode_manager import ModeManager # Adjusted relative import
from ...modes.launcher_mode.launcher import LauncherWidget # Import LauncherWidget

# Use Gtk.Template with the .blp file directly
@Gtk.Template(resource_path='/org/example/Thunderstruck/ui/main_window.ui')
class MainWindow(Adw.ApplicationWindow):
    """
    The main window for the Thunderstruck application.
    It will contain the main UI elements and host the different modes
    via an Adw.ViewStack managed by the ModeManager.
    """
    __gtype_name__ = 'MainWindow' # Explicitly define GType name

    # Define Template Children (widgets defined in the .blp file)
    mode_stack: Adw.ViewStack = Gtk.Template.Child() # Reference the Adw.ViewStack with id="mode_stack"
    mode_selector_box: Gtk.Box = Gtk.Template.Child() # Reference the Gtk.Box with id="mode_selector_box"

    def __init__(self, mode_manager: ModeManager, **kwargs):
        """
        Initializes the MainWindow.

        Args:
            mode_manager: The application's ModeManager instance.
            **kwargs: Additional arguments for Adw.ApplicationWindow.
        """
        super().__init__(**kwargs)
        # Menu is now defined directly in the main_window.blp file within the Gtk.MenuButton.
        # No need to create or set the menu model programmatically here.


        if not isinstance(mode_manager, ModeManager):
             raise TypeError("MainWindow requires a valid ModeManager instance.")
        self._mode_manager = mode_manager

        # Initialize the template *after* parent __init__

        print("MainWindow initialized and template bound.")

        # Connect to the ModeManager's signal
        self._mode_manager.connect('active-mode-changed', self._on_active_mode_changed)

        # Trigger initial mode display if a mode is already active in the manager
        # Ensure this runs after the main loop starts potentially, or check widget visibility
        # Using GLib.idle_add to ensure the UI is ready might be safer sometimes,
        # but let's try direct call first.
        if self._mode_manager.active_mode:
            print("MainWindow: Initial mode detected, triggering display.")
            initial_widget = self._mode_manager.active_mode.get_widget()
            if initial_widget:
                 # Directly call the handler now that the template is initialized
                 self._on_active_mode_changed(self._mode_manager, initial_widget)
            else:
                 print("MainWindow: Initial active mode has no widget.")

       # Populate the mode selector bar
        self._populate_mode_selector()

       # TODO: Connect signals from other UI elements defined in the .blp file
       # Example: self.search_entry.connect('search-changed', self.on_search_changed)
        # Connect visibility signal for focus management
        self.connect("notify::visible", self._on_visibility_changed)

        # Add Escape key handler
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE) # Add this line
        self.add_controller(key_controller)

    # --- Signal Handlers ---

    # No need for @GObject.Signal decorator here, it's a regular method callback
    def _on_active_mode_changed(self, mode_manager: ModeManager, new_widget: Gtk.Widget):
        """
        Called when the ModeManager signals a change in the active mode.
        Adds the new mode's widget to the ViewStack (if not already present)
        and makes it visible.
        """
        active_mode = mode_manager.active_mode
        if not active_mode:
            print("Warning: _on_active_mode_changed called but ModeManager has no active mode.")
            # Optionally clear the stack or show a default page
            # Example: Find a way to show a default "no mode" page if needed
            # existing_default = self.mode_stack.get_child_by_name("default_empty_page")
            # if existing_default: self.mode_stack.set_visible_child(existing_default)
            return

        mode_name = active_mode.name
        print(f"MainWindow: Handling active-mode-changed signal for mode '{mode_name}' with widget {new_widget}")

        # Check if the widget is already a child of the stack under the correct name
        existing_page = self.mode_stack.get_child_by_name(mode_name)

        if existing_page is None:
            print(f"MainWindow: Adding widget for mode '{mode_name}' to the ViewStack.")
            # Add the widget to the stack with the mode's name as the page name
            self.mode_stack.add_named(new_widget, mode_name)
            # Ensure the new widget is shown immediately after adding
            self.mode_stack.set_visible_child(new_widget) # Use set_visible_child for direct widget reference
            print(f"MainWindow: CONFIRM visible child name after set: {self.mode_stack.get_visible_child_name()}")
            print(f"MainWindow: Set visible child to newly added widget for '{mode_name}'")
            return # Added and shown, done.

        elif existing_page != new_widget:
             print(f"MainWindow: Warning - Widget for mode '{mode_name}' changed. Replacing in ViewStack.")
             # If the widget somehow changed for the same mode name, replace it
             self.mode_stack.remove(existing_page)
             self.mode_stack.add_named(new_widget, mode_name)
             # Ensure the replacement is shown
             self.mode_stack.set_visible_child(new_widget)
             print(f"MainWindow: CONFIRM visible child name after set: {self.mode_stack.get_visible_child_name()}")
             print(f"MainWindow: Set visible child to replaced widget for '{mode_name}'")
             return # Replaced and shown, done.
        else:
             # Widget exists and is the same, just ensure it's visible
             print(f"MainWindow: Widget for mode '{mode_name}' already in ViewStack. Ensuring visibility.")
             self.mode_stack.set_visible_child(new_widget) # Or set_visible_child_name(mode_name)
             print(f"MainWindow: CONFIRM visible child name after set: {self.mode_stack.get_visible_child_name()}")
             print(f"MainWindow: Set visible child to existing widget for '{mode_name}'")

    def _populate_mode_selector(self):
        """
        Populates the mode selector box with buttons for each available mode.
        """
        print("MainWindow: Populating mode selector.")
        available_modes = self._mode_manager.get_available_modes()
        print(f"MainWindow: Found modes: {[mode.name for mode in available_modes]}")

        # Clear any existing children (in case this is called again)
        child = self.mode_selector_box.get_first_child()
        while child:
            self.mode_selector_box.remove(child)
            child = self.mode_selector_box.get_first_child()

        for mode in available_modes:
            button = Gtk.Button()
            icon = Gtk.Image.new_from_icon_name(mode.icon_name)
            button.set_child(icon) # Use set_child for Gtk 4
            button.set_tooltip_text(mode.name)
            # Connect the signal, passing the mode name
            button.connect('clicked', self._on_mode_button_clicked, mode.name)
            self.mode_selector_box.append(button) # Use append for Gtk.Box
            print(f"MainWindow: Added button for mode '{mode.name}' with icon '{mode.icon_name}'")

    def _on_mode_button_clicked(self, button: Gtk.Button, mode_name: str):
        """
        Handles clicks on the mode selector buttons.
        """
        print(f"MainWindow: Mode button clicked for '{mode_name}'.")
        self._mode_manager.set_active_mode(mode_name)

    def _on_visibility_changed(self, *args):
        """
        Handles the window becoming visible. If the LauncherMode is active,
        focus the search entry.
        """
        if self.is_visible():
            print("MainWindow: Visibility changed to visible.")
            active_widget = self.mode_stack.get_visible_child()
            if isinstance(active_widget, LauncherWidget):
                print("MainWindow: Active widget is LauncherWidget, attempting to focus search_entry.")
                if active_widget.search_entry: # Check if search_entry exists
                     active_widget.search_entry.grab_focus()
                     print("MainWindow: search_entry focused.")
                else:
                     print("MainWindow: Warning - search_entry not found on LauncherWidget.")
            elif active_widget:
                print(f"MainWindow: Active widget is {type(active_widget).__name__}, not focusing.")
            else:
                print("MainWindow: No active widget visible when window shown.")

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handles key press events for the main window."""
        if keyval == Gdk.KEY_Escape:
            print(">>> MainWindow: Escape key detected.") # Start marker
            active_mode = self._mode_manager.active_mode
            handled_by_mode = False

            if active_mode and hasattr(active_mode, 'handle_escape'):
                print(f">>> MainWindow: Checking mode '{active_mode.name}' for escape handling.")
                try:
                    # Call the mode's handler
                    handled_by_mode = active_mode.handle_escape()
                    print(f">>> MainWindow: Mode '{active_mode.name}' handle_escape returned: {handled_by_mode}")
                except Exception as e:
                    # Log errors during delegation but treat as unhandled
                    print(f">>> MainWindow: Error calling handle_escape for mode '{active_mode.name}': {e}")
                    handled_by_mode = False
            else:
                 print(">>> MainWindow: No active mode or mode has no handle_escape method.")


            # Mode has had its chance to handle Escape (e.g., clear search).
            # Now, unconditionally hide the window.
            print(">>> MainWindow: Proceeding to hide window after mode handling (if any).")
            try:
                self.hide()
                print(">>> MainWindow: self.hide() called successfully.")
            except Exception as e:
                print(f">>> MainWindow: Error calling self.hide(): {e}")

            # Always return True for Escape to prevent further propagation
            print(">>> MainWindow: Returning True from _on_key_pressed for Escape.")
            return True
        return False # Event not handled

# --- Public Methods ---
# (No public methods needed for mode switching now, handled by signal)