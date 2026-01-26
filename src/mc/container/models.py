"""Container metadata models."""

from dataclasses import dataclass


@dataclass
class ContainerMetadata:
    """Metadata for a case container.

    Attributes:
        case_number: Salesforce case number (primary identifier)
        container_id: Podman container ID
        workspace_path: Host workspace directory path
        created_at: Unix timestamp when container was created
        updated_at: Unix timestamp when metadata was last updated
    """

    case_number: str
    container_id: str
    workspace_path: str
    created_at: int
    updated_at: int
