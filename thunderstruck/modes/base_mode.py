import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GObject, Gtk
from abc import ABC, abstractmethod

class BaseMode(ABC):
    """
    Abstract base class for all application modes.
    Each mode represents a distinct functionality or view within the application.
    """
    __gsignals__ = {} # Modes can define their own signals if needed

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    @abstractmethod
    def name(self) -> str:
        """
        The user-visible name of the mode (e.g., "AI Chat").
        """
        pass

    @property
    @abstractmethod
    def icon_name(self) -> str:
        """
        The icon name associated with the mode (e.g., "dialog-question-symbolic").
        Should correspond to a themed icon available in the system or application resources.
        """
        pass

    @abstractmethod
    def get_widget(self) -> Gtk.Widget:
        """
        Returns the primary Gtk.Widget associated with this mode.
        This widget will be displayed in the main window's content area when the mode is active.
        Implementations should ideally create the widget lazily or ensure it's lightweight
        until activated.
        """
        pass

    def activate(self) -> None:
        """
        Called when the mode becomes the active mode.
        Subclasses can override this to perform setup, start services, etc.
        """
        # Default implementation does nothing
        pass

    def handle_escape(self) -> bool:
        """
        Called when the Escape key is pressed while this mode is active.
        Modes can override this to perform mode-specific actions (e.g., clear search).

        Returns:
            bool: True if the mode handled the Escape key, False otherwise.
                  If False, the default action (e.g., hiding the window) may occur.
        """
        return False # Default: Mode does not handle Escape

    def deactivate(self) -> None:
        """
        Called when the mode is no longer the active mode.
        Subclasses can override this to perform cleanup, stop services, etc.
        """
        # Default implementation does nothing
        pass

    def __str__(self):
        # Implement __str__ only after name is available (concrete class)
        try:
            return f"<BaseMode name='{self.name}'>"
        except NotImplementedError:
            return f"<{self.__class__.__name__} (Abstract)>"


    def __repr__(self):
         # Implement __repr__ only after name/icon are available (concrete class)
        try:
            return f"{self.__class__.__name__}(name='{self.name}', icon='{self.icon_name}')"
        except NotImplementedError:
            return f"<{self.__class__.__name__} (Abstract)>"