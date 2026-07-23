from django.conf import settings


def platform_settings(request):
    return {
        "PLATFORM_NAME": settings.PLATFORM_NAME,
        "NETWORK_SHORT_NAME": settings.NETWORK_SHORT_NAME,
        "NETWORK_TAGLINE": settings.NETWORK_TAGLINE,
    }
