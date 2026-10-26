"""OpenTelemetry metrics setup. App-agnostic: the app binds its own instruments in `metrics.py`."""

import os
from dataclasses import dataclass

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

# The exporter reads these (and OTEL_EXPORTER_OTLP_HEADERS, ..._TIMEOUT, ...) itself.
OTLP_ENDPOINT_VARIABLES = ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")


@dataclass(frozen=True)
class MetricsConfig:
    service_name: str
    environment: str
    export_interval_seconds: float = 60


def make_meter_provider(
    config: MetricsConfig, *, readers: tuple[MetricReader, ...] = ()
) -> MeterProvider:
    """A meter provider with `readers`, exporting over OTLP/HTTP when an endpoint is set.

    Export follows the standard `OTEL_EXPORTER_OTLP_*` environment variables, so
    collectors and platforms configure it the way they configure any OpenTelemetry SDK.
    Without an endpoint, measurements stay in-process and are discarded.
    """
    all_readers = list(readers)
    if any(os.environ.get(name) for name in OTLP_ENDPOINT_VARIABLES):
        all_readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(),
                export_interval_millis=config.export_interval_seconds * 1000,
            )
        )
    return MeterProvider(
        resource=Resource.create(
            {
                "service.name": config.service_name,
                "deployment.environment.name": config.environment,
            }
        ),
        metric_readers=all_readers,
    )
