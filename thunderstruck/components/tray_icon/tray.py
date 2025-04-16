import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib 

import logging

logger = logging.getLogger(__name__)

# Tray icon functionality removed due to GTK3/GTK4 incompatibility with AppIndicator3.
# TODO: Investigate alternative GTK4-compatible tray icon solutions if needed.