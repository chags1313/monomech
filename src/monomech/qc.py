from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class QCReport:
    dataframe: pd.DataFrame

    def summary(self) -> pd.DataFrame:
        return self.dataframe.copy()

    def to_dataframe(self) -> pd.DataFrame:
        return self.dataframe.copy()
