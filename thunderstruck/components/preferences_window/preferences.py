import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GObject, Gdk

# Define the GSettings schema ID
SCHEMA_ID = "org.example.Thunderstruck"

@Gtk.Template(resource_path='/org/example/Thunderstruck/ui/preferences.ui')
class PreferencesDialog(Adw.PreferencesDialog):
    __gtype_name__ = 'PreferencesDialog'
    shortcut_label = Gtk.Template.Child()
    set_shortcut_button = Gtk.Template.Child()
    vertex_api_key_row = Gtk.Template.Child()
    openrouter_api_key_row = Gtk.Template.Child()
    general_group = Gtk.Template.Child()
    api_keys_group = Gtk.Template.Child()
    launcher_group = Gtk.Template.Child() # Added for Launcher settings
    launcher_max_results_row = Gtk.Template.Child() # Added for Launcher settings

# TODO: Implement shortcut setting logic later

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = Gio.Settings.new(SCHEMA_ID)

        # Page and groups are already defined and structured in the UI template.
        # No need to create page or reparent groups programmatically.

        # Bindings remain the same, as the rows/widgets are children of the groups
        self.settings.bind("global-shortcut", self.shortcut_label, "label", Gio.SettingsBindFlags.DEFAULT)
        self.set_shortcut_button.connect("clicked", self._on_set_shortcut_clicked)
        self.settings.bind("vertex-ai-api-key", self.vertex_api_key_row, "text", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("openrouter-api-key", self.openrouter_api_key_row, "text", Gio.SettingsBindFlags.DEFAULT)

        # Bind Launcher settings
        # Note: We bind to the 'value' property of the *adjustment* within the SpinRow
        self.settings.bind("launcher-max-results",
                           self.launcher_max_results_row.get_adjustment(), # Get the Gtk.Adjustment
                           "value",                                        # Bind its 'value' property
                           Gio.SettingsBindFlags.DEFAULT)

        print("PreferencesDialog initialized, page created, and settings bound")

    def _on_set_shortcut_clicked(self, button):
        """Handles the click event of the 'Set Shortcut' button."""
        dialog = Adw.MessageDialog(
            transient_for=self.get_root(), # Ensure dialog is attached to the window
            modal=True,
            heading=_("Set Global Shortcut"),
            body=_("Press the desired key combination.\nPress Escape to cancel."),
        )
        dialog.add_response("cancel", _("Cancel"))
        # We don't add an "ok" response, as capturing the keypress is the confirmation.

        captured_shortcut = None # Variable to store the result

        def on_key_pressed(controller, keyval, keycode, state):
            nonlocal captured_shortcut
            # Ignore modifier-only presses
            is_modifier = keyval in (
                Gdk.KEY_Control_L, Gdk.KEY_Control_R,
                Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_Meta_L, Gdk.KEY_Meta_R, # Alt/Meta
                Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
                Gdk.KEY_Super_L, Gdk.KEY_Super_R, Gdk.KEY_Hyper_L, Gdk.KEY_Hyper_R
            )
            if is_modifier:
                return True # Indicate event handled, but don't close dialog

            # Handle Escape key for cancellation
            if keyval == Gdk.KEY_Escape:
                print("Shortcut capture cancelled by Escape.")
                dialog.close()
                return True

            shortcut_str = self._accelerator_str_from_event(keyval, state)
            if shortcut_str:
                captured_shortcut = shortcut_str
                print(f"Captured shortcut: {captured_shortcut}")
                dialog.close() # Close dialog on successful capture
                return True # Indicate event handled
            else:
                print("Failed to format key event.")
                # Maybe show an error briefly? For now, just ignore.
                return False # Indicate event not fully handled

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", on_key_pressed)
        dialog.add_controller(key_controller)

        dialog.connect("response", self._on_capture_dialog_response, captured_shortcut)
        dialog.present()

    def _on_capture_dialog_response(self, dialog, response_id, captured_shortcut):
        """Handles the response from the shortcut capture dialog."""
        if response_id == "cancel":
            print("Shortcut capture cancelled by button.")
        elif captured_shortcut:
            try:
                # Save the captured shortcut to GSettings
                self.settings.set_string('global-shortcut', captured_shortcut)
                print(f"Saved new shortcut: {captured_shortcut}")
                # The label updates automatically due to the binding
            except Exception as e:
                print(f"Error saving shortcut: {e}")
                # Optionally show an error message to the user here
        else:
             print("Dialog closed without capturing a valid shortcut.")

        # Dialog is closed automatically by Adw.MessageDialog on response
        pass

    def _accelerator_str_from_event(self, keyval, state):
        """
        Converts a GDK key event (keyval + state) into a GTK accelerator string.
        e.g., (Gdk.KEY_space, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK) -> "<Control><Alt>Space"
        """
        # Basic implementation - might need refinement for edge cases/specific keys
        mods = []
        if state & Gdk.ModifierType.CONTROL_MASK:
            mods.append("<Control>")
        if state & Gdk.ModifierType.ALT_MASK: # Note: Alt is often META on Linux/X11
            mods.append("<Alt>")
        if state & Gdk.ModifierType.SHIFT_MASK:
            mods.append("<Shift>")
        if state & Gdk.ModifierType.SUPER_MASK:
            mods.append("<Super>") # Windows/Command key

        key_name = Gdk.keyval_name(keyval)
        if key_name is None:
            return None # Or handle error

        # Handle common cases like 'space' -> 'Space'
        if key_name == "space":
            key_name = "Space"
        elif len(key_name) == 1 and key_name.islower():
             key_name = key_name.upper() # Capitalize single letters like 't' -> 'T'


        return "".join(mods) + key_name
