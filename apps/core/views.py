from django.http import HttpResponse


def health_check(request):
    """Liveness/readiness probe for Docker/Kubernetes/Coolify.

    Deliberately does nothing else: no auth, no DB or cache query, no
    template render, no redirect. It exists purely to prove the WSGI
    process is up and serving requests. See SECURE_REDIRECT_EXEMPT and the
    always-allowed hosts in config/settings.py — both exist specifically so
    this endpoint keeps working regardless of ALLOWED_HOSTS/HTTPS
    configuration, since health probes hit the container directly over
    plain HTTP on its internal port, not through the public domain/proxy.
    """
    return HttpResponse("OK", content_type="text/plain")
