from identityos import Identity, IdentityObject


def load_or_create_identity(
    identity_id: str,
    identity_name: str = "Discord Agent",
    identity_class: str = "assistant",
    storage_path: str = "/data/identities",
) -> IdentityObject:
    """Load an existing identity or create a new one, then return it."""
    try:
        identity = Identity.load(identity_id, storage_path=storage_path)
        return identity
    except Exception:
        identity = Identity.create(
            name=identity_name,
            identity_id=identity_id,
            identity_class=identity_class,
            storage_path=storage_path,
        )
        return identity
