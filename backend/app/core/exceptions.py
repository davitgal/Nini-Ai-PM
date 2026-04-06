class NiniError(Exception):
    """Base exception for Nini."""

    def __init__(self, message: str = "An error occurred", status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ClickUpAPIError(NiniError):
    """Error communicating with ClickUp API."""

    def __init__(self, message: str = "ClickUp API error", status_code: int = 502):
        super().__init__(message, status_code)


class SyncError(NiniError):
    """Error during sync operation."""

    def __init__(self, message: str = "Sync error"):
        super().__init__(message, status_code=500)


class WebhookVerificationError(NiniError):
    """Invalid webhook signature."""

    def __init__(self):
        super().__init__("Invalid webhook signature", status_code=401)
