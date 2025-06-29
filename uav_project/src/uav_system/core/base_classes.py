"""
Base classes for the UAV system components.
"""

import abc
from typing import Any, Dict, Optional
from ..core.logging_config import get_logger


class BaseComponent(abc.ABC):
    """Base class for all UAV system components."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.logger = get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._initialized = False
        self._running = False
    
    @abc.abstractmethod
    def initialize(self) -> bool:
        """Initialize the component."""
        pass
    
    @abc.abstractmethod
    def start(self) -> bool:
        """Start the component."""
        pass
    
    @abc.abstractmethod
    def stop(self) -> bool:
        """Stop the component."""
        pass
    
    @abc.abstractmethod
    def cleanup(self) -> bool:
        """Clean up component resources."""
        pass
    
    @property
    def is_initialized(self) -> bool:
        """Check if component is initialized."""
        return self._initialized
    
    @property
    def is_running(self) -> bool:
        """Check if component is running."""
        return self._running


class BaseSensor(BaseComponent):
    """Base class for all sensor components."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self._last_reading = None
        self._reading_count = 0
    
    @abc.abstractmethod
    def read_data(self) -> Any:
        """Read data from the sensor."""
        pass
    
    @abc.abstractmethod
    def calibrate(self) -> bool:
        """Calibrate the sensor."""
        pass
    
    @property
    def last_reading(self) -> Any:
        """Get the last sensor reading."""
        return self._last_reading
    
    @property
    def reading_count(self) -> int:
        """Get the total number of readings."""
        return self._reading_count


class BaseProtocol(BaseComponent):
    """Base class for all communication protocols."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self._connected = False
    
    @abc.abstractmethod
    def connect(self, connection_string: str) -> bool:
        """Connect using the protocol."""
        pass
    
    @abc.abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the protocol."""
        pass
    
    @abc.abstractmethod
    def send_data(self, data: Any) -> bool:
        """Send data using the protocol."""
        pass
    
    @abc.abstractmethod
    def receive_data(self) -> Any:
        """Receive data using the protocol."""
        pass
    
    @property
    def is_connected(self) -> bool:
        """Check if protocol is connected."""
        return self._connected


class BaseController(BaseComponent):
    """Base class for all control components."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self._target_value = None
        self._current_value = None
    
    @abc.abstractmethod
    def set_target(self, target: Any) -> bool:
        """Set the target value for the controller."""
        pass
    
    @abc.abstractmethod
    def update(self, current_value: Any) -> Any:
        """Update the controller with current value and return control output."""
        pass
    
    @abc.abstractmethod
    def reset(self) -> bool:
        """Reset the controller state."""
        pass
    
    @property
    def target_value(self) -> Any:
        """Get the current target value."""
        return self._target_value
    
    @property
    def current_value(self) -> Any:
        """Get the current value."""
        return self._current_value
