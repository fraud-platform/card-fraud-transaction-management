"""Base classes for repository layer."""

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class BaseCursor:
    """Base cursor for keyset pagination.

    Subclasses should define the timestamp field name.
    """

    timestamp: datetime
    id: UUID

    def encode(self) -> str:
        """Encode cursor to base64 string."""
        data = f"{self.timestamp.isoformat()}|{self.id}"
        return base64.urlsafe_b64encode(data.encode()).decode()

    @classmethod
    def decode(cls, cursor: str) -> BaseCursor | None:
        """Decode cursor from base64 string. Returns None for invalid cursors."""
        try:
            data = base64.urlsafe_b64decode(cursor.encode()).decode()
            parts = data.split("|")
            if len(parts) != 2:
                return None
            return cls(
                timestamp=datetime.fromisoformat(parts[0]),
                id=UUID(parts[1]),
            )
        except (ValueError, binascii.Error):
            return None
