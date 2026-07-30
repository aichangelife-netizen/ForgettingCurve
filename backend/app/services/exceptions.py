class ServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class NotFoundError(ServiceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(404, code, message)


class ConflictError(ServiceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(409, code, message)


class ValidationServiceError(ServiceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(422, code, message)
