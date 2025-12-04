class PVConnectionError(Exception):
    """Raised when PV fails to connect"""

    pass


class PVGetError(Exception):
    """Raised when PV get operation fails"""

    pass


class PVPutError(Exception):
    """Raised when PV put operation fails"""

    pass


class PVInvalidError(Exception):
    """Raised when PV value is invalid"""

    pass
