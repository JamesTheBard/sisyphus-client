class Error(Exception):
    pass


class ValidationError(Error):
    def __init__(self, message):
        self.message = message


class InitializationError(Error):
    def __init__(self, message):
        self.message = message


class RunError(Error):
    def __init__(self, message):
        self.message = message


class CleanupError(Error):
    def __init__(self, message):
        self.message = message
