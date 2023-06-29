class ModularCliSdkBaseException(Exception):
    """
    Base Modular CLI SDK exception
    """


class ModularCliSdkBadRequestException(ModularCliSdkBaseException):
    """
    Incoming request is invalid due to parameters invalidity
    """
    code = 400


class ModularCliSdkNotFoundException(ModularCliSdkBaseException):
    """
    The requested resource not found
    """
    code = 404


class ModularCliSdkConfigurationException(ModularCliSdkBaseException):
    """
    Configuration exception
    """
    code = 503
