"""OpenTelemetry metrics setup. App-agnostic: the app binds its own instruments in `metrics.py`."""

from dataclasses import dataclass

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import Histogram, MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource

# Millisecond buckets for request and operation durations, 5 ms to 10 s.
DURATION_BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)


@dataclass(frozen=True)
class MetricsConfig:
    service_name: str
    environment: str
    # Base URL of an OTLP/HTTP collector. None keeps metrics in-process only.
    otlp_endpoint: str | None = None
    export_interval_seconds: float = 60


def make_meter_provider(
    config: MetricsConfig, *, readers: tuple[MetricReader, ...] = ()
) -> MeterProvider:
    """A meter provider exporting to the configured collector, if any, plus `readers`."""
    all_readers = list(readers)
    if config.otlp_endpoint:
        exporter = OTLPMetricExporter(endpoint=f"{config.otlp_endpoint.rstrip('/')}/v1/metrics")
        all_readers.append(
            PeriodicExportingMetricReader(
                exporter, export_interval_millis=config.export_interval_seconds * 1000
            )
        )
    return MeterProvider(
        resource=Resource.create(
            {"service.name": config.service_name, "deployment.environment": config.environment}
        ),
        metric_readers=all_readers,
        views=[
            View(
                instrument_type=Histogram,
                instrument_name="*duration*",
                aggregation=ExplicitBucketHistogramAggregation(DURATION_BUCKETS_MS),
            )
        ],
    )
