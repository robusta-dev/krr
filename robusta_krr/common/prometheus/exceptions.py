

class MetricsNotFound(Exception):
    """
    An exception raised when Metrics service is not found.
    """

    pass

class PrometheusNotFound(MetricsNotFound):
    """
    An exception raised when Prometheus is not found.
    """

    pass

class VictoriaMetricsNotFound(MetricsNotFound):
    """
    An exception raised when Victoria Metrics is not found.
    """

    pass

class ThanosMetricsNotFound(MetricsNotFound):
    """
    An exception raised when Thanos is not found.
    """

    pass

class PrometheusFlagsConnectionError(Exception):
    """
    Exception, when Prometheus flag or AlertManager flag api cannot be reached
    """
    
    pass