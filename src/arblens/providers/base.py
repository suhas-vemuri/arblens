from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from arblens.market import UnderlyingQuote


class OptionChainProvider(ABC):
    """Interface implemented by option-market data providers."""

    @property
    def environment(self) -> str:
        """Describe the provider environment."""
        return "unknown"

    def get_underlying_quote(
        self,
        symbol: str,
    ) -> UnderlyingQuote:
        """Return the underlying stock or ETF quote.

        Providers that do not support underlying quotes may leave
        this method unimplemented.
        """
        raise NotImplementedError("provider does not support underlying quotes")

    @abstractmethod
    def get_expirations(
        self,
        symbol: str,
    ) -> list[str]:
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
