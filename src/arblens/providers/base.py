from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class OptionChainProvider(ABC):
    """Interface implemented by option-market data providers."""

    @property
    def environment(self) -> str:
        """Describe the provider environment."""
        return "unknown"

    @abstractmethod
    def get_expirations(self, symbol: str) -> list[str]:
        """Return the available option expirations for a symbol."""
        raise NotImplementedError

    @abstractmethod
    def get_chain(
        self,
        symbol: str,
        expiration: str,
    ) -> pd.DataFrame:
        """Return one normalized option chain."""
        raise NotImplementedError
