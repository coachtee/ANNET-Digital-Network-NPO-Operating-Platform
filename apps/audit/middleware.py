import threading

_thread_locals = threading.local()


class AuditContextMiddleware:
    """Stashes the current request's user/IP in thread-local storage so
    ``apps.audit.services.log_action`` can be called from model signals or
    service functions that do not have direct access to the request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, "user", None)
        _thread_locals.ip_address = request.META.get("REMOTE_ADDR")
        try:
            return self.get_response(request)
        finally:
            _thread_locals.user = None
            _thread_locals.ip_address = None


def get_current_user():
    return getattr(_thread_locals, "user", None)


def get_current_ip():
    return getattr(_thread_locals, "ip_address", None)
