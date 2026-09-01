class InviteError(Exception):
    """Basisklasse für alle Invite-bezogenen Fehler."""

    pass


class DuplicateInviteError(InviteError):
    """Es existiert bereits ein offener Invite für diese E-Mail im Tenant."""

    pass


class InvalidInviteTokenError(InviteError):
    """Token existiert nicht, ist abgelaufen, oder bereits verbraucht/revoked."""

    pass
