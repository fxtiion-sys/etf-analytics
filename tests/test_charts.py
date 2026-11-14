"""Smoke test: every chart is drawn from small fake data without errors or network access."""
import numpy as np
import pandas as pd

from etf_analytics import charts


def test_make_all_charts_writes_png_files(tmp_path):
    idx = pd.bdate_range("2021-12-01", "2023-03-01")
    rng = np.random.default_rng(0)
    data = {t: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx)))) for t in charts.ETFS}
    data["CAD=X"] = 1.3 * np.exp(np.cumsum(rng.normal(0, 0.003, len(idx))))
    paths = charts.make_all_charts(pd.DataFrame(data, index=idx), out_dir=tmp_path)

    assert len(paths) == 6
    for path in paths.values():
        assert path.exists() and path.stat().st_size > 0