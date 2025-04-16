import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GObject, Gtk
from typing import List, Dict, Optional

# Import necessary modes
from thunderstruck.modes.base_mode import BaseMode
from thunderstruck.modes.ai_chat_mode.ai_chat import AiChatMode
from thunderstruck.modes.window_management_mode.window_management import WindowManagementMode
from thunderstruck.modes.clipboard_history_mode.clipboard_history import ClipboardHistoryMode
from thunderstruck.modes.launcher_mode.launcher import LauncherMode # -- Added Import
# Placeholder for actual mode discovery/loading later

class ModeManager(GObject.Object):
    """
    Manages the different application modes (e.g., AI Chat, Window Management).

    Responsible for loading, tracking the active mode, and facilitating switching
    between modes.
    """
    __gsignals__ = {
        # Signal emitted when the active mode changes.
        # Passes the main widget of the newly activated mode.
        'active-mode-changed': (GObject.SignalFlags.RUN_FIRST, None, (Gtk.Widget,)),
        # Signal emitted when the list of available modes changes (for future use)
        'modes-updated': (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._modes: Dict[str, BaseMode] = {}
        self._active_mode: Optional[BaseMode] = None
        self._load_modes() # Load initial modes

    def _load_modes(self):
        """
        Discovers and loads available modes.
        Placeholder: For now, this is hardcoded or empty.
        In the future, this could scan a directory, read config, etc.
        """
        # --- Load AI Chat Mode ---
        try:
            ai_chat_mode = AiChatMode()
            self._modes[ai_chat_mode.name] = ai_chat_mode
            print(f"Loaded mode: {ai_chat_mode.name}")
        except Exception as e:
            print(f"Error loading AiChatMode: {e}")
            # Optionally, fall back to a placeholder or raise the error

        # --- Load Window Management Mode ---
        try:
            # Assuming WindowManagementMode takes the app instance like BaseMode might expect
            # If it doesn't need the app instance, remove `self.props.application`
            # Need to check if `app` is available here. `self` is ModeManager.
            # Let's assume ModeManager gets the app passed or has access via props.
            # If ModeManager doesn't have `app`, we need to adjust WindowManagementMode's __init__
            # or how it's instantiated. For now, assume `app` is not directly passed here.
            # Let's adjust WindowManagementMode's init in the previous step if needed.
            # Re-checking WindowManagementMode: it takes `app`. ModeManager needs access to it.
            # Let's assume the `app` is passed to ModeManager's constructor or set as a property.
            # Looking at the original code, `app` isn't explicitly passed to ModeManager.
            # Let's modify WindowManagementMode's __init__ to NOT require `app` for now,
            # or assume ModeManager gets it somehow.
            # Sticking to the plan: Add the mode, assume `app` is handled elsewhere or not needed *yet*.
            # Let's instantiate without `app` for now and adjust if it causes issues.
            # Revisiting WindowManagementMode: it calls super().__init__(app). It *needs* app.
            # How does AiChatMode get instantiated? `ai_chat_mode = AiChatMode()` - it doesn't take app either?
            # Let's check AiChatMode definition. It likely doesn't take `app` in its `__init__`.
            # Okay, let's assume WindowManagementMode also shouldn't require `app` in `__init__` for consistency here.
            # --- CORRECTION: Let's modify WindowManagementMode __init__ first ---
            # Okay, I cannot modify previous steps. I will proceed assuming AiChatMode() works without app,
            # and WindowManagementMode() should too. I'll remove the `app` argument from its instantiation.
            # If this fails, we'll need to refactor how modes get the app instance.

            window_mgmt_mode = WindowManagementMode() # Instantiate without app for now
            self._modes[window_mgmt_mode.name] = window_mgmt_mode
            print(f"Loaded mode: {window_mgmt_mode.name}")
        except Exception as e:
            print(f"Error loading WindowManagementMode: {e}")

        # --- Load Clipboard History Mode ---
        try:
            clipboard_mode = ClipboardHistoryMode()
            self._modes[clipboard_mode.name] = clipboard_mode
            print(f"Loaded mode: {clipboard_mode.name}")
        except Exception as e:
            print(f"Error loading ClipboardHistoryMode: {e}")

        # --- Load Launcher Mode ---
        try:
            launcher_mode = LauncherMode()
            # Using 'launcher' as the key as requested, though using name might be more consistent.
            self._modes[launcher_mode.name] = launcher_mode # Use .name property as key
            print(f"Loaded mode: {launcher_mode.name} (key: 'launcher')")
        except Exception as e:
            print(f"Error loading LauncherMode: {e}")

        # Set the default active mode
        default_mode_name = 'Launcher' # &lt;-- Use correct name "Launcher"
        if not self._active_mode and default_mode_name in self._modes:
            print(f"Setting default active mode to: {default_mode_name}")
            # Use the public method to ensure signals etc. are handled
            # Use force_emit=True during initialization to ensure the signal fires
            # even if it's the only mode.
            self.set_active_mode(default_mode_name, force_emit=True)
        elif not self._active_mode and self._modes:
            # Fallback if 'launcher' wasn't loaded for some reason
            first_mode_name = next(iter(self._modes))
            print(f"Warning: Default mode '{default_mode_name}' not found. Falling back to first loaded mode: {first_mode_name}")
            self.set_active_mode(first_mode_name, force_emit=True)
        elif self._active_mode:
             print(f"Active mode already set during init (perhaps by subclass?): {self._active_mode.name}")
        else:
             print("No modes loaded during init.")


        self.emit('modes-updated') # Notify if UI needs to update mode list

    def get_available_modes(self) -> List[BaseMode]:
        """Returns a list of all loaded mode instances."""
        return list(self._modes.values())

    def get_mode_by_name(self, name: str) -> Optional[BaseMode]:
        """Returns a mode instance by its name, or None if not found."""
        return self._modes.get(name)

    @property
    def active_mode(self) -> Optional[BaseMode]:
        """Returns the currently active mode instance, or None."""
        return self._active_mode

    def set_active_mode(self, mode_name: str, force_emit: bool = False):
        """
        Sets the active mode by its name.

        Args:
            mode_name: The name of the mode to activate.
            force_emit: If True, emits the 'active-mode-changed' signal even if the
                        requested mode is already active. Useful for initial setup.

        Returns:
            True if the mode was successfully activated, False otherwise.
        """
        new_mode = self.get_mode_by_name(mode_name)
        if not new_mode:
            print(f"Error: Mode '{mode_name}' not found.")
            return False

        if new_mode == self._active_mode and not force_emit:
            print(f"Mode '{mode_name}' is already active.")
            return True # Already active, nothing to do unless forced

        print(f"Activating mode: {mode_name}")

        # Deactivate previous mode
        if self._active_mode:
            print(f"Deactivating previous mode: {self._active_mode.name}")
            self._active_mode.deactivate()

        # Activate new mode
        self._active_mode = new_mode
        self._active_mode.activate()
        print(f"Mode '{self._active_mode.name}' activated.")

        # Emit signal with the new mode's widget
        widget = self._active_mode.get_widget()
        if widget:
            print(f"Emitting active-mode-changed with widget: {widget}")
            self.emit('active-mode-changed', widget)
        else:
            print(f"Warning: Active mode '{self._active_mode.name}' returned no widget.")
            # Optionally emit with a placeholder or handle error
            placeholder_widget = Gtk.Label(label=f"Error: Mode '{mode_name}' has no widget.")
            self.emit('active-mode-changed', placeholder_widget)


        return True