import gi
import random # Added for random delays

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

# Import GLib for error handling and Adw.Animation for fade-out
from gi.repository import Gtk, Adw, Gio, GObject, GLib, Pango # Added Pango for label wrapping

@Gtk.Template(resource_path='/org/example/Thunderstruck/ui/welcome_screen.ui')
class WelcomeWindow(Adw.Window):
    __gtype_name__ = "WelcomeWindow"

    # Bind UI elements defined in the .blp file
    status_label = Gtk.Template.Child()
    splash_image = Gtk.Template.Child()

    # Bind UI elements defined in the .blp file
    status_label = Gtk.Template.Child() # Keep binding

    # Store the application instance to call methods on it later
    application = None

    # Animation state
    _status_messages = [
        "Instantiating subsystems",
        "Unfolding lemarchand-cube",
        "Establishing subspace connections",
        "Watering the pod of Mogwais",
        "Almost ready"
    ]
    _current_message_index = 0
    _current_dot_count = 0
    _animation_timeout_id = None

    def __init__(self, application, **kwargs):
        super().__init__(application=application, **kwargs)
        self.application = application # Store the application instance

        # Configure status label after it's initialized by Gtk.Template
        if self.status_label:
            self.status_label.set_wrap(True)
            self.status_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            self.status_label.set_justify(Gtk.Justification.CENTER)
        else:
            print("Warning: status_label not found during __init__.")

        # Start the animation sequence shortly after initialization
        GLib.idle_add(self._start_animation_sequence)

    def _start_animation_sequence(self):
        """Starts the initial animation timeout."""
        if self._animation_timeout_id:
            GLib.source_remove(self._animation_timeout_id)
        # Start immediately for the first message
        self._animate_status()
        return GLib.SOURCE_REMOVE # Run only once

    def _animate_status(self):
        """Updates the status label with message and dots, schedules next update."""
        if self._current_message_index >= len(self._status_messages):
            # Should not happen if logic is correct, but safety check
            self._start_fade_out()
            return GLib.SOURCE_REMOVE # Stop animation

        current_message = self._status_messages[self._current_message_index]
        dots = "." * self._current_dot_count
        # Add padding spaces to prevent horizontal shifting
        padding_spaces = ' ' * (3 - self._current_dot_count)
        display_text = f"{current_message}{dots}{padding_spaces}"
        self.status_label.set_label(display_text)
        print(f"Welcome Status: {display_text}") # Debug (includes padding)

        self._current_dot_count += 1

        if self._current_dot_count > 3:
            self._current_dot_count = 0
            self._current_message_index += 1

            if self._current_message_index >= len(self._status_messages):
                # Last message finished, start fade out
                self._start_fade_out()
                return GLib.SOURCE_REMOVE # Stop animation loop
            else:
                 # Immediately show the next message without dots before the next delay
                next_message = self._status_messages[self._current_message_index]
                # Show next message with full padding initially
                self.status_label.set_label(f"{next_message}{' ' * 3}")


        # Schedule the next update
        delay_ms = random.randint(300, 800) # Random delay between 0.5s and 0.8s
        self._animation_timeout_id = GLib.timeout_add(delay_ms, self._animate_status)

        # Return False because timeout_add handles rescheduling
        return False # Important: Use False when timeout_add is used inside the callback

    def _start_fade_out(self):
        """Initiates the fade-out animation."""
        print("Starting fade-out animation...")
        # 1. Create the target
        target = Adw.PropertyAnimationTarget.new(self, "opacity")
        # 2. Create the animation with widget, duration, target
        #    Create the animation with positional arguments:
        #    widget, value_from, value_to, duration, target
        animation = Adw.TimedAnimation.new(
            self,      # widget
            1.0,       # value_from
            0.0,       # value_to
            500,       # duration (ms)
            target     # target
        )
        # No need to set_value_to() as it's done in the constructor now
        # No need to manually set opacity to 1.0, animation starts from value_from
        animation.connect("done", self._on_fade_out_done)
        animation.play()

    def _on_fade_out_done(self, animation):
        """Called when the fade-out animation completes."""
        print("Fade-out complete. Closing Welcome, Showing Main.")
        if self.application:
            self.application.show_main_window()
        self.close()
# --- Output Capture ---

# Inherit from GObject.Object to support signals
class OutputRedirector(GObject.Object):
    """A file-like object to capture stdout/stderr and emit a signal."""
    __gsignals__ = {
        'message-captured': (GObject.SignalFlags.RUN_LAST, None, (str,))
    }

    def __init__(self):
        """Initializes the redirector."""
        # Initialize the GObject base class
        GObject.Object.__init__(self)
        # No longer need original_stdout or callback here

    def write(self, text):
        """Captures the text and emits the 'message-captured' signal."""
        message = text.strip()
        if message: # Avoid emitting signals for empty lines
            # print(f"DEBUG Redirector emitting: {message}") # Uncomment for intense debugging
            self.emit("message-captured", message)

    def flush(self):
        """Flush method, required for file-like objects. Flushes the original stream."""
        # Flush is still required for file-like objects, but does nothing here now.
        pass