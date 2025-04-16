import threading
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio
from pynput import keyboard
import re # For parsing the shortcut string

# Define the GSettings schema ID
SCHEMA_ID = "org.example.Thunderstruck"

# Mapping from GTK accelerator string parts to pynput keys
# Using lowercase for modifiers as we'll lowercase the input string parts
# Using Key attributes like .ctrl instead of specific _l/_r for broader compatibility
MODIFIER_MAP = {
    "<control>": keyboard.Key.ctrl,
    "<alt>": keyboard.Key.alt,
    "<shift>": keyboard.Key.shift,
    "<super>": keyboard.Key.cmd, # Map Super (Win/Cmd) to pynput's cmd
    "<meta>": keyboard.Key.alt, # Meta is often Alt
    # Add other potential modifiers if needed (e.g., <hyper>)
}

# Mapping for special key names (lowercase)
SPECIAL_KEY_MAP = {
    "space": keyboard.Key.space,
    "enter": keyboard.Key.enter,
    "return": keyboard.Key.enter, # Alias
    "esc": keyboard.Key.esc,
    "escape": keyboard.Key.esc, # Alias
    "tab": keyboard.Key.tab,
    "backspace": keyboard.Key.backspace,
    "delete": keyboard.Key.delete,
    "home": keyboard.Key.home,
    "end": keyboard.Key.end,
    "pageup": keyboard.Key.page_up,
    "pagedown": keyboard.Key.page_down,
    "up": keyboard.Key.up,
    "down": keyboard.Key.down,
    "left": keyboard.Key.left,
    "right": keyboard.Key.right,
    # Function keys F1-F12
    **{f"f{i}": getattr(keyboard.Key, f"f{i}") for i in range(1, 13)}
}
# Alternative: <Super>space (Windows/Command key + Space)
# DEFAULT_SHORTCUT = {keyboard.Key.cmd, keyboard.Key.space}

# Keep track of currently pressed keys (instance variable now)
# current_keys = set() # Moved to instance

class ShortcutListener:
    """
    Listens for a global keyboard shortcut in a separate thread
    and triggers an action on the main application thread.
    """
    def __init__(self, app):
        self.app = app
        self._listener_thread = None
        self._listener = None
        self._stop_event = threading.Event()
        self._current_keys = set() # Instance variable for pressed keys
        self._target_shortcut_set = set() # Parsed shortcut from settings

        # Get GSettings
        self.settings = Gio.Settings.new(SCHEMA_ID)

        # Load initial shortcut and connect to changes
        self._update_shortcut_from_settings()
        self.settings.connect("changed::global-shortcut", self._on_shortcut_setting_changed)

    def _parse_shortcut_string(self, shortcut_str):
        """Parses a GTK accelerator string into a set of pynput keys."""
        if not shortcut_str or not isinstance(shortcut_str, str):
            print(f"Error: Invalid shortcut string format: {shortcut_str}")
            return None

        # Regex to find modifiers like <Control> or the final key like Space or A
        parts = re.findall(r"(<[^>]+>|[^<]+)", shortcut_str)
        if not parts:
            print(f"Error: Could not parse shortcut string: {shortcut_str}")
            return None

        parsed_keys = set()
        final_key_part = parts[-1].lower() # Treat final key case-insensitively for lookup

        # Process modifiers
        for part in parts[:-1]:
            mod_key = MODIFIER_MAP.get(part.lower())
            if mod_key:
                parsed_keys.add(mod_key)
            else:
                print(f"Warning: Unknown modifier '{part}' in shortcut '{shortcut_str}'")

        # Process the final key
        final_key = SPECIAL_KEY_MAP.get(final_key_part)
        if final_key:
            parsed_keys.add(final_key)
        elif len(final_key_part) == 1 and 'a' <= final_key_part <= 'z':
            # Assume it's a letter key
            try:
                parsed_keys.add(keyboard.KeyCode.from_char(final_key_part))
            except ValueError:
                 print(f"Error: Could not create KeyCode for '{final_key_part}'")
                 return None # Failed parsing
        else:
            print(f"Error: Unknown or unsupported final key '{parts[-1]}' in shortcut '{shortcut_str}'")
            return None # Failed parsing

        if not parsed_keys: # Should have at least one key
             print(f"Error: No valid keys found after parsing '{shortcut_str}'")
             return None

        return parsed_keys

    def _update_shortcut_from_settings(self):
        """Reads the shortcut from GSettings, parses it, and updates the target set."""
        shortcut_str = self.settings.get_string('global-shortcut')
        print(f"Loading shortcut from settings: '{shortcut_str}'")
        parsed_set = self._parse_shortcut_string(shortcut_str)
        if parsed_set:
            self._target_shortcut_set = parsed_set
            print(f"Successfully parsed shortcut: {self._target_shortcut_set}")
        else:
            print(f"Failed to parse shortcut '{shortcut_str}'. Listener might not work correctly.")
            # Keep the old set or clear it? Let's clear it to prevent mismatch.
            self._target_shortcut_set = set()

    def _on_shortcut_setting_changed(self, settings, key):
        """Handler for the 'changed::global-shortcut' signal."""
        print(f"GSettings key '{key}' changed.")
        self._update_shortcut_from_settings()
        # Restart the listener to use the new shortcut
        print("Restarting listener due to shortcut change...")
        self.stop()
        # Short delay might be needed if stop() is not fully synchronous, but start() checks thread status.
        # time.sleep(0.1) # Consider adding if race conditions occur
        self.start()

    def _on_press(self, key):
        """Callback executed when a key is pressed."""
        # Check if the pressed key is part of our *target* shortcut
        if not self._target_shortcut_set: return # Don't process if shortcut invalid

        # Normalize key for comparison (handle KeyCode vs Key)
        compare_key = key
        if isinstance(key, keyboard.KeyCode):
             # Use char for comparison if it's a simple character
             compare_key = key.char if key.char else key

        # Check if the pressed key (or its char representation) is relevant
        key_is_relevant = False
        for target_key in self._target_shortcut_set:
            target_compare_key = target_key
            if isinstance(target_key, keyboard.KeyCode):
                 target_compare_key = target_key.char if target_key.char else target_key

            if compare_key == target_compare_key:
                 key_is_relevant = True
                 # Add the *original* pynput key object to the set
                 self._current_keys.add(key)
                 break # Found a match

        if key_is_relevant:
            # Check if all keys in the shortcut are currently pressed
            # We need a way to map the generic Key.ctrl etc. to the specific events (_l/_r)
            # or simplify the check. Let's check based on the *defined* target set.
            active_target_keys = set()
            for pressed in self._current_keys:
                 # Map specific keys (_l/_r) back to generic for checking against target_set
                 if pressed in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                     active_target_keys.add(keyboard.Key.ctrl)
                 elif pressed in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
                     active_target_keys.add(keyboard.Key.alt)
                 elif pressed in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                     active_target_keys.add(keyboard.Key.shift)
                 elif pressed in (keyboard.Key.cmd_l, keyboard.Key.cmd_r, keyboard.Key.cmd): # Use cmd, cmd_l, cmd_r
                     active_target_keys.add(keyboard.Key.cmd)
                 elif isinstance(pressed, keyboard.KeyCode):
                     # Add the char representation if possible
                     char = pressed.char if pressed.char else pressed
                     for target in self._target_shortcut_set:
                          if isinstance(target, keyboard.KeyCode) and (target.char if target.char else target) == char:
                               active_target_keys.add(target)
                               break
                 else: # Regular keys like space, enter, f1 etc.
                     active_target_keys.add(pressed)


            if self._target_shortcut_set.issubset(active_target_keys):
                print(f"Shortcut {self._target_shortcut_set} detected!") # Debug print
            # Note: The above check might be slightly lenient if e.g. only ctrl_l is pressed
            # but target just has ctrl. For most cases this should work.

            # Check if all keys in the target shortcut set are currently pressed
            # This check is tricky because current_keys has specific _l/_r, while target_set has generic.
            # Let's refine the check:
            all_pressed = True
            temp_current = self._current_keys.copy()

            for target_key in self._target_shortcut_set:
                found = False
                # Find a matching key in currently pressed keys
                key_to_remove = None
                for pressed_key in temp_current:
                    match = False
                    if target_key == pressed_key:
                        match = True
                    elif target_key == keyboard.Key.ctrl and pressed_key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                        match = True
                    elif target_key == keyboard.Key.alt and pressed_key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
                        match = True
                    elif target_key == keyboard.Key.shift and pressed_key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                        match = True
                    elif target_key == keyboard.Key.cmd and pressed_key in (keyboard.Key.cmd_l, keyboard.Key.cmd_r, keyboard.Key.cmd): # Use cmd, cmd_l, cmd_r
                         match = True
                    elif isinstance(target_key, keyboard.KeyCode) and isinstance(pressed_key, keyboard.KeyCode):
                         # Compare chars, case-insensitively for letters
                         t_char = target_key.char.lower() if target_key.char else None
                         p_char = pressed_key.char.lower() if pressed_key.char else None
                         if t_char and t_char == p_char:
                              match = True

                    if match:
                        found = True
                        key_to_remove = pressed_key
                        break # Found a match for this target key

                if found and key_to_remove:
                     # Removed matched key to avoid double counting (e.g. if target is <Control>A and user presses Ctrl+A)
                     # temp_current.remove(key_to_remove) # This logic is flawed, don't remove. Just check presence.
                     pass # Keep iterating through target keys
                else:
                     all_pressed = False
                     break # A required key is missing

            # Check if the number of pressed keys is exactly the number required by the shortcut
            # This prevents triggering <Control>A when <Control><Shift>A is pressed.
            if len(self._current_keys) != len(self._target_shortcut_set):
                 all_pressed = False


            if all_pressed:
                print(f"Shortcut {self._target_shortcut_set} fully detected!") # Debug print
                # Trigger the action on the main GTK thread
                GLib.idle_add(self.app.activate_action, 'toggle_window', None)
                # Optional: If you want the shortcut to trigger only once per press sequence,
                # you might want to clear current_keys here or add a flag.
                # For toggle, triggering multiple times might be acceptable or even desired.

        # Stop condition (e.g., pressing Esc - optional)
        # if key == keyboard.Key.esc:
        #     self.stop()
        #     return False # Stop listener

    def _on_release(self, key):
        """Callback executed when a key is released."""
        try:
            self._current_keys.remove(key)
        except KeyError:
            # Key was not in the set, possibly released after starting the app
            # or wasn't part of our tracked keys. Ignore.
            pass

    def _run_listener(self):
        """Runs the keyboard listener loop."""
        # Create and run the listener within the thread
        # Use suppress=False if you want key events to pass through to other apps
        # Use suppress=True if you want to block the key combo from reaching other apps (might be desired)
        with keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=False # Let key presses through to other applications
            ) as self._listener:
            print("Shortcut listener started...")
            # Keep the listener running until stop() is called or an error occurs
            # The stop event allows us to signal the thread to exit gracefully.
            self._stop_event.wait() # Wait until the stop event is set
            print("Shortcut listener stopping...")
            # Listener automatically stops when 'with' block exits

    def start(self):
        """Starts the listener in a separate thread."""
        if self._listener_thread is None or not self._listener_thread.is_alive():
            self._stop_event.clear() # Ensure stop event is not set initially
            self._listener_thread = threading.Thread(target=self._run_listener, daemon=True)
            self._listener_thread.start()
        else:
            print("Listener thread already running.")

    def stop(self):
        """Signals the listener thread to stop."""
        print("Attempting to stop shortcut listener...")
        if self._listener:
            self._listener.stop() # Stop the pynput listener
        self._stop_event.set() # Signal the thread's wait loop to exit
        if self._listener_thread and self._listener_thread.is_alive():
             # Optional: Wait for the thread to finish
             # self._listener_thread.join(timeout=1.0)
             # If join times out, it means the thread didn't exit cleanly.
             # In a daemon thread, this might be okay as Python will exit anyway,
             # but non-daemon threads would require more robust handling.
             pass
        self._listener_thread = None
        self._listener = None
        self._current_keys.clear() # Clear keys on stop
        print("Shortcut listener stopped.")

# Example Usage (for testing purposes, not part of the final integration)
if __name__ == '__main__':
    # A dummy application class for testing
    class DummyApp:
        def activate_action(self, action_name, parameter):
            print(f"Action '{action_name}' activated with parameter '{parameter}'")
            # In real app, this would toggle the window

    dummy_app = DummyApp()
    listener = ShortcutListener(dummy_app)
    listener.start()

    # Keep the main thread alive to allow the listener thread to run
    # In a real GTK app, the Gtk.main() loop serves this purpose.
    try:
        # Wait indefinitely, or until an event like Ctrl+C
        threading.Event().wait()
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        listener.stop()