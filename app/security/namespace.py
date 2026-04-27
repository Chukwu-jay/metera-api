from fastapi import HTTPException, status


VALID_NAMESPACE_CHARACTERS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def resolve_namespace(header_value: str | None, configured_header_name: str) -> str:
    if not header_value:
        return "default"

    namespace = header_value.strip()
    validate_namespace(namespace, configured_header_name=configured_header_name)
    return namespace


def validate_namespace(namespace: str, *, configured_header_name: str = "x-metera-namespace") -> str:
    if not namespace:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Header {configured_header_name} cannot be empty",
        )
    if len(namespace) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Header {configured_header_name} is too long",
        )
    if any(character not in VALID_NAMESPACE_CHARACTERS for character in namespace):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Header {configured_header_name} contains invalid namespace characters",
        )
    return namespace
