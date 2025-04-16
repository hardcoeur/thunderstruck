import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
import subprocess
from gi.repository import Gtk, Adw, Gio, GObject, GLib # Added GLib
# from pathlib import Path # No longer needed for UI file path
import logging # Use logging for better error reporting

from ..base_mode import BaseMode

# Configure logging
logger = logging.getLogger(__name__)


# Define the widget using Gtk.Template
@Gtk.Template(resource_path='/org/example/Thunderstruck/ui/window_management.ui')
class WindowManagementWidget(Gtk.Box):
    __gtype_name__ = 'WindowManagementWidget'

    list_box = Gtk.Template.Child("action_list_box")
    search_entry = Gtk.Template.Child("search_entry")

    def __init__(self, mode_handler, **kwargs):
        super().__init__(**kwargs)
        self._mode_handler = mode_handler # Reference back to the mode logic

        if not self.list_box:
            logger.warning("action_list_box not found in blueprint template.")
        if not self.search_entry:
            logger.warning("search_entry not found in blueprint template.")

        # Populate and connect signals
        if self.list_box:
            self._populate_actions(self.list_box)
            self.list_box.connect("row-activated", self._on_row_activated)

        if self.search_entry:
            self.search_entry.connect("search-changed", self._on_search_changed)

    def _populate_actions(self, list_box: Gtk.ListBox):
        """Populates the list box with defined actions and their identifiers."""
        # Define actions with a user-friendly name and a command identifier
        actions = {
            "Maximize": "maximize",
            "Unmaximize": "unmaximize",
            # Add more simple actions here if needed
            # "Left Half": "left_half", # Example for future extension
            # "Right Half": "right_half", # Example for future extension
        }
        # Clear existing rows if any (e.g., if called multiple times)
        child = list_box.get_first_child()
        while child:
            list_box.remove(child)
            child = list_box.get_first_child()


        for name, identifier in actions.items():
            # Margins are now handled by CSS rule: listbox row.action-row label
            label = Gtk.Label(label=name, xalign=0)
            row = Gtk.ListBoxRow()
            row.set_child(label)
            row.set_name(identifier) # Store the command identifier
            # Add CSS class for potential styling
            row.add_css_class("action-row")
            list_box.append(row)

    def _on_search_changed(self, search_entry: Gtk.SearchEntry):
        """Handles the search-changed signal from the search entry."""
        search_text = search_entry.get_text().strip().lower()
        self._filter_list(search_text)

    def _filter_list(self, search_text: str):
        """Filters the list box rows based on the search text."""
        if not self.list_box:
            return

        row = self.list_box.get_first_child()
        while row:
            if isinstance(row, Gtk.ListBoxRow):
                label = row.get_child()
                if isinstance(label, Gtk.Label):
                    row_text = label.get_label().lower()
                    row.set_visible(search_text in row_text)
            # Get next sibling
            row = row.get_next_sibling()

    def _on_row_activated(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow):
        """Handles the row-activated signal from the list box."""
        action_id = row.get_name()
        logger.info(f"Action activated: {action_id}")
        self._mode_handler.execute_action(action_id) # Delegate execution to mode handler

    def reset_and_focus(self):
        """Resets search and focuses the entry."""
        if self.search_entry:
            self.search_entry.set_text("") # Clear search on activation
            self.search_entry.grab_focus()
        self._filter_list("") # Reset filter

class WindowManagementMode(BaseMode):
    """
    Mode for managing and manipulating application windows.
    Delegates UI to WindowManagementWidget.
    """
    def __init__(self, **kwargs):
        # Initialize the parent GObject, accepting potential kwargs
        super().__init__(**kwargs)
        self._widget: WindowManagementWidget | None = None
        # Removed builder, _list_box, _search_entry references from mode

    @property
    def name(self) -> str:
        """The user-visible name of the mode."""
        return "Window Management"

    @property
    def icon_name(self) -> str:
        """The icon name for the mode."""
        # Using 'view-grid-symbolic' as it seems appropriate for window arrangement
        return 'view-grid-symbolic'

    def get_widget(self) -> Gtk.Widget:
        """Returns the main widget for this mode."""
        if self._widget is None:
            try:
                # Instantiate the template-based widget, passing self as the handler
                self._widget = WindowManagementWidget(mode_handler=self)
            except Exception as e:
                 logger.error(f"Error instantiating WindowManagementWidget: {e}", exc_info=True)
                 # Fallback widget in case of error
                 self._widget = Gtk.Label(label=f"Error loading UI for {self.name}")
        return self._widget

    # _populate_actions moved to WindowManagementWidget

    def activate(self):
        """Called when the mode becomes active."""
        logger.info(f"{self.name} mode activated")
        widget = self.get_widget() # Ensure widget is created
        if isinstance(widget, WindowManagementWidget):
            widget.reset_and_focus()
        else:
            logger.warning("Cannot activate: Widget is not a WindowManagementWidget instance.")


    def deactivate(self):
        """Called when the mode becomes inactive."""
        logger.info(f"{self.name} mode deactivated")
        # Optional: Clear search text when deactivating? Handled by activate's reset.
        pass

    # _on_search_changed moved to WindowManagementWidget
    # _filter_list moved to WindowManagementWidget


    # _on_row_activated moved to WindowManagementWidget

    def execute_action(self, action_id: str):
        """Executes the window management command associated with the action ID."""

        command = None
        if action_id == "maximize":
            command = ["wmctrl", "-r", ":ACTIVE:", "-b", "add,maximized_vert,maximized_horz"]
        elif action_id == "unmaximize":
            command = ["wmctrl", "-r", ":ACTIVE:", "-b", "remove,maximized_vert,maximized_horz"]
        # Add other command constructions here based on action_id

        if command:
            try:
                # Run in the background, don't wait, don't capture output unless needed for debugging
                logger.info(f"Executing command: {' '.join(command)}")
                subprocess.Popen(command)

                # Hide the main application window after executing
                app_window = self.get_widget().get_ancestor(Gtk.Window)
                if app_window:
                    # Use idle_add to ensure hide happens after current event processing
                    # Although Popen is non-blocking, hiding immediately might feel abrupt
                    GLib.idle_add(app_window.hide) # Requires GLib import

            except FileNotFoundError:
                logger.error(f"Error: 'wmctrl' command not found. Please install it.")
                # Optionally show a user-facing dialog here
                dialog = Adw.MessageDialog.new(self.get_widget().get_ancestor(Gtk.Window),
                                               "Error: wmctrl not found",
                                               "The 'wmctrl' command is required for window management but was not found. Please install it (e.g., 'sudo apt install wmctrl').")
                dialog.add_response("ok", "OK")
                dialog.connect("response", lambda d, r: d.close())
                dialog.present()
            except Exception as e:
                logger.error(f"Error executing wmctrl command: {e}", exc_info=True)
                # Optionally show a user-facing dialog for other errors
        else:
            logger.warning(f"No command defined for action: {action_id}")