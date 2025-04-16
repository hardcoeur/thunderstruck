# SPDX-FileCopyrightText: 2024-present The Thunderstruck Authors
#
# SPDX-License-Identifier: MIT

import logging
import os
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib, GObject, Gtk, GdkPixbuf # Added Gtk and GdkPixbuf

# Dummy _ function for gettext if not available globally
try:
    _
except NameError:
    _ = lambda s: s

logger = logging.getLogger(__name__)

# Basic StatusNotifierItem interface structure (will be expanded)
# Reference: https://freedesktop.org/wiki/Specifications/StatusNotifierItem/
STATUS_NOTIFIER_ITEM_INTERFACE_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Id" type="s" access="read"/>
    <property name="Category" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="ToolTip" type="s" access="read"/> <!-- Simplified: spec uses (ss) -->
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/> <!-- Object path for the menu -->

    <method name="ContextMenu">
      <arg direction="in" name="x" type="i"/>
      <arg direction="in" name="y" type="i"/>
    </method>
    <method name="Activate">
      <arg direction="in" name="x" type="i"/>
      <arg direction="in" name="y" type="i"/>
    </method>

    <signal name="NewIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus">
        <arg name="status" type="s"/>
    </signal>
  </interface>
</node>
"""

# D-Bus Menu interface (Restored)
DBUS_MENU_INTERFACE_XML = """
<node>
   <interface name="com.canonical.dbusmenu">
       <!-- Basic properties and methods needed -->
       <property name="Version" type="u" access="read"/>
       <property name="TextDirection" type="s" access="read"/>
       <property name="Status" type="s" access="read"/>
       <property name="IconThemePath" type="as" access="read"/>

       <method name="GetLayout">
           <arg type="i" name="parentId" direction="in"/>
           <arg type="i" name="recursionDepth" direction="in"/>
           <arg type="as" name="propertyNames" direction="in"/>
           <arg type="u" name="revision" direction="out"/>
           <arg type="(ia{sv}av)" name="layout" direction="out"/> <!-- Complex layout structure -->
       </method>
       <method name="GetGroupProperties">
            <arg type="ai" name="ids" direction="in"/>
            <arg type="as" name="propertyNames" direction="in"/>
            <arg type="a(ia{sv})" name="properties" direction="out"/>
       </method>
       <method name="GetProperty">
           <arg type="i" name="id" direction="in"/>
           <arg type="s" name="name" direction="in"/>
           <arg type="v" name="value" direction="out"/>
       </method>
       <method name="Event">
           <arg type="i" name="id" direction="in"/>
           <arg type="s" name="eventId" direction="in"/>
           <arg type="v" name="data" direction="in"/>
           <arg type="u" name="timestamp" direction="in"/>
       </method>
       <method name="EventGroup">
           <arg type="a(isv)" name="events" direction="in"/> <!-- Array of (id, eventId, data) -->
           <arg type="ai" name="idErrors" direction="out"/>
       </method>
       <method name="AboutToShow">
           <arg type="i" name="id" direction="in"/>
           <arg type="b" name="needUpdate" direction="out"/>
       </method>
       <method name="AboutToShowGroup">
            <arg type="ai" name="ids" direction="in"/>
            <arg type="ai" name="updatesNeeded" direction="out"/>
            <arg type="ai" name="idErrors" direction="out"/>
       </method>

       <signal name="ItemsPropertiesUpdated">
           <arg type="a(ia{sv})" name="updatedProps"/>
           <arg type="a(ias)" name="removedProps"/>
       </signal>
       <signal name="LayoutUpdated">
           <arg type="u" name="revision"/>
           <arg type="i" name="parentId"/>
       </signal>
       <signal name="ItemActivationRequested">
           <arg type="i" name="id"/>
           <arg type="u" name="timestamp"/>
       </signal>
   </interface>
</node>
"""

class GnomeStatusIcon(GObject.Object):
    """
    Manages a status icon in the GNOME Shell using the StatusNotifierItem D-Bus spec.
    """
    __gtype_name__ = 'GnomeStatusIcon'

    # --- StatusNotifierItem Properties ---
    @GObject.Property(type=str, default="Thunderstruck")
    def id(self):
        return "Thunderstruck" # Application ID

    @GObject.Property(type=str, default="ApplicationStatus")
    def category(self):
        return "ApplicationStatus" # "SystemServices", "ApplicationStatus"

    @GObject.Property(type=str, default="Active", flags=GObject.ParamFlags.READWRITE)
    def status(self):
        # "Active", "Passive", "NeedsAttention"
        return self._status

    @status.setter
    def status(self, value):
        if self._status != value:
            self._status = value
            self.notify("status")
            self._emit_signal("NewStatus", GLib.Variant("(s)", (value,)))


    @GObject.Property(type=str, default="system-run-symbolic", flags=GObject.ParamFlags.READWRITE) # Changed default
    def icon_name(self):
        return self._icon_name

    @icon_name.setter
    def icon_name(self, value):
        if self._icon_name != value:
            self._icon_name = value
            self.notify("icon-name")
            self._emit_signal("NewIcon")

    # ToolTip property requires custom handling due to its complex type (a(ss))
    # We won't use GObject.Property directly for it, but handle it in _handle_get_property
    # @GObject.Property(type=str, default="Thunderstruck Launcher") # Placeholder Tooltip text
    def get_tool_tip_variant(self):
         # Spec requires array of structs of (string, string): a(ss)
         # Structure: [(icon_name, icon_data), (title, text)]
         # We provide an empty icon_data and use the icon_name property.
         icon_name = self.icon_name
         title = "Thunderstruck"
         text = "Thunderstruck Launcher" # Simple text for now
         # Build the variant: a(ss)
         tooltip_data = [
             GLib.Variant('(ss)', (icon_name, '')), # Icon Name, Icon Data (empty)
             GLib.Variant('(ss)', (title, text))      # Title, Text
         ]
         return GLib.Variant('a(ss)', tooltip_data)

    @GObject.Property(type=bool, default=True)
    def item_is_menu(self):
        return True # We provide a D-Bus menu

    @GObject.Property(type=str) # Object path
    def menu(self):
        # This property now returns the path where Gio.Menu is exported
        return self._dbus_menu_object_path # Point back to the dbusmenu object path

    # --- Dbusmenu Properties (Restored, Simplified) ---
    @GObject.Property(type=int, default=3) # Version 3 is common
    def version(self):
        return 3

    @GObject.Property(type=str, default="ltr") # or "rtl"
    def text_direction(self):
        return "ltr"

    @GObject.Property(type=str, default="normal") # or "notice"
    def dbusmenu_status(self):
        return "normal"

    @GObject.Property(type=GObject.TYPE_STRV, default=[]) # Icon search paths
    def icon_theme_path(self):
        return []


    def __init__(self, application: Gtk.Application):
        super().__init__()
        logger.debug("GnomeStatusIcon.__init__ starting.")
        self._application = application
        self._bus: Gio.DBusConnection | None = None
        self._registration_id: int = 0
        self._menu_registration_id: int = 0 # Restored for dbusmenu object
        self._bus_name_id: int = 0
        self._status: str = "Active" # "Active", "Passive", "NeedsAttention"
        self._icon_name: str = "application-x-executable" # Use app icon
        # self._gio_menu: Gio.Menu | None = None # Removed
        # self._menu_object_path: str | None = None # Removed
        # self._menu_export_id: int = 0 # Removed

        self._object_path: str = "/StatusNotifierItem"
        # Use the conventional Ayatana path for the dbusmenu object
        self._dbus_menu_object_path = "/org/ayatana/NotificationItem/Thunderstruck/Menu"

        # Parse both interface XMLs (Restored)
        try:
            self._node_info = Gio.DBusNodeInfo.new_for_xml(STATUS_NOTIFIER_ITEM_INTERFACE_XML)
            self._menu_node_info = Gio.DBusNodeInfo.new_for_xml(DBUS_MENU_INTERFACE_XML)
        except GLib.Error as e:
            logger.error(f"Failed to parse D-Bus interface XML: {e}")
            self._node_info = None
            self._menu_node_info = None
            return # Cannot proceed without interface info

        self._interface_info = self._node_info.lookup_interface("org.kde.StatusNotifierItem")
        self._dbusmenu_interface_info = self._menu_node_info.lookup_interface("com.canonical.dbusmenu")

        if not self._interface_info or not self._dbusmenu_interface_info:
             logger.error("Could not find interfaces in parsed XML.")
             return

        # Unique bus name for the StatusNotifierItem
        # Format: org.kde.StatusNotifierItem-<PID>-<instance>
        self._bus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"

        # Get Session Bus
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            logger.info("Successfully connected to D-Bus session bus.")
            logger.debug("D-Bus connection retrieved.")

            # Register StatusNotifierItem object (Restored original order)
            self._registration_id = self._bus.register_object(
                object_path=self._object_path,
                interface_info=self._interface_info,
                method_call_closure=self._handle_method_call,
                get_property_closure=self._handle_get_property,
                set_property_closure=None # Properties are read-only for now
            )
            if self._registration_id > 0:
                logger.info(f"Successfully registered StatusNotifierItem object at {self._object_path}")
                logger.debug(f"StatusNotifierItem registration ID: {self._registration_id}")
            else:
                logger.error("Failed to register StatusNotifierItem object.")
                return # Cannot proceed

            # Register Dbusmenu object (Restored)
            self._menu_registration_id = self._bus.register_object(
                object_path=self._dbus_menu_object_path, # Use the correct path
                interface_info=self._dbusmenu_interface_info,
                method_call_closure=self._handle_menu_method_call, # Use menu handler
                get_property_closure=self._handle_get_property, # Reuse getter logic for GObject props
                set_property_closure=None
            )
            if self._menu_registration_id > 0:
                logger.info(f"Successfully registered Dbusmenu object at {self._dbus_menu_object_path}")
                logger.debug(f"Dbusmenu registration ID: {self._menu_registration_id}")
            else:
                logger.error("Failed to register Dbusmenu object.")
                # Clean up SNI registration if menu fails
                if self._registration_id > 0:
                    self._bus.unregister_object(self._registration_id)
                return

            # Acquire the unique bus name and store the owner ID for cleanup
            self._bus_name_id = Gio.bus_own_name(
                bus_type=Gio.BusType.SESSION,
                name=self._bus_name,
                flags=Gio.BusNameOwnerFlags.NONE,
                bus_acquired_closure=self._on_bus_acquired, # Called when connection is ready
                name_acquired_closure=self._on_name_acquired, # Called when name is acquired
                name_lost_closure=self._on_name_lost # Called when name is lost
            )
            logger.info(f"Requested D-Bus name '{self._bus_name}'. Owner ID: {self._bus_name_id}")
            logger.debug(f"Initiated request for bus name '{self._bus_name}'.")

        except GLib.Error as e:
            logger.error(f"Failed to connect to D-Bus session bus or register object: {e}")
            self._bus = None
            # Ensure cleanup if partial registration occurred
            if self._registration_id > 0 and self._bus:
                 self._bus.unregister_object(self._registration_id)
            # Restored menu registration ID cleanup
            if self._menu_registration_id > 0 and self._bus:
                 self._bus.unregister_object(self._menu_registration_id)
            self._registration_id = 0
            self._menu_registration_id = 0 # Reset menu ID too
        logger.debug("GnomeStatusIcon.__init__ finished.")


    def _on_bus_acquired(self, connection, name):
        logger.debug(f"_on_bus_acquired called for name '{name}'.")
        logger.info(f"D-Bus connection acquired for name '{name}'.")
        # This callback confirms the connection is ready *if* we didn't get it synchronously before.
        # We already got the bus sync, so this is mostly informational here.
        pass
        logger.debug(f"_on_bus_acquired finished for name '{name}'.")

    def _on_name_acquired(self, connection, name): # Note: The owner_id is NOT passed here. It's returned by bus_own_name itself.
        logger.debug(f"_on_name_acquired called for name '{name}'.")
        logger.info(f"Successfully acquired D-Bus name: {name} (Owner ID stored: {self._bus_name_id})")
        if self._bus_name_id == 0:
             logger.warning("Bus name acquired, but stored owner ID is 0. Cleanup might fail.")
        # Now we need to register with the StatusNotifierWatcher
        logger.debug(f"Calling _register_with_watcher for name '{name}'.")
        self._register_with_watcher()
        # Emit initial LayoutUpdated signal for dbusmenu (Restored)
        logger.debug("Emitting initial LayoutUpdated signal for the menu.")
        # revision=1 (matches _build_menu_layout), parentId=0 (root)
        self._emit_menu_signal("LayoutUpdated", GLib.Variant("(ui)", (1, 0)))
        logger.debug(f"_on_name_acquired finished for name '{name}'.")
    def _on_name_lost(self, connection, name):
        logger.error(f"****** D-BUS NAME LOST UNEXPECTEDLY: {name} ******") # Add prominent log
        logger.warning(f"Lost D-Bus name: {name}")
        self._bus_name_id = 0 # Reset ID
        # Clean up registrations if name is lost
        self.cleanup()

    def _register_with_watcher(self):
        """Register this item with the StatusNotifierWatcher."""
        logger.debug("_register_with_watcher starting.")
        if not self._bus:
            logger.error("Cannot register with watcher, no D-Bus connection.")
            return

        watcher_name = "org.kde.StatusNotifierWatcher"
        watcher_path = "/StatusNotifierWatcher"
        watcher_interface = "org.kde.StatusNotifierWatcher"

        try:
            # Create a proxy to the watcher
            logger.debug(f"Creating D-Bus proxy for {watcher_name} at {watcher_path}")
            proxy = Gio.DBusProxy.new_sync(
                self._bus,
                Gio.DBusProxyFlags.NONE,
                None,  # interface info (optional)
                watcher_name,
                watcher_path,
                watcher_interface,
                None # cancellable
            )
            logger.debug(f"D-Bus proxy created: {proxy}")

            # Call the RegisterStatusNotifierItem method
            # The argument is the service name (our unique bus name)
            variant = GLib.Variant("(s)", (self._bus_name,))
            logger.debug(f"Calling RegisterStatusNotifierItem with service name variant: {variant.print_(True)}")
            proxy.call_sync(
                "RegisterStatusNotifierItem",
                variant,
                Gio.DBusCallFlags.NONE,
                -1, # timeout default
                None # cancellable
            )
            logger.debug("RegisterStatusNotifierItem call completed.")
            logger.info(f"Successfully registered with StatusNotifierWatcher using service name: {self._bus_name}")

        except GLib.Error as e:
            logger.error(f"Failed to register with StatusNotifierWatcher: {e}")
            # Common reasons: Watcher service not running (no tray extension?)
            # or incorrect service name format.
        logger.debug("_register_with_watcher finished.")

    def _handle_method_call(self, connection, sender, object_path, interface_name,
                             method_name, parameters, invocation):
        """Handles incoming D-Bus method calls for StatusNotifierItem."""
        logger.debug(f"_handle_method_call: Received call {interface_name}.{method_name} from {sender} on {object_path}")

        if interface_name != "org.kde.StatusNotifierItem":
            # Should not happen given the registration path/interface
            logger.warning(f"Received method call for unexpected interface: {interface_name}")
            # Indicate method not handled
            invocation.return_error_literal(Gio.DBusError, Gio.DBusError.UNKNOWN_METHOD, f"Unknown interface {interface_name}")
            return

        if method_name == "ContextMenu":
            logger.debug("Handling 'ContextMenu' method.")
            x = parameters.get_child_value(0).get_int32()
            y = parameters.get_child_value(1).get_int32()
            logger.info(f"ContextMenu requested at ({x}, {y})")
            # TODO: Implement actual menu display logic here using the Dbusmenu interface
            # For now, just acknowledge the call.
            invocation.return_value(None) # No return value for ContextMenu
        elif method_name == "Activate":
            logger.debug("Handling 'Activate' method.")
            x = parameters.get_child_value(0).get_int32()
            y = parameters.get_child_value(1).get_int32()
            logger.info(f"Activate requested at ({x}, {y})")
            # Activate the 'toggle_window' action
            logger.info("Activating 'app.toggle_window' action.")
            GLib.idle_add(self._application.activate_action, "toggle_window", None)
            invocation.return_value(None) # No return value for Activate
        else:
            logger.warning(f"Received unknown method call: {method_name}")
            invocation.return_error_literal(Gio.DBusError, Gio.DBusError.UNKNOWN_METHOD, f"Unknown method {method_name}")
        logger.debug(f"_handle_method_call finished for {method_name}.")

    # Restored _handle_menu_method_call
    def _handle_menu_method_call(self, connection, sender, object_path, interface_name,
                                method_name, parameters, invocation):
        """Handles incoming D-Bus method calls for Dbusmenu."""
        logger.debug(f"_handle_menu_method_call: Received call {interface_name}.{method_name} from {sender} on {object_path}")

        if interface_name != "com.canonical.dbusmenu":
            logger.warning(f"Received menu method call for unexpected interface: {interface_name}")
            invocation.return_error_literal(Gio.DBusError, Gio.DBusError.UNKNOWN_METHOD, f"Unknown interface {interface_name}")
            return

        # --- Implementations for required menu methods ---
        if method_name == "GetLayout":
            logger.debug("Handling 'GetLayout' method.")
            # Unpack the (iias) parameters for GetLayout
            parent_id_variant = parameters.get_child_value(0)
            recursion_depth_variant = parameters.get_child_value(1)
            property_names_variant = parameters.get_child_value(2)

            parent_id = parent_id_variant.get_int32()
            recursion_depth = recursion_depth_variant.get_int32()
            property_names = property_names_variant.get_strv() # Use get_strv() for 'as'

            logger.debug(f"GetLayout called: parent={parent_id}, depth={recursion_depth}, props={property_names}")
            # Build and return the actual menu layout
            # _build_menu_layout now returns revision and the NATIVE layout tuple
            revision, layout_data_tuple = self._build_menu_layout(parent_id, recursion_depth, property_names)
            # Construct the final variant here, passing the native tuple for the inner structure
            # Return type is (u (ia{sv}av))
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (revision, layout_data_tuple)))

        elif method_name == "GetGroupProperties":
            logger.debug("Handling 'GetGroupProperties' method.")
            # Return empty array for now, not typically needed for simple menus
            # The signature expects a tuple containing the array: (a(ia{sv}))
            invocation.return_value(GLib.Variant("(a(ia{sv}))", ([],)))

        elif method_name == "GetProperty":
            logger.debug("Handling 'GetProperty' method.")
            # This handles properties of the *menu object itself*, not items
            item_id, prop_name_variant = parameters.get_children()
            prop_name = prop_name_variant.get_string()
            logger.debug(f"GetProperty called for menu object (ID: {item_id.get_int32()}) prop: {prop_name}")
            # Look up property using our GObject property system
            try:
                 # Map D-Bus prop names to GObject prop names
                 gobject_prop_name = prop_name.lower().replace('-', '_')
                 # Special case for dbusmenu status vs SNI status
                 if gobject_prop_name == 'status':
                     gobject_prop_name = 'dbusmenu_status'

                 value = self.get_property(gobject_prop_name)
                 # Convert to variant - rely on _handle_get_property's logic for wrapping
                 variant = self._value_to_variant(value, prop_name) # Use helper
                 if variant:
                     invocation.return_value(GLib.Variant("(v)", (variant,)))
                     logger.debug(f"Returned menu property {gobject_prop_name}: {value}")
                 else:
                      raise ValueError(f"Could not convert {gobject_prop_name} to variant")
            except Exception as e:
                 logger.error(f"Error getting menu property {prop_name}: {e}")
                 invocation.return_error_literal(Gio.DBusError, Gio.DBusError.INVALID_ARGS, f"Unknown or unconvertible property {prop_name}")

        elif method_name == "Event":
            logger.debug("Handling 'Event' method.")
            # Unpack the (isvu) tuple variant using get_child_value
            item_id_variant = parameters.get_child_value(0)
            event_id_variant = parameters.get_child_value(1)
            data_variant = parameters.get_child_value(2) # data is type 'v' (variant)
            timestamp_variant = parameters.get_child_value(3)

            # Extract native values
            item_id = item_id_variant.get_int32()
            event_id = event_id_variant.get_string()
            timestamp = timestamp_variant.get_uint32()

            logger.info(f"Menu Event: id={item_id}, event='{event_id}', data='{data_variant.print_(True)}', timestamp={timestamp}")
            # Handle menu item activation ('clicked')
            if event_id == 'clicked':
                self._handle_menu_item_clicked(item_id) # Call handler with the native int
            # Acknowledge event, no return value needed typically
            invocation.return_value(None)

        elif method_name == "AboutToShow":
            logger.debug("Handling 'AboutToShow' method.")
            item_id = parameters.get_child_value(0).get_int32() # Get first arg as int
            logger.debug(f"AboutToShow called for ID: {item_id}")
            # We don't need dynamic updates for this simple menu
            needs_update = False
            invocation.return_value(GLib.Variant("(b)", (needs_update,)))

        # --- Methods we likely don't need complex logic for initially ---
        elif method_name in ["EventGroup", "AboutToShowGroup"]:
             logger.debug(f"Handling '{method_name}' method (ignored/default response).")
             # Provide valid default returns if necessary based on spec
             if method_name == "EventGroup":
                 invocation.return_value(GLib.Variant("(ai)", ([]))) # No errors
             elif method_name == "AboutToShowGroup":
                 # ids_variant = parameters.get_variant(0) # Get first arg as variant
                 # ids = ids_variant.get_int32_array() # Assuming it's ai
                 invocation.return_value(GLib.Variant("(ai ai)", ([], []))) # No updates needed, no errors
             else:
                 invocation.return_value(None) # Fallback
        else:
            logger.warning(f"Received unknown menu method call: {method_name}")
            invocation.return_error_literal(Gio.DBusError, Gio.DBusError.UNKNOWN_METHOD, f"Unknown method {method_name}")
        logger.debug(f"_handle_menu_method_call finished for {method_name}.")

    def _handle_get_property(self, connection, sender, object_path, interface_name, property_name):
        """Handles incoming D-Bus property get requests."""
        logger.debug(f"_handle_get_property: Received request for {interface_name}.{property_name} from {sender} on {object_path}")
        value = None
        variant = None
        try:
            # Map D-Bus property name (CamelCase) to GObject property name (snake_case)
            gobject_prop_name = property_name.lower().replace('-', '_')

            # --- Add specific checks for debugging ---
            if property_name == "IconName":
                print("DEBUG: Explicitly getting 'icon_name'") # DEBUG PRINT
                value = self.icon_name # Use direct attribute access
            elif property_name == "ItemIsMenu":
                print("DEBUG: Explicitly getting 'item_is_menu'") # DEBUG PRINT
                value = self.item_is_menu # Use direct attribute access
            # --- End specific checks ---

            # Handle StatusNotifierItem properties
            elif interface_name == "org.kde.StatusNotifierItem":
                if property_name == 'ToolTip': # Use D-Bus name directly for special handling
                    variant = self.get_tool_tip_variant()
                    logger.debug(f"Returning property ToolTip as Variant {variant.print_(True)}")
                    return variant # Return the already created variant directly
                elif property_name == 'Menu':
                    # Return the object path where the dbusmenu object is registered
                    # ensuring it's correctly typed as 'o' (object path).
                    if self._dbus_menu_object_path: # Check the correct path variable
                        variant = GLib.Variant('o', self._dbus_menu_object_path) # Use the correct path variable
                        logger.debug(f"Returning property Menu as Variant {variant.print_(True)}")
                        return variant # Return the correctly typed variant directly
                    else:
                         # Should not happen if init succeeded, but return null variant if no path
                         logger.warning("Menu property requested but _dbus_menu_object_path is None.")
                         return GLib.Variant('o', '/') # Return default '/' path variant? Or None? Let's use '/'
                # Add other SNI properties using mapped name
                elif gobject_prop_name == 'id': value = self.id
                elif gobject_prop_name == 'category': value = self.category
                elif gobject_prop_name == 'status': value = self.status
                elif gobject_prop_name == 'icon_name': value = self.icon_name
                elif gobject_prop_name == 'item_is_menu': value = self.item_is_menu
                else:
                    logger.warning(f"GetProperty request for unknown SNI property: {property_name}")
                    return None

            # Restored com.canonical.dbusmenu interface handling for GObject props
            elif interface_name == "com.canonical.dbusmenu":
                 # Handle specific dbusmenu properties if naming differs significantly
                 if gobject_prop_name == 'status':
                     gobject_prop_name = 'dbusmenu_status' # Map to our internal name
                 # Use the mapped gobject_prop_name for standard GObject properties
                 value = self.get_property(gobject_prop_name)
            else:
                logger.warning(f"GetProperty request for unknown interface: {interface_name}")
                return None # Returning None indicates property not found

            # If we got a value from the property checks (that wasn't returned directly), wrap it.
            # Note: ToolTip and Menu are now returned directly above.
            if value is not None:
                # Use helper function to convert value to variant
                variant = self._value_to_variant(value, property_name)
                if variant:
                     logger.debug(f"Returning property {property_name}: {value} as Variant {variant.print_(True)}")
                     return variant
                else:
                     logger.error(f"Could not convert value for property {property_name} to Variant.")
                     return None # Indicate error
            else:
                 # This case handles if none of the specific checks above yielded a value
                 # (excluding ToolTip which returns directly)
                 logger.warning(f"_handle_get_property: Property {interface_name}.{property_name} (mapped to {gobject_prop_name}) not found or is None.")
                 logger.debug(f"_handle_get_property finished for {interface_name}.{property_name} (not found).")
                 return None # Property not found

        except Exception as e:
            logger.error(f"Error getting property {interface_name}.{property_name}: {e}", exc_info=True) # Added exc_info for better debugging
            logger.debug(f"_handle_get_property finished for {interface_name}.{property_name} (error).")
            return None # Indicate error by returning None

    # Restored _handle_menu_item_clicked
    def _handle_menu_item_clicked(self, item_id):
        """Handles menu item activation based on its ID."""
        logger.info(f"Menu item clicked: ID={item_id}")
        action_name = None
        # Map item_id back to the corresponding application action
        # These IDs must match those defined in _build_menu_layout
        if item_id == 1:
            action_name = "toggle_window"
        elif item_id == 2:
            action_name = "preferences"
        elif item_id == 3:
            action_name = "about"
        # Item ID 4 is separator
        elif item_id == 5:
            action_name = "quit"

        if action_name:
            logger.info(f"Activating 'app.{action_name}' action for menu item {item_id}.")
            # Use GLib.idle_add for safety, though activate_action might be main-thread safe
            GLib.idle_add(self._application.activate_action, action_name, None)
        else:
            logger.warning(f"No action mapped for menu item ID: {item_id}")
        logger.debug(f"_handle_menu_item_clicked finished for item ID={item_id}")


    # Restored _build_menu_layout
    def _build_menu_layout(self, parent_id, recursion_depth, property_names):
        """Builds the D-Bus menu layout structure for com.canonical.dbusmenu using VariantBuilder."""
        logger.debug(f"_build_menu_layout starting: parent_id={parent_id}, depth={recursion_depth}, props={property_names}")
        # Revision number for the layout
        revision = 1 # Increment if layout changes significantly

        # Define menu items: (id, label, action_name_suffix, icon_name)
        menu_structure = [
            (1, _("Show / Hide"), "toggle_window", None),
            (2, _("Preferences"), "preferences", "preferences-system-symbolic"),
            (3, _("About"), "about", "help-about-symbolic"),
            (4, None, None, None), # Separator ID 4
            (5, _("Quit"), "quit", "application-exit-symbolic"),
        ]

        children_variants = []
        # We only provide layout for the root (parent_id == 0)
        if parent_id == 0:
            for item_id, label, action_suffix, icon_name in menu_structure:
                # Create props dict, wrapping VALUES in GLib.Variant for a{sv}
                item_type = 'separator' if not label and not action_suffix else 'standard'
                props = {
                    'visible': GLib.Variant('b', True),
                    'enabled': GLib.Variant('b', True),
                    'type': GLib.Variant('s', item_type),
                }
                if label:
                    props['label'] = GLib.Variant('s', label)
                if action_suffix:
                     # Use the full 'app.action' name
                    props['action'] = GLib.Variant('s', f"app.{action_suffix}")
                if icon_name:
                    props['icon-name'] = GLib.Variant('s', icon_name)

                # Create item variant - PASS NATIVE TYPES (int, dict, list) for the tuple (i a{sv} av)
                # The 'props' dict contains Variants as values, which is correct for a{sv}.
                # The 'children' list is empty, which is correct for 'av'.
                item_variant = GLib.Variant('(ia{sv}av)', (item_id, props, []))
                children_variants.append(item_variant)

        # Root node layout: (root_id=0, props_dict, children_list)
        # Root node properties as a standard Python dict
        root_props = {'children-display': GLib.Variant('s', 'submenu')}

        # Prepare the NATIVE Python tuple structure (int, dict, list) to be returned.
        # The dict (root_props) and the list (children_variants) contain GLib.Variants where required internally (e.g., values in a{sv}).
        layout_data_tuple = (0, root_props, children_variants)

        logger.debug(f"_build_menu_layout finished (rev {revision}): Returning native layout tuple.")
        # Return the revision and the NATIVE layout tuple
        return revision, layout_data_tuple

    # Helper to convert Python value to GLib.Variant for property getters
    def _value_to_variant(self, value, property_name_for_logging=""):
        variant = None
        try:
            if isinstance(value, str):
                variant = GLib.Variant.new_string(value)
            elif isinstance(value, bool):
                variant = GLib.Variant.new_boolean(value)
            elif isinstance(value, int):
                # Dbusmenu Version is 'u' (uint32)
                if property_name_for_logging == "Version":
                    variant = GLib.Variant.new_uint32(value)
                else: # Assume others are standard int 'i' (int32)
                    variant = GLib.Variant.new_int32(value)
            elif isinstance(value, list) and all(isinstance(s, str) for s in value):
                # Handle string arrays ('as') like IconThemePath
                variant = GLib.Variant.new_strv(value)
            # Add elif for other types if needed
            else:
                 logger.error(f"Cannot create Variant for unhandled type: {type(value)} (Property: {property_name_for_logging})")
        except Exception as e:
             logger.error(f"Error converting value '{value}' to Variant (Property: {property_name_for_logging}): {e}")

        return variant

    def _emit_signal(self, signal_name, parameters):
         """Helper to emit a D-Bus signal on the StatusNotifierItem interface."""
         logger.debug(f"_emit_signal: Attempting to emit '{signal_name}' with params: {parameters.print_(True) if parameters else 'None'}")
         if not self._bus or self._registration_id == 0:
              logger.warning(f"Cannot emit signal '{signal_name}', D-Bus not fully setup.")
              return
         try:
              self._bus.emit_signal(
                   None, # destination_bus_name (None for broadcast)
                   self._object_path, # Object path of the SNI
                   "org.kde.StatusNotifierItem", # Interface name
                   signal_name,
                   parameters
              )
              logger.debug(f"_emit_signal: Successfully emitted D-Bus signal: {signal_name}")
         except GLib.Error as e:
              logger.error(f"Error emitting D-Bus signal {signal_name}: {e}")

    # Restored _emit_menu_signal
    def _emit_menu_signal(self, signal_name, parameters):
         """Helper to emit a D-Bus signal on the com.canonical.dbusmenu interface."""
         logger.debug(f"_emit_menu_signal: Attempting to emit '{signal_name}' with params: {parameters.print_(True) if parameters else 'None'}")
         # Use menu registration ID for check
         if not self._bus or self._menu_registration_id == 0:
              logger.warning(f"Cannot emit menu signal '{signal_name}', D-Bus not fully setup for menu.")
              return
         try:
              self._bus.emit_signal(
                   None, # destination_bus_name (None for broadcast)
                   self._dbus_menu_object_path, # Object path of the MENU
                   "com.canonical.dbusmenu", # Interface name
                   signal_name,
                   parameters
              )
              logger.debug(f"_emit_menu_signal: Successfully emitted D-Bus signal: {signal_name}")
         except GLib.Error as e:
              logger.error(f"Error emitting D-Bus menu signal {signal_name}: {e}")


    def cleanup(self):
        """Unregister D-Bus objects and release name."""
        logger.debug("GnomeStatusIcon cleanup starting.")
        logger.info("Cleaning up GnomeStatusIcon D-Bus connections.")

        # 1. Unregister D-Bus objects first
        if self._bus:
            if self._registration_id > 0:
                logger.debug(f"Attempting to unregister SNI object with ID: {self._registration_id}")
                unregistered = self._bus.unregister_object(self._registration_id)
                if unregistered:
                    logger.info("Unregistered StatusNotifierItem D-Bus object.")
                else:
                    logger.warning("Failed to unregister StatusNotifierItem D-Bus object.")
                self._registration_id = 0 # Mark as unregistered regardless

            # Restored menu object unregistration using its ID (CORRECT INDENTATION)
            if self._menu_registration_id > 0:
                logger.debug(f"Attempting to unregister Menu object with ID: {self._menu_registration_id}")
                unregistered = self._bus.unregister_object(self._menu_registration_id)
                if unregistered:
                    logger.info("Unregistered Dbusmenu D-Bus object.")
                else:
                    logger.warning("Failed to unregister Dbusmenu D-Bus object.")
                self._menu_registration_id = 0 # Mark as unregistered regardless

        # Removed Gio.Menu unexport logic

        # 3. Unown the bus name using the stored ID
        # Ensure we have a valid ID returned by Gio.bus_own_name
        if self._bus_name_id > 0:
            logger.debug(f"Attempting to release/unown D-Bus name '{self._bus_name}' using owner ID: {self._bus_name_id}")
            logger.info(f"Attempting to release D-Bus name owner ID: {self._bus_name_id} for name '{self._bus_name}'")
            try:
                # Pass the owner_id obtained from bus_own_name
                Gio.bus_unown_name(self._bus_name_id)
                logger.info(f"Successfully requested release of D-Bus name: {self._bus_name}")
                logger.debug(f"Gio.bus_unown_name called for ID {self._bus_name_id}.")
            except GLib.Error as e:
                 # This can happen if the connection is already closed or the name was lost
                 logger.warning(f"GLib error releasing D-Bus name ID {self._bus_name_id} ({self._bus_name}): {e}")
            except Exception as e: # Catch potential other errors
                 logger.error(f"Unexpected error releasing D-Bus name ID {self._bus_name_id} ({self._bus_name}): {e}", exc_info=True)
            self._bus_name_id = 0 # Mark as unowned attempt complete

        # 4. Release bus reference (optional, helps garbage collection)
        logger.debug("Setting self._bus to None.")
        self._bus = None
        logger.info("GnomeStatusIcon cleanup finished.")