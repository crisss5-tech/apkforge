from abc import ABC, abstractmethod

class BasePatcher(ABC):
    name = "base"

    def match(self, package: str) -> bool:
        return False

    @abstractmethod
    def patch(self, decoded_dir: str, package: str) -> int:
        """Return jumlah file yang berhasil dipatch."""
        ...