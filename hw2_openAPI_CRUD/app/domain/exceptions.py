class DomainException(Exception):

    error_code: str = "DOMAIN_ERROR"
    http_status: int = 500

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ProductNotFoundException(DomainException):
    error_code = "PRODUCT_NOT_FOUND"
    http_status = 404


class ProductInactiveException(DomainException):
    error_code = "PRODUCT_INACTIVE"
    http_status = 409


class OrderNotFoundException(DomainException):
    error_code = "ORDER_NOT_FOUND"
    http_status = 404


class OrderLimitExceededException(DomainException):
    error_code = "ORDER_LIMIT_EXCEEDED"
    http_status = 429


class OrderHasActiveException(DomainException):
    error_code = "ORDER_HAS_ACTIVE"
    http_status = 409


class InvalidStateTransitionException(DomainException):
    error_code = "INVALID_STATE_TRANSITION"
    http_status = 409


class InsufficientStockException(DomainException):
    error_code = "INSUFFICIENT_STOCK"
    http_status = 409


class PromoCodeInvalidException(DomainException):
    error_code = "PROMO_CODE_INVALID"
    http_status = 422


class PromoCodeMinAmountException(DomainException):
    error_code = "PROMO_CODE_MIN_AMOUNT"
    http_status = 422


class OrderOwnershipViolationException(DomainException):
    error_code = "ORDER_OWNERSHIP_VIOLATION"
    http_status = 403


class AccessDeniedException(DomainException):
    error_code = "ACCESS_DENIED"
    http_status = 403


class TokenExpiredException(DomainException):
    error_code = "TOKEN_EXPIRED"
    http_status = 401


class TokenInvalidException(DomainException):
    error_code = "TOKEN_INVALID"
    http_status = 401


class RefreshTokenInvalidException(DomainException):
    error_code = "REFRESH_TOKEN_INVALID"
    http_status = 401


class ConflictException(DomainException):
    error_code = "CONFLICT"
    http_status = 409
