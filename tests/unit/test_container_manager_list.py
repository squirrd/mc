"""Unit tests for ContainerManager list operation."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest

from mc.container.manager import ContainerManager
from mc.container.models import ContainerMetadata
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


@pytest.fixture
def mock_podman_client() -> MagicMock:
    """Create mock Podman client."""
    client = MagicMock(spec=PodmanClient)
    client.client = MagicMock()
    client.client.containers = MagicMock()
    return client


@pytest.fixture
def mock_state_db() -> MagicMock:
    """Create mock state database."""
    return MagicMock(spec=StateDatabase)


@pytest.fixture
def container_manager(
    mock_podman_client: MagicMock, mock_state_db: MagicMock
) -> ContainerManager:
    """Create ContainerManager with mocked dependencies."""
    return ContainerManager(mock_podman_client, mock_state_db)


def create_mock_container(
    container_id: str,
    short_id: str,
    case_number: str,
    customer: str,
    status: str,
    started_at: str | None = None
) -> Mock:
    """Create a mock Podman container object.

    Args:
        container_id: Full container ID
        short_id: Short container ID
        case_number: Salesforce case number
        customer: Customer name
        status: Container status (running, stopped, exited)
        started_at: ISO timestamp when container started (for running containers)

    Returns:
        Mock container object with required attributes
    """
    container = Mock()
    container.id = container_id
    container.short_id = short_id
    container.status = status
    container.labels = {
        "mc.managed": "true",
        "mc.case_number": case_number,
        "mc.customer": customer
    }

    # Add attrs for uptime calculation
    container.attrs = {"State": {}}
    if started_at:
        container.attrs["State"]["StartedAt"] = started_at

    return container


class TestListEmpty:
    """Test list() with no containers."""

    def test_empty_list_returns_empty_array(
        self,
        container_manager: ContainerManager,
        mock_podman_client: MagicMock,
        mock_state_db: MagicMock
    ) -> None:
        """Empty container list returns [] without errors."""
        # Mock empty Podman list
        mock_podman_client.client.containers.list.return_value = []

        # Call list
        result = container_manager.list()

        # Verify empty list returned
        assert result == []

        # Verify reconcile called (containers.list called twice: once in reconcile, once in list)
        assert mock_podman_client.client.containers.list.call_count == 2
        mock_state_db.reconcile.assert_called_once_with(set())


class TestListRunningContainers:
    """Test list() with running containers."""

    def test_running_container_includes_uptime(
        self,
        container_manager: ContainerManager,
        mock_podman_client: MagicMock,
        mock_state_db: MagicMock
    ) -> None:
        """Running container shows status and uptime."""
        from datetime import timedelta
        # Create mock running container
        now = datetime.now(timezone.utc)
        started = now - timedelta(hours=2, minutes=34)  # 2h 34m ago
        started_iso = started.isoformat().replace('+00:00', 'Z')

        container = create_mock_container(
            container_id="abc123def456",
            short_id="abc123",
            case_number="12345678",
            customer="Acme Corp",
            status="running",
            started_at=started_iso
        )

        mock_podman_client.client.containers.list.return_value = [container]

        # Mock state database metadata
        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123def456",
            workspace_path="/home/user/mc/workspaces/12345678",
            created_at=int(started.timestamp()),
            updated_at=int(now.timestamp())
        )
        mock_state_db.get_container.return_value = metadata

        # Call list
        result = container_manager.list()

        # Verify result
        assert len(result) == 1
        assert result[0]["case_number"] == "12345678"
        assert result[0]["status"] == "running"
        assert result[0]["customer"] == "Acme Corp"
        assert result[0]["container_id"] == "abc123"
        assert result[0]["workspace_path"] == "/home/user/mc/workspaces/12345678"
        assert result[0]["uptime"]  # Should have uptime for running container
        assert "h" in result[0]["uptime"]  # Should be in hours format

    def test_uptime_calculation_seconds(
        self,
        container_manager: ContainerManager
    ) -> None:
        """Uptime less than 1 minute shows seconds."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        started = now - timedelta(seconds=45)
        started_iso = started.isoformat().replace('+00:00', 'Z')

        uptime = container_manager._calculate_uptime(started_iso)

        assert "s" in uptime
        assert "m" not in uptime
        assert "h" not in uptime

    def test_uptime_calculation_minutes(
        self,
        container_manager: ContainerManager
    ) -> None:
        """Uptime less than 1 hour shows minutes and seconds."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        started = now - timedelta(minutes=34, seconds=12)
        started_iso = started.isoformat().replace('+00:00', 'Z')

        uptime = container_manager._calculate_uptime(started_iso)

        assert "m" in uptime
        assert "s" in uptime
        assert "h" not in uptime
        assert "d" not in uptime

    def test_uptime_calculation_hours(
        self,
        container_manager: ContainerManager
    ) -> None:
        """Uptime less than 1 day shows hours and minutes."""
        now = datetime.now(timezone.utc)
        started = now.replace(hour=now.hour - 5 if now.hour >= 5 else now.hour + 19)
        started_iso = started.isoformat().replace('+00:00', 'Z')

        uptime = container_manager._calculate_uptime(started_iso)

        assert "h" in uptime
        assert "m" in uptime
        assert "d" not in uptime

    def test_uptime_calculation_days(
        self,
        container_manager: ContainerManager
    ) -> None:
        """Uptime over 1 day shows days and hours."""
        now = datetime.now(timezone.utc)
        started = now.replace(day=now.day - 5 if now.day > 5 else 1)
        started_iso = started.isoformat().replace('+00:00', 'Z')

        uptime = container_manager._calculate_uptime(started_iso)

        assert "d" in uptime
        assert "h" in uptime


class TestListStoppedContainers:
    """Test list() with stopped containers."""

    def test_stopped_container_no_uptime(
        self,
        container_manager: ContainerManager,
        mock_podman_client: MagicMock,
        mock_state_db: MagicMock
    ) -> None:
        """Stopped container shows status without uptime."""
        # Create mock stopped container
        container = create_mock_container(
            container_id="def456ghi789",
            short_id="def456",
            case_number="87654321",
            customer="Widget Inc",
            status="stopped"
        )

        mock_podman_client.client.containers.list.return_value = [container]

        # Mock state database metadata
        metadata = ContainerMetadata(
            case_number="87654321",
            container_id="def456ghi789",
            workspace_path="/home/user/mc/workspaces/87654321",
            created_at=1706300000,
            updated_at=1706300100
        )
        mock_state_db.get_container.return_value = metadata

        # Call list
        result = container_manager.list()

        # Verify result
        assert len(result) == 1
        assert result[0]["case_number"] == "87654321"
        assert result[0]["status"] == "stopped"
        assert result[0]["customer"] == "Widget Inc"
        assert result[0]["uptime"] == ""  # No uptime for stopped container

    def test_exited_container_no_uptime(
        self,
        container_manager: ContainerManager,
        mock_podman_client: MagicMock,
        mock_state_db: MagicMock
    ) -> None:
        """Exited container shows status without uptime."""
        container = create_mock_container(
            container_id="ghi789jkl012",
            short_id="ghi789",
            case_number="11223344",
            customer="Test Co",
            status="exited"
        )

        mock_podman_client.client.containers.list.return_value = [container]

        metadata = ContainerMetadata(
            case_number="11223344",
            container_id="ghi789jkl012",
            workspace_path="/home/user/mc/workspaces/11223344",
            created_at=1706300000,
            updated_at=1706300100
        )
        mock_state_db.get_container.return_value = metadata

        result = container_manager.list()

        assert len(result) == 1
        assert result[0]["status"] == "exited"
        assert result[0]["uptime"] == ""


class TestListMultipleContainers:
    """Test list() with multiple containers."""

    def test_multiple_containers_sorted_by_created_at(
        self,
        container_manager: ContainerManager,
        mock_podman_client: MagicMock,
        mock_state_db: MagicMock
    ) -> None:
        """Multiple containers sorted by created_at (newest first)."""
        # Create mock containers
        container1 = create_mock_container(
            container_id="aaa111",
            short_id="aaa111",
            case_number="11111111",
            customer="First Corp",
            status="running"
        )

        container2 = create_mock_container(
            container_id="bbb222",
            short_id="bbb222",
            case_number="22222222",
            customer="Second Corp",
            status="stopped"
        )

        container3 = create_mock_container(
            container_id="ccc333",
            short_id="ccc333",
            case_number="33333333",
            customer="Third Corp",
            status="running"
        )

        mock_podman_client.client.containers.list.return_value = [
            container1, container2, container3
        ]

        # Mock state database metadata (different timestamps)
        def get_container_side_effect(case_number: str) -> ContainerMetadata:
            metadata_map = {
                "11111111": ContainerMetadata(
                    case_number="11111111",
                    container_id="aaa111",
                    workspace_path="/home/user/mc/workspaces/11111111",
                    created_at=1706300000,  # Oldest
                    updated_at=1706300000
                ),
                "22222222": ContainerMetadata(
                    case_number="22222222",
                    container_id="bbb222",
                    workspace_path="/home/user/mc/workspaces/22222222",
                    created_at=1706300200,  # Middle
                    updated_at=1706300200
                ),
                "33333333": ContainerMetadata(
                    case_number="33333333",
                    container_id="ccc333",
                    workspace_path="/home/user/mc/workspaces/33333333",
                    created_at=1706300400,  # Newest
                    updated_at=1706300400
                )
            }
            return metadata_map[case_number]

        mock_state_db.get_container.side_effect = get_container_side_effect

        # Call list
        result = container_manager.list()

        # Verify sorting (newest first)
        assert len(result) == 3
        assert result[0]["case_number"] == "33333333"  # Newest
        assert result[1]["case_number"] == "22222222"  # Middle
        assert result[2]["case_number"] == "11111111"  # Oldest


class TestListMetadataEnrichment:
    """Test list() metadata enrichment from state database."""

    def test_workspace_path_from_state(
        self,
        container_manager: ContainerManager,
        mock_podman_client: MagicMock,
        mock_state_db: MagicMock
    ) -> None:
        """Workspace path from state database included in result."""
        container = create_mock_container(
            container_id="xyz789",
            short_id="xyz789",
            case_number="99887766",
            customer="Path Corp",
            status="running"
        )

        mock_podman_client.client.containers.list.return_value = [container]

        metadata = ContainerMetadata(
            case_number="99887766",
            container_id="xyz789",
            workspace_path="/custom/workspace/path/99887766",
            created_at=1706300000,
            updated_at=1706300100
        )
        mock_state_db.get_container.return_value = metadata

        result = container_manager.list()

        assert result[0]["workspace_path"] == "/custom/workspace/path/99887766"

    def test_missing_metadata_shows_na(
        self,
        container_manager: ContainerManager,
        mock_podman_client: MagicMock,
        mock_state_db: MagicMock
    ) -> None:
        """Container not in state database shows N/A for workspace path."""
        container = create_mock_container(
            container_id="missing123",
            short_id="missing",
            case_number="00000000",
            customer="Missing Corp",
            status="running"
        )

        mock_podman_client.client.containers.list.return_value = [container]

        # No metadata in state database
        mock_state_db.get_container.return_value = None

        result = container_manager.list()

        assert result[0]["workspace_path"] == "N/A"
        assert result[0]["created_at"] == "Unknown"


class TestListReconciliation:
    """Test list() reconciliation behavior."""

    def test_reconcile_called_before_listing(
        self,
        container_manager: ContainerManager,
        mock_podman_client: MagicMock,
        mock_state_db: MagicMock
    ) -> None:
        """Reconcile called before listing containers."""
        # Setup
        container = create_mock_container(
            container_id="reconcile123",
            short_id="reconcile",
            case_number="55555555",
            customer="Reconcile Corp",
            status="running"
        )

        mock_podman_client.client.containers.list.return_value = [container]

        metadata = ContainerMetadata(
            case_number="55555555",
            container_id="reconcile123",
            workspace_path="/home/user/mc/workspaces/55555555",
            created_at=1706300000,
            updated_at=1706300100
        )
        mock_state_db.get_container.return_value = metadata

        # Call list
        container_manager.list()

        # Verify reconcile was called
        mock_state_db.reconcile.assert_called_once()

        # Verify reconcile called with correct container IDs
        call_args = mock_state_db.reconcile.call_args[0][0]
        assert "reconcile123" in call_args

    def test_containers_list_called_with_correct_filters(
        self,
        container_manager: ContainerManager,
        mock_podman_client: MagicMock
    ) -> None:
        """containers.list() called with all=True and mc.managed=true filter."""
        mock_podman_client.client.containers.list.return_value = []

        container_manager.list()

        mock_podman_client.client.containers.list.assert_called_with(
            all=True,
            filters={"label": "mc.managed=true"}
        )
