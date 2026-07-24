def ensure_hosts_present(hosts, *required):
    """Return `hosts` with every value in `required` present, without
    duplicating ones already there. Used to guarantee container-internal
    health-check hostnames (127.0.0.1, localhost) always pass Django's
    ALLOWED_HOSTS check regardless of what an operator configures for the
    public domain — see config/settings.py.
    """
    result = list(hosts)
    for host in required:
        if host not in result:
            result.append(host)
    return result
