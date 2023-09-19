class Error(Exception):
    pass


class ValidationError(Error):
    """Task data is invalid."""
    def __init__(self, message):
        self.message = message


class InitializationError(Error):
    """Initialization failed during task load."""
    def __init__(self, message):
        self.message = message


class RunError(Error):
    """Running the module failed."""
    def __init__(self, message):
        self.message = message


class CleanupError(Error):
    """Could not cleanup the module."""
    def __init__(self, message):
        self.message = message
