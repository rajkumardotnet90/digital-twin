import pandas as pd

from core.simulation import Scenario, history_series, run_simulation
from ui import charts


def test_chart_builders_return_expected_traces(twin_enet):
    res = run_simulation(twin_enet, Scenario("elasticnet", (1, 2, 3), 6, (("avg_traffic_volume", -30.0),)))
    hist = history_series(twin_enet, [1, 2, 3])
    fig = charts.forecast_chart(hist, res.city_series(), pd.Timestamp("2024-06-01"), "t")
    assert [t.name for t in fig.data] == ["Observed AQI", "Forecast - no change", "Forecast - scenario"]
    assert len(charts.zone_bar_chart(res.summary).data) == 2
    cmp = charts.compare_chart(hist, [("base", res.city_series(), True), ("run", res.city_series(), False)])
    assert len(cmp.data) == 3
