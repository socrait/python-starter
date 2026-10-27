import pytest
from opentelemetry.sdk.metrics.export import (
    DataPointT,
    HistogramDataPoint,
    InMemoryMetricReader,
    NumberDataPoint,
)

from starter_app.config import Settings
from starter_app.libs.metrics import make_meter_provider
from starter_app.metrics import AppMetrics, make_metrics_config


@pytest.fixture
def metrics_reader() -> InMemoryMetricReader:
    return InMemoryMetricReader()


@pytest.fixture
def app_metrics(settings: Settings, metrics_reader: InMemoryMetricReader) -> AppMetrics:
    provider = make_meter_provider(make_metrics_config(settings), readers=(metrics_reader,))
    return AppMetrics(provider.get_meter("test"))


def _points(reader: InMemoryMetricReader, name: str) -> list[DataPointT]:
    data = reader.get_metrics_data()
    if data is None:
        return []
    return [
        point
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
        if metric.name == name
        for point in metric.data.data_points
    ]


def counter_points(reader: InMemoryMetricReader, name: str) -> list[NumberDataPoint]:
    return [p for p in _points(reader, name) if isinstance(p, NumberDataPoint)]


def histogram_points(reader: InMemoryMetricReader, name: str) -> list[HistogramDataPoint]:
    return [p for p in _points(reader, name) if isinstance(p, HistogramDataPoint)]
