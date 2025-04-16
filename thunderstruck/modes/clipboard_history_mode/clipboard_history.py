import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GObject, Gdk, GLib # Import Gdk and GLib

from ..base_mode import BaseMode


@Gtk.Template(resource_path='/org/example/Thunderstruck/ui/clipboard_history.ui')
class ClipboardHistoryWidget(Gtk.Box):
    __gtype_name__ = 'ClipboardHistoryWidget'

    list_box = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._history_cache = [] # Cache for filtering
        self.search_entry.connect("search-changed", self._on_search_changed)

    def _update_history_list(self, history):
        """Clears and repopulates the list_box from the provided history."""
        print(f"[ClipboardHistoryWidget] Updating history list ({len(history)} items)")
        self._history_cache = history # Update cache

        # Clear existing items
        while child := self.list_box.get_first_child():
             self.list_box.remove(child)

        # Add items from history
        for item_text in history:
            escaped_text = GLib.markup_escape_text(item_text)
            row = Adw.ActionRow(title=escaped_text)
            row.set_activatable(True)
            icon = Gtk.Image.new_from_icon_name("text-x-generic-symbolic")
            row.add_prefix(icon)
            self.list_box.append(row)

        # Apply current filter after updating list
        self._apply_filter()


    def _on_search_changed(self, search_entry):
        """Handler for the search entry 'search-changed' signal."""
        self._apply_filter()

    def _apply_filter(self):
        """Applies the current search filter to the list_box items based on cached history."""
        search_term = self.search_entry.get_text().lower()
        print(f"[ClipboardHistoryWidget] Applying filter: '{search_term}'")

        # Filter based on the cached history text, not just visible rows
        filtered_history = [
            item for item in self._history_cache
            if search_term in item.lower()
        ]

        # Update visible rows based on filtered history
        current_row = self.list_box.get_first_child()
        visible_items_in_order = {item: i for i, item in enumerate(filtered_history)}
        row_index = 0

        while current_row:
            if isinstance(current_row, Adw.ActionRow):
                 row_text = current_row.get_title()
                 # Check if this row's text is in the filtered list
                 is_visible = row_text in visible_items_in_order
                 current_row.set_visible(is_visible)
            else:
                 # Handle potential separators etc.
                 current_row.set_visible(True)

            next_row = current_row.get_next_sibling()
            current_row = next_row


class ClipboardHistoryMode(BaseMode):
    __gtype_name__ = 'ClipboardHistoryMode'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._history = []
        self.widget = ClipboardHistoryWidget() # Instantiate the widget
        self._clipboard = Gdk.Display.get_default().get_clipboard()
        self._clipboard.connect("changed", self._on_clipboard_changed)
        self.widget._update_history_list(self._history) # Initial population

    @property
    def name(self):
        return "Clipboard History"

    @property
    def icon_name(self):
        # Using 'edit-copy-symbolic' as suggested
        return 'edit-copy-symbolic'

    def get_widget(self):
        """Returns the main UI widget for this mode."""
        return self.widget

    def _on_clipboard_changed(self, clipboard):
        """Handler for the clipboard 'changed' signal."""
        print(f"[{self.name}] Clipboard changed, reading text...")
        clipboard.read_text_async(None, self._on_clipboard_read_text_finish)

    def _on_clipboard_read_text_finish(self, clipboard, result):
        """Callback for async clipboard text read."""
        try:
            text = clipboard.read_text_finish(result)
            if text:
                print(f"[{self.name}] Read text: '{text[:50]}...'")
                # Avoid consecutive duplicates
                if not self._history or self._history[0] != text:
                    self._history.insert(0, text)
                    # Limit history size (e.g., 100 entries)
                    self._history = self._history[:100]
                    # Delegate UI update to the widget
                    self.widget._update_history_list(self._history)
            else:
                print(f"[{self.name}] No text found on clipboard.")
        except Exception as e:
            # Exceptions can happen if content isn't text or read fails
            print(f"[{self.name}] Error reading clipboard text: {e}")

    # UI update and filter methods are now in ClipboardHistoryWidget