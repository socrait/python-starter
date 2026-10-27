from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider

from starter_app.config import Settings
from starter_app.libs.metrics import MetricsConfig, make_meter_provider


class AppMetrics:
    """The app's business instruments, one method per event. HTTP metrics come from FastAPI.

    Every attribute is low-cardinality: no ids, emails, or free text. Each distinct
    combination of attribute values is a separate time series, exported every interval.
    """

    def __init__(self, meter: Meter):
        self._projects_created = meter.create_counter(
            "app.projects.created", unit="{project}", description="Projects created"
        )
        self._tasks_completed = meter.create_counter(
            "app.tasks.completed", unit="{task}", description="Tasks marked done"
        )

    def record_project_created(self) -> None:
        self._projects_created.add(1)

    def record_task_completed(self) -> None:
        self._tasks_completed.add(1)


def make_metrics_config(settings: Settings) -> MetricsConfig:
    return MetricsConfig(service_name=settings.app_name, environment=settings.environment.value)


def make_meter_provider_from_settings(settings: Settings) -> MeterProvider:
    """Exports when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; otherwise measurements are discarded.

    Call `shutdown()` on exit so the last interval's measurements are flushed.
    """
    return make_meter_provider(make_metrics_config(settings))
