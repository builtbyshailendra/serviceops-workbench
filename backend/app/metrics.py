"""Prometheus metrics, served at /metrics.

Two kinds:
- Traffic: calls by method, route and status, and how long they took. The route
  is the pattern, such as /api/requests/{request_id}, not the real path, so each
  request id doesn't become a separate time series.
- Work waiting: service requests by status, counted in the database when
  Prometheus asks. Every copy of the backend reports the same numbers, so a
  dashboard should take the max() across copies, not the sum().
"""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Iterator

from prometheus_client import REGISTRY, Counter, Histogram
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.exposition import choose_encoder
from prometheus_client.registry import Collector
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import Response

from app.db import SessionLocal
from app.models import STATUSES, ServiceRequest

HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP requests handled, by route and status", ["method", "route", "status"]
)
HTTP_DURATION = Histogram(
    "http_request_duration_seconds", "Time taken to handle an HTTP request", ["method", "route"]
)


def _requests_family() -> GaugeMetricFamily:
    return GaugeMetricFamily("serviceops_requests", "Service requests by status", labels=["status"])


class RequestsByStatus(Collector):
    def describe(self) -> Iterator[GaugeMetricFamily]:
        # Lets the registry learn the name without querying the database.
        yield _requests_family()

    def collect(self) -> Iterator[GaugeMetricFamily]:
        try:
            with SessionLocal() as session:
                query = select(ServiceRequest.status, func.count()).group_by(ServiceRequest.status)
                counts = dict(session.execute(query).all())
        except SQLAlchemyError:
            return  # Without the database there are no numbers, but the rest still works.
        family = _requests_family()
        for status in STATUSES:
            family.add_metric([status], counts.get(status, 0))
        yield family


REGISTRY.register(RequestsByStatus())


async def record(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """HTTP middleware: count every call and time it."""
    started = time.perf_counter()
    status = 500  # if the handler raises, this is what the caller gets
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # The router stores the matched route on the scope. No match means a 404.
        route = getattr(request.scope.get("route"), "path", "unmatched")
        if route != "/metrics":
            HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
            HTTP_DURATION.labels(request.method, route).observe(time.perf_counter() - started)


def endpoint(request: Request) -> Response:
    # Answer in the format the caller asks for: OpenMetrics for Prometheus,
    # plain text for curl.
    encode, content_type = choose_encoder(request.headers.get("accept", ""))
    return Response(encode(REGISTRY), media_type=content_type)
