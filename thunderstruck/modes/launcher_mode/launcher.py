import gi
import os
import configparser
import logging

gi.require_version("Gtk", "4.0")
# Need GObject for ListStore items, SliceListModel
from gi.repository import Gtk, Gio, GObject, GLib, Gdk # Import GLib for idle_add if needed later, Gdk for keys

# Define the GSettings schema ID (used by LauncherWidget)
SCHEMA_ID = "org.example.Thunderstruck"

import subprocess
import shlex
import re

from thunderstruck.modes.base_mode import BaseMode

# Define the GObject wrapper class for our list items
class AppItem(GObject.Object):
    __gtype_name__ = "AppItem" # Good practice to define gtype name

    name = GObject.Property(type=str, default="")
    icon_name = GObject.Property(type=str, default=None) # Store icon name as string
    exec_cmd = GObject.Property(type=str, default="")

    def __init__(self, name, icon_name, exec_cmd):
        super().__init__()
        self.name = name
        self.icon_name = icon_name
        self.exec_cmd = exec_cmd

@Gtk.Template(resource_path="/org/example/Thunderstruck/ui/launcher.ui")
class LauncherWidget(Gtk.Box):
    __gtype_name__ = "LauncherWidget"

    search_entry: Gtk.SearchEntry = Gtk.Template.Child()

    results_list: Gtk.ListView = Gtk.Template.Child() 

    def __init__(self, mode_handler, **kwargs):
        super().__init__(**kwargs)
        self.mode_handler = mode_handler # LauncherMode instance
        self._search_text = "" # Initialize search text

        
        # Get GSettings
        self.settings = Gio.Settings.new(SCHEMA_ID)
        
        # Read initial max results and connect to changes
        self._max_results = self.settings.get_int("launcher-max-results")
        self.settings.connect("changed::launcher-max-results", self._on_max_results_changed)
        
        # Set up the list view using the model from the mode handler
        self._setup_results_list(self.mode_handler.list_store)
        # Connect search entry signal
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry.connect("activate", self._execute_selected_item) # Execute on Enter in search

        # Add keyboard navigation to the results list
        self.key_controller = Gtk.EventControllerKey()
        self.key_controller.connect("key-pressed", self._on_results_list_key_pressed)
        self.add_controller(self.key_controller) # Attach to the parent widget (self)

    def _setup_results_list(self, list_store: Gio.ListStore):
        """Sets up the model, filter, factory for the results ListView."""
        # Store the base list_store reference
        self.list_store = list_store

        # 1. Custom Filter
        self.custom_filter = Gtk.CustomFilter.new(self._filter_func, None)

        # 2. Filter Model (wraps the base store, uses the custom filter)
        self.filter_model = Gtk.FilterListModel(model=self.list_store, filter=self.custom_filter)

        
        # 3. Slice Model (wraps the filter model, applies the limit)
        self.slice_model = Gtk.SliceListModel(model=self.filter_model, offset=0, size=self._max_results)
        
        # 4. Selection Model (wraps the *slice* model)
        self.selection_model = Gtk.SingleSelection(model=self.slice_model)
        
        # 4. Factory
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_factory_setup)
        factory.connect("bind", self._on_factory_bind)

        # 6. Set Model and Factory on ListView
        # IMPORTANT: The ListView uses the SingleSelection model (which wraps the slice)
        self.results_list.set_model(self.selection_model)
        self.results_list.set_factory(factory)
        self.results_list.set_focusable(True) # Make the list view focusable

    def _on_factory_setup(self, factory, list_item):
        """Creates the widget (a Label) for each list item."""
        # Create a Box container for icon and label
        # Margins and spacing are now handled by CSS rule: listview listitem > box
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # Create an Image for the icon
        icon = Gtk.Image(icon_size=Gtk.IconSize.LARGE) # Use a standard size
        # Create a Label for the name
        label = Gtk.Label(xalign=0, hexpand=True) # Align left, expand horizontally

        box.append(icon)
        box.append(label)
        list_item.set_child(box)
        list_item.set_activatable(True)

    def _on_factory_bind(self, factory, list_item):
        """Binds the data (app name) to the widget (Label)."""
        box = list_item.get_child() # The Gtk.Box
        icon = box.get_first_child() # The Gtk.Image
        label = box.get_last_child() # The Gtk.Label
        item: AppItem = list_item.get_item() # Get the AppItem instance

        # Bind data
        label.set_label(item.name)
        # Set icon, handle cases where icon_name might be None or invalid
        if item.icon_name:
            # Use Gtk.IconTheme to check if the icon exists? Maybe overkill for now.
            # Let GTK handle missing icons by setting the name directly.
            # If it fails, it might show a fallback 'image-missing'.
            icon.set_from_icon_name(item.icon_name)
        else:
            icon.set_from_icon_name("application-x-executable") # Default fallback icon

    def _filter_func(self, item: AppItem, user_data):
        """Custom filter function. Returns True if item should be visible."""
        if not self._search_text:
            return True # Show all if search is empty
        # Case-insensitive search in the name
        return self._search_text.lower() in item.name.lower()

    def _on_search_changed(self, search_entry: Gtk.SearchEntry):
        """Handles the 'search-changed' signal from the search entry."""
        self._search_text = search_entry.get_text()
        logging.debug(f"Search text changed: '{self._search_text}'")
        # Notify the filter model that the filter needs to be re-evaluated
        # Re-assigning the filter seems to be the documented way,
        # though changed(DIFFERENT) might work in some GTK versions.
        self.filter_model.set_filter(None) # Temporarily remove filter
        self.filter_model.set_filter(self.custom_filter) # Re-apply the filter
        # Alternative: self.custom_filter.changed(Gtk.FilterChange.DIFFERENT) # Might be simpler if it works reliably

        # Select the first item after filtering if search text is not empty and *slice* is not empty
        if self._search_text and self.slice_model.get_n_items() > 0:
            self.selection_model.set_selected(0)
            # self.results_list.grab_focus() # REMOVED: Keep focus in search entry while typing
        elif not self._search_text: # Clear selection if search is cleared
             self.selection_model.set_selected(Gtk.INVALID_LIST_POSITION)


    def _on_results_list_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses on the results list for navigation and execution."""
        print(f"DEBUG: _on_results_list_key_pressed received keyval: {Gdk.keyval_name(keyval)}")
        # Check the slice model for emptiness and count
        list_empty = self.slice_model.get_n_items() == 0
        if list_empty:
            return False # Nothing to navigate or execute

        current_pos = self.selection_model.get_selected()
        last_pos = self.slice_model.get_n_items() - 1 # Use slice model count

        if keyval == Gdk.KEY_Up:
            if current_pos == Gtk.INVALID_LIST_POSITION: # No selection, select last
                new_pos = last_pos
            else:
                new_pos = max(0, current_pos - 1)
            self.selection_model.set_selected(new_pos)
            # Ensure the selected item is visible
            self.results_list.scroll_to(new_pos, Gtk.ListScrollFlags.NONE, None)
            return True # Key handled
        elif keyval == Gdk.KEY_Down:
            if current_pos == Gtk.INVALID_LIST_POSITION: # No selection, select first
                new_pos = 0
            else:
                new_pos = min(current_pos + 1, last_pos)
            self.selection_model.set_selected(new_pos)
            # Ensure the selected item is visible
            self.results_list.scroll_to(new_pos, Gtk.ListScrollFlags.NONE, None)
            return True # Key handled
        elif keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter:
            if current_pos != Gtk.INVALID_LIST_POSITION:
                 print("DEBUG: Enter key detected in list key handler.")
                 self._execute_selected_item()
                 return True # Key handled
            else: # If nothing selected but Enter pressed, execute first item if available in slice
                 if self.slice_model.get_n_items() > 0:
                     self.selection_model.set_selected(0)
                     self._execute_selected_item()
                     return True # Key handled

        return False # Key not handled here

    def _execute_selected_item(self, *args): # Accept *args for signal handlers like 'activate'
        """Executes the currently selected application, prioritizing explicit selection."""
        print("DEBUG: _execute_selected_item called.") # <<< ADDED LOGGING
        selected_pos = self.selection_model.get_selected()
        item_to_execute = None

        print(f"Executing: Initial selected_pos from selection_model = {selected_pos}")

        # If selection is invalid, try defaulting to the first item *if* the list isn't empty
        print(f"DEBUG: Checking if selected_pos ({selected_pos}) is invalid.") # <<< ADDED LOGGING
        if selected_pos == Gtk.INVALID_LIST_POSITION or selected_pos < 0:
            if self.slice_model.get_n_items() > 0:
                print("No valid selection, defaulting to index 0.")
                selected_pos = 0 # Default to first item's index
                # Explicitly update the selection model to reflect this default visually
                self.selection_model.set_selected(selected_pos)
                print(f"DEBUG: Defaulted selected_pos to {selected_pos}.") # <<< ADDED LOGGING
            else:
                print("No selection and list is empty, cannot execute.")
                return # Nothing to execute

        # Now, selected_pos should be a valid index (either original or defaulted 0)
        # Check if it's within the bounds of the slice model
        if 0 <= selected_pos < self.slice_model.get_n_items():
            item_to_execute = self.slice_model.get_item(selected_pos)
            print(f"Attempting to execute item at slice index {selected_pos}. Item: {getattr(item_to_execute, 'name', 'N/A')}")
        else:
            # This could happen if list changed rapidly, very unlikely here but good defense
            print(f"Error: Position {selected_pos} is out of bounds for slice model ({self.slice_model.get_n_items()} items). Cannot execute.")
            return

        # Final check if we have a valid item object
        if not isinstance(item_to_execute, AppItem):
            print(f"Error: Failed to get a valid AppItem object at slice position {selected_pos}.")
            return

        print(f"Proceeding to execute: {item_to_execute.name} (Exec: {item_to_execute.exec_cmd})")

        # --- Execution Logic ---
        exec_cmd = item_to_execute.exec_cmd
        print(f"DEBUG: Original exec_cmd: '{exec_cmd}'") # <<< ADDED LOGGING
        # Clean command (remove % codes) - simple approach
        cleaned_cmd = re.sub(r' %[a-zA-Z]', '', exec_cmd).strip()
        print(f"DEBUG: Cleaned command: '{cleaned_cmd}'") # <<< ADDED LOGGING
        # Basic command splitting (shlex might be better for complex cases)
        try:
            command_list = shlex.split(cleaned_cmd)
        except ValueError as e:
             print(f"Error splitting command '{cleaned_cmd}': {e}")
             # Optionally show an error to the user via a dialog
             return

        if not command_list:
            print("Error: No command left after cleaning.")
            return

        print(f"Executing command list: {command_list}")
        try:
            print(f"DEBUG: Attempting subprocess.Popen with: {command_list}") # <<< ADDED LOGGING
            # Use Popen for non-blocking execution
            subprocess.Popen(command_list, start_new_session=True) # start_new_session detaches from launcher
            # Hide the main window after successful launch attempt
            window = self.get_ancestor(Gtk.Window)
            if window:
                window.hide()
        except FileNotFoundError:
            print(f"Error: Command not found: {command_list[0]}")
            # Optionally show error dialog
        except Exception as e:
            print(f"Error executing command {command_list}: {e}")
            # Optionally show error dialog

    def _on_max_results_changed(self, settings, key):
        """Called when the 'launcher-max-results' GSetting changes."""
        self._max_results = settings.get_int(key)
        logging.info(f"Launcher max results setting changed to: {self._max_results}")
        # Update the slice model size
        if hasattr(self, 'slice_model') and self.slice_model:
            self.slice_model.set_size(self._max_results)
        else:
             logging.warning("Slice model not yet initialized when trying to update size.")


class LauncherMode(BaseMode):
    def __init__(self):
        super().__init__()
        # Create the ListStore here, owned by the mode
        self.list_store = Gio.ListStore.new(AppItem)
        self._index_desktop_files() # Populate with .desktop files first
        self._index_executables_with_rg() # Then add executables from PATH

    @property
    def name(self) -> str:
        return "Launcher"

    @property
    def icon_name(self) -> str:
        # Using 'system-run-symbolic' as suggested
        return "system-run-symbolic"

    def get_widget(self) -> Gtk.Widget:
        """Returns the main widget for this mode, passing self."""
        # Pass the mode instance (self) to the widget
        if not hasattr(self, '_widget_instance') or self._widget_instance is None:
             self._widget_instance = LauncherWidget(mode_handler=self)
        return self._widget_instance

    def activate(self):
        """Called when the mode becomes active."""
        print(f"{self.name} mode activated")
        # Ensure the search entry gets focus when the mode is activated
        widget = self.get_widget()
        if isinstance(widget, LauncherWidget):
            widget.search_entry.grab_focus() # Restore focus grabbing
        # else: # Removed as the corresponding 'if' block is commented out
        #      logging.warning("Could not get LauncherWidget instance to set focus.")
    def deactivate(self):
        """Called when the mode becomes inactive."""
        print(f"{self.name} mode deactivated")

    def handle_escape(self) -> bool:
        """
        Handles Escape key press for Launcher mode.
        Clears the search entry if it contains text.
        """
        widget = self.get_widget() # Get the LauncherWidget instance
        if isinstance(widget, LauncherWidget) and widget.search_entry:
            # Always clear the search entry and consume the event
            print("LauncherMode: Handling Escape, clearing search entry.")
            widget.search_entry.set_text("")
            # Clearing text will trigger _on_search_changed, which handles filter update
            return True # Escape always handled by LauncherMode (by clearing or doing nothing if already empty)
        # Return False only if widget/search_entry couldn't be accessed
        return False
    def _index_desktop_files(self):
        """Finds and parses .desktop files from standard locations."""
        logging.info("Starting desktop file indexing...")
        # Clear the store before indexing
        self.list_store.remove_all()
        desktop_entry_section = "Desktop Entry"
        standard_dirs = [
            "/usr/share/applications",
            "/usr/local/share/applications",
            os.path.expanduser("~/.local/share/applications"),
        ]

        # Use strict=False to be more lenient with file format variations
        # interpolation=None prevents errors with '%' chars often found in Exec lines
        parser = configparser.ConfigParser(interpolation=None, strict=False)

        for directory in standard_dirs:
            if not os.path.isdir(directory):
                logging.warning(f"Standard directory not found or not a directory: {directory}")
                continue # Skip if directory doesn't exist

            for root, _, files in os.walk(directory):
                for filename in files:
                    if filename.lower().endswith(".desktop"):
                        filepath = os.path.join(root, filename)
                        try:
                            # Clear previous file data and read the new one
                            parser.clear()
                            # Read with UTF-8 encoding, ignore errors for robustness
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                parser.read_file(f)


                            if parser.has_section(desktop_entry_section):
                                entry = parser[desktop_entry_section]

                                # Skip if NoDisplay or Hidden is true (case-insensitive check)
                                if entry.get("NoDisplay", "").lower() == 'true' or \
                                   entry.get("Hidden", "").lower() == 'true':
                                    continue
                                
                                # Skip if Type is not Application (if Type exists)
                                app_type = entry.get("Type", "Application") # Default to Application if Type is missing
                                if app_type != "Application":
                                    continue

                                name = entry.get("Name")
                                exec_cmd = entry.get("Exec")
                                icon = entry.get("Icon")
                                generic_name = entry.get("GenericName") # Also useful sometimes
                                comment = entry.get("Comment") # Also useful

                                # Only add if essential fields are present
                                if name and exec_cmd:
                                    # Create AppItem and append to the list_store
                                    app_item = AppItem(
                                        name=name,
                                        icon_name=icon, # Pass icon name string directly
                                        exec_cmd=exec_cmd
                                    )
                                    self.list_store.append(app_item)

                        except configparser.Error as e:
                            # Log specific parsing errors but continue
                            logging.warning(f"Config parsing error in {filepath}: {e}")
                        except Exception as e: # Catch other potential errors during file processing
                            logging.error(f"Unexpected error processing {filepath}: {e}")

        # Sorting is now implicitly handled by how items are added or could be done
        # on the ListStore if needed, but maybe not necessary for initial display.
        # If sorting is desired, Gtk.SortListModel could be introduced later.
        logging.info(f"Finished .desktop file indexing. Found {self.list_store.get_n_items()} applications from .desktop files.")

    def _index_executables_with_rg(self):
        """Finds executables in common PATH directories using ripgrep (rg)."""
        logging.info("Starting executable indexing with ripgrep...")
        # Keep track of added executables to avoid duplicates (using full path)
        added_executables = set()
        # Add executables found via .desktop files first to avoid overwriting them
        # if they also happen to be found by rg. We use the full path.
        current_items_count = self.list_store.get_n_items() # Count before adding rg results
        for i in range(current_items_count):
            item = self.list_store.get_item(i)
            if isinstance(item, AppItem) and item.exec_cmd:
                 # Basic check: if exec_cmd starts with an absolute path, add it
                 # This isn't perfect for complex Exec= lines, but covers simple cases.
                 cmd_parts = shlex.split(item.exec_cmd)
                 if cmd_parts and os.path.isabs(cmd_parts[0]):
                     added_executables.add(cmd_parts[0])
                 # Also add the name itself if it doesn't contain '/' to potentially
                 # catch commands run directly without path (e.g., 'firefox')
                 # This might add false positives if a .desktop name matches an exe name
                 # but it helps prevent adding 'firefox' again if found in /usr/bin
                 elif cmd_parts and '/' not in cmd_parts[0]:
                      added_executables.add(cmd_parts[0])


        # Define standard search paths for executables
        search_paths = [
            os.path.expanduser("~/bin"),
            os.path.expanduser("~/.local/bin"),
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
            "/snap/bin", # Common on Ubuntu systems
            "/var/lib/flatpak/exports/bin",
        ]

        generic_icon = "application-x-executable-symbolic" # Use a symbolic icon

        rg_found = False # Flag to check if rg was ever found

        for path_dir in search_paths:
            path_dir = os.path.normpath(path_dir) # Normalize path
            if not os.path.isdir(path_dir):
                logging.debug(f"Skipping non-existent or non-directory path: {path_dir}")
                continue

            rg_command = [
                "rg",
                "--files",        # List files instead of searching content
                "--no-ignore",    # Include ignored files (.gitignore, etc.)
                "--hidden",       # Include hidden files
                # "--follow",       # Follow symlinks (REMOVED due to potential filesystem loops)
                "--max-depth", "1", # Only search top-level in these dirs
                path_dir          # The directory to search
            ]

            try:
                logging.debug(f"Running ripgrep in: {path_dir}")
                result = subprocess.run(
                    rg_command,
                    capture_output=True,
                    text=True,
                    check=False, # Don't raise exception on non-zero exit
                    encoding='utf-8', # Explicitly set encoding
                    errors='ignore'   # Ignore potential decoding errors
                )
                rg_found = True # Mark rg as found if subprocess.run succeeds

                if result.returncode != 0 and result.stderr:
                     # Log rg errors, but continue (might be permission issues etc.)
                     logging.warning(f"ripgrep command may have failed in {path_dir} (exit code {result.returncode}): {result.stderr.strip()}")
                     # Don't 'continue' here, as rg might list some files even with errors

                if result.stdout:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        potential_exe_path = line.strip()
                        if not potential_exe_path:
                            continue

                        # Sanity check - ensure the path is within the searched directory
                        # Prevents issues if rg output includes parent dirs somehow
                        if not potential_exe_path.startswith(path_dir + os.sep):
                             continue


                        # 1. Check if it's executable and not a directory
                        try:
                            is_executable = os.access(potential_exe_path, os.X_OK) and not os.path.isdir(potential_exe_path)
                        except OSError as oe:
                            logging.debug(f"OSError checking access for {potential_exe_path}: {oe}")
                            continue # Skip if we can't access it

                        if is_executable:
                            # 2. Check if already added (using full path)
                            exe_name = os.path.basename(potential_exe_path)
                            if potential_exe_path not in added_executables and exe_name not in added_executables:
                                try:
                                    app_item = AppItem(
                                        name=exe_name,
                                        icon_name=generic_icon,
                                        exec_cmd=potential_exe_path # Use the full path as exec_cmd
                                    )
                                    self.list_store.append(app_item)
                                    added_executables.add(potential_exe_path)
                                    added_executables.add(exe_name) # Add name too for basic collision check
                                    logging.debug(f"Added executable: {exe_name} ({potential_exe_path})")
                                except Exception as e:
                                    logging.error(f"Error creating AppItem for {potential_exe_path}: {e}")


            except FileNotFoundError:
                # Only log the error once if rg is not found at all
                if not rg_found:
                    logging.error("ripgrep (rg) command not found. Please install ripgrep to find executables in PATH.")
                # Stop trying subsequent paths if rg isn't installed
                break
            except Exception as e:
                logging.error(f"Unexpected error running ripgrep or processing results in {path_dir}: {e}")

        final_count = self.list_store.get_n_items()
        added_count = final_count - current_items_count
        logging.info(f"Finished executable indexing. Added {added_count} executables via ripgrep.")


# Add other necessary methods like handle_input, etc., later