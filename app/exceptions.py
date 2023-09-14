class Error(Exception):
    pass

class ValidationError(Error):
    def __init__(self, message):
        self.message = message