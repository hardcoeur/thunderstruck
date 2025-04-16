import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GObject, GLib, Gio

import os
import threading
import requests # Dependency: Add 'requests' to requirements.txt
try:
    # Dependency: Add 'google-cloud-aiplatform' to requirements.txt
    import vertexai
    from vertexai.generative_models import GenerativeModel # Or specific model class
    from google.api_core import exceptions as google_exceptions
    # ADC is preferred, but attempting to use API key if provided
    # from google.oauth2 import service_account # For service account keys
    # from google.auth.transport.requests import Request # For explicit key usage (complex)
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    print("Vertex AI SDK not found. Install google-cloud-aiplatform.")

from thunderstruck.modes.base_mode import BaseMode
# Import APP_ID from the main script where it's defined
# Use try-except for potential circular import issues during initialization,
# though it should be fine here. A better approach might be a dedicated config module.
try:
    from thunderstruck.main import APP_ID
except ImportError:
    # Fallback or raise error if absolute import fails
    print("Warning: Could not import APP_ID from thunderstruck.main. Using default.")
    # Make sure this matches the actual ID used in main.py and gschema.xml
    APP_ID = "org.example.Thunderstruck"


# Define placeholder constants (replace with actual values or config)
openrouter_API_URL = "https://openrouter.ai/api/v1/chat/completions" # Example URL
openrouter_MODEL = "mistralai/mistral-7b-instruct:free" # Example model
VERTEX_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") # Or get from config/settings
VERTEX_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1") # Or get from config/settings
VERTEX_MODEL_NAME = "gemini-1.5-flash-001" # Example model


# Helper function to create a message label
def create_message_label(text: str, is_user: bool, is_error: bool = False) -> Gtk.Box:
    # Use a Box to hold the label and allow for potential icons later
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    label = Gtk.Label(label=text, wrap=True, xalign=0.0, selectable=True) # Align left within box
    label.add_css_class("message")

    # Add classes to the BOX for alignment styling
    if is_error:
        label.add_css_class("error-message")
        box.add_css_class("error-message-container") # Add container class
        box.set_halign(Gtk.Align.END) # Align right
    elif is_user:
        label.add_css_class("user-message")
        box.add_css_class("user-message-container") # Add container class
        box.set_halign(Gtk.Align.START) # Align left
    else:
        label.add_css_class("ai-message")
        box.add_css_class("ai-message-container") # Add container class
        box.set_halign(Gtk.Align.END) # Align right

    box.append(label)
    return box


# Define the path to the blueprint file relative to this script

@Gtk.Template(resource_path='/org/example/Thunderstruck/ui/ai_chat.ui')
class AiChatWidget(Gtk.Box):
    __gtype_name__ = 'AiChatWidget'

    chat_box: Gtk.Box = Gtk.Template.Child()
    message_entry: Adw.EntryRow = Gtk.Template.Child()
    spinner: Gtk.Spinner = Gtk.Template.Child() # Assumes spinner is added to ai_chat.blp

    def __init__(self, mode_handler):
        super().__init__()
        self.mode_handler: AiChatMode = mode_handler # Reference to AiChatMode instance
        self.message_entry.connect("apply", self._on_message_send)

    def _on_message_send(self, entry: Adw.EntryRow):
        prompt = entry.get_text().strip()
        if prompt:
            entry.set_text("")
            self.add_message(prompt, is_user=True)
            self.show_loading(True)
            # Decide which API to call (e.g., based on config or a dropdown later)
            # For now, let's default to Vertex AI if available, else openrouter
            if VERTEX_AI_AVAILABLE and self.mode_handler._vertex_api_key:
                 print("Sending to Vertex AI...")
                 self.mode_handler.send_prompt(prompt, api_target='vertex')
            elif self.mode_handler._openrouter_api_key:
                 print("Sending to openrouter...")
                 self.mode_handler.send_prompt(prompt, api_target='openrouter')
            else:
                 print("No API key configured.")
                 self.show_loading(False)
                 self.add_message("No AI provider API key configured in Preferences.", is_user=False, is_error=True)

    def add_message(self, text: str, is_user: bool, is_error: bool = False):
        message_widget = create_message_label(text, is_user, is_error)
        self.chat_box.append(message_widget)
        # Try to scroll down (best effort)
        # Getting the scrolled window requires knowing the parent structure.
        # If this widget is directly inside a ScrolledWindow:
        parent = self.get_parent()
        if isinstance(parent, Gtk.ScrolledWindow):
             adj = parent.get_vadjustment()
             if adj:
                 # Wait for GTK layout cycle before scrolling
                 GLib.idle_add(lambda: adj.set_value(adj.get_upper()))

    def show_loading(self, show: bool):
        if self.spinner: # Check if spinner exists
            self.spinner.set_visible(show)
            if show:
                self.spinner.start()
            else:
                self.spinner.stop()
        self.message_entry.set_sensitive(not show) # Disable entry while loading


class AiChatMode(BaseMode):
    __gtype_name__ = 'AiChatMode'

    # GSettings keys
    SETTINGS_SCHEMA = APP_ID # Use the main app ID
    VERTEX_API_KEY_SETTING = "vertex-ai-api-key"
    openrouter_API_KEY_SETTING = "openrouter-api-key"

    def __init__(self):
        super().__init__()
        self._widget: AiChatWidget | None = None
        self._settings: Gio.Settings | None = None
        self._vertex_api_key: str | None = None
        self._openrouter_api_key: str | None = None

        try:
            self._settings = Gio.Settings.new(self.SETTINGS_SCHEMA)
            self._load_api_keys()
            # Connect to changes (optional but good practice)
            self._settings.connect(f"changed::{self.VERTEX_API_KEY_SETTING}", self._on_setting_changed)
            self._settings.connect(f"changed::{self.openrouter_API_KEY_SETTING}", self._on_setting_changed)
        except GLib.Error as e:
            print(f"Error loading GSettings schema '{self.SETTINGS_SCHEMA}': {e}")
            self._settings = None # Ensure it's None if schema fails

    def _load_api_keys(self):
        if self._settings:
            self._vertex_api_key = self._settings.get_string(self.VERTEX_API_KEY_SETTING)
            self._openrouter_api_key = self._settings.get_string(self.openrouter_API_KEY_SETTING)
            print(f"Vertex Key Loaded: {'Yes' if self._vertex_api_key else 'No'}")
            print(f"openrouter Key Loaded: {'Yes' if self._openrouter_api_key else 'No'}")
        else:
            self._vertex_api_key = None
            self._openrouter_api_key = None

    def _on_setting_changed(self, settings, key):
        print(f"Setting changed: {key}")
        self._load_api_keys()
        # Potentially notify the user or re-validate state if needed

    @property
    def name(self) -> str:
        return "AI Chat"

    @property
    def icon_name(self) -> str:
        # Using 'chat-symbolic' as a placeholder icon
        return 'chat-symbolic' # Or 'dialog-question-symbolic'

    def get_widget(self) -> Gtk.Widget:
        if self._widget is None:
            # Build the UI from the template, passing self (AiChatMode instance)
            self._widget = AiChatWidget(mode_handler=self)
        return self._widget

    # --- API Call Handling ---
    def send_prompt(self, prompt: str, api_target: str):
        """Starts the API call in a separate thread."""
        thread = threading.Thread(target=self._api_worker, args=(prompt, api_target), daemon=True)
        thread.start()

    def _api_worker(self, prompt: str, api_target: str):
        """Worker function executed in a separate thread."""
        api_key = None
        response_text = None
        error_message = None

        try:
            if api_target == 'vertex':
                api_key = self._vertex_api_key
                if not api_key:
                    error_message = "Error: Vertex AI API key not configured."
                elif not VERTEX_AI_AVAILABLE:
                     error_message = "Error: google-cloud-aiplatform library not installed."
                elif not VERTEX_PROJECT_ID:
                     error_message = "Error: GOOGLE_CLOUD_PROJECT environment variable not set."
                else:
                    # --- Vertex AI Call ---
                    print(f"Calling Vertex AI (Project: {VERTEX_PROJECT_ID}, Location: {VERTEX_LOCATION})")
                    # Note: Using API key directly with client library is non-standard.
                    # ADC (gcloud auth application-default login) is preferred.
                    # This implementation attempts it but might require adjustments
                    # depending on how Vertex AI auth handles keys for this specific API.
                    # Consider setting GOOGLE_API_KEY env var if client supports it,
                    # or using specific credentials object if init allows.
                    try:
                        # os.environ['GOOGLE_API_KEY'] = api_key # Might work for some APIs? Unreliable.
                        # Initialize client (might implicitly use ADC or GOOGLE_API_KEY if set)
                        vertexai.init(project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)
                        model = GenerativeModel(VERTEX_MODEL_NAME)
                        response = model.generate_content(prompt)
                        response_text = response.text
                        print("Vertex AI call successful.")
                    except google_exceptions.PermissionDenied as e:
                        print(f"Vertex AI Permission Denied: {e}")
                        error_message = "Error: Vertex AI permission denied. Check API key or ADC setup."
                    except Exception as e:
                        print(f"Vertex AI Error: {e}")
                        error_message = f"Error calling Vertex AI: {e}"

            elif api_target == 'openrouter':
                api_key = self._openrouter_api_key
                if not api_key:
                    error_message = "Error: openrouter API key not configured."
                else:
                    # --- openrouter Call ---
                    print(f"Calling openrouter API (Model: {openrouter_MODEL})")
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    # Basic payload structure - adjust based on actual API spec
                    payload = {
                        "model": openrouter_MODEL,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                    try:
                        response = requests.post(openrouter_API_URL, headers=headers, json=payload, timeout=30)
                        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                        # Extract response - adjust based on actual API spec
                        # Assuming OpenAI-like structure
                        data = response.json()
                        if data.get("choices") and len(data["choices"]) > 0:
                            message = data["choices"][0].get("message")
                            if message and message.get("content"):
                                response_text = message["content"].strip()
                                print("openrouter call successful.")
                            else:
                                error_message = "Error: Unexpected response format from openrouter."
                        else:
                            error_message = "Error: No response choices found from openrouter."
                    except requests.exceptions.HTTPError as e:
                         print(f"openrouter HTTP Error: {e.response.status_code} - {e.response.text}")
                         if e.response.status_code == 401:
                             error_message = "Error: Invalid openrouter API key."
                         elif e.response.status_code == 429:
                              error_message = "Error: openrouter rate limit exceeded."
                         else:
                             error_message = f"Error: openrouter API returned status {e.response.status_code}."
                    except requests.exceptions.RequestException as e:
                        print(f"openrouter Network Error: {e}")
                        error_message = f"Error: Network error connecting to openrouter: {e}"
                    except Exception as e:
                        print(f"openrouter General Error: {e}")
                        error_message = f"Error processing openrouter request: {e}"

            else:
                error_message = f"Error: Unknown API target '{api_target}'"

        finally:
            # Schedule UI update on the main thread
            if error_message:
                GLib.idle_add(self._handle_api_response, error_message, True)
            elif response_text:
                GLib.idle_add(self._handle_api_response, response_text, False)
            else:
                # Should not happen unless logic error above, but handle defensively
                GLib.idle_add(self._handle_api_response, "Error: Unknown API failure.", True)


    def _handle_api_response(self, text: str, is_error: bool):
        """Handles the API response on the main GTK thread."""
        print(f"API response received (is_error={is_error}): {text[:100]}...") # Log truncated response
        if self._widget:
            self._widget.show_loading(False)
            self._widget.add_message(text, is_user=False, is_error=is_error)
        return GLib.SOURCE_REMOVE # Ensure idle_add runs only once