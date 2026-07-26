from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class OptionChainProvider(ABC):
    @abstractmethod
    def get_chain(self, symbol: str, expiration: str) -> pd.DataFrame:
        """Return one normalized option chain."""
        raise NotImplementedError
