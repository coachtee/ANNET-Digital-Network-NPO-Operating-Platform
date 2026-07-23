from apps.networks.models import Network


def get_primary_network():
    """The platform supports multiple network deployments (spec section 2),
    but this initial build anchors the UI to a single primary network
    (ANNET) rather than adding network-switching UI ahead of a real second
    deployment. Extending to multiple concurrent networks later only
    requires swapping this lookup for a request-scoped one.
    """
    return Network.objects.order_by("created_at").first()
