import datetime
from dataclasses import dataclass
from typing import Any

import requests
from cachetools import FIFOCache, cached

import alpacalert.instrumentors.prometheus_models as m
from alpacalert.generic import SensorConstant, status_all
from alpacalert.instrumentor import Instrumentor, InstrumentorError, InstrumentorRegistry, Kind, Registrations
from alpacalert.instrumentors.k8s import k8skind
from alpacalert.models import Log, Scanner, Severity, State, Status, System


@dataclass
class PrometheusApi:
	"""Interface for Prometheus API"""

	base_url: str
	session: requests.Session

	def call(self, req: requests.Request) -> requests.Response:
		"""Send a request to the Prometheus API"""
		return self.session.send(self.session.prepare_request(req))

	def query_instant(self, query: str, time: datetime.datetime | None = None, timeout: int = 30, limit=0) -> m.PromResponse[m.DataInstant[m.InstantVectorValue]]:
		"""Make an Instant query"""
		res = self.call(requests.Request(
			"POST",
			self.base_url + "/api/v1/query",
			params={"query": query, "time": time.isoformat() if time else None, "limit": limit, "timeout": timeout}),
		)
		if not res.ok:
			raise InstrumentorError(res)

		return m.PromResponse[m.DataInstant[m.InstantVectorValue]].model_validate_json(res.content)


@dataclass
class PrometheusMultiplexer:
	"""Separate a prometheus query result into separate sensors"""

	api: PrometheusApi
	query: str
	groupby: tuple[str, ...] | None = None

	@cached(cache=FIFOCache(maxsize=7), key=lambda s, t: (s.query, t))
	def get(self, time: datetime.datetime | None = None):
		res = self.api.query_instant(self.query, time)

		o = {}
		for e in res.data.result:
			if self.groupby is not None:
				k = tuple(e.metric[v] for v in self.groupby)
			else:
				k = tuple(e.metric.values())
			v = e.value[1]
			o[k] = v

		return o

	def result(self, keyset: tuple[Any, ...], time: datetime.datetime | None = None):
		return self.get(time).get(keyset)


@dataclass
class SystemContainer(System):
	name: str
	cpu_utilisation: float | None
	mem_utilisation: float | None
	restarts: float | None

	def children(self):
		"""Instrument a container"""
		sensors = []

		if self.cpu_utilisation is not None:
			status = Status(
				state=State.FAILING if self.cpu_utilisation > 0.98 else State.PASSING,
				messages=[Log(message=f"ratio of request: {self.cpu_utilisation:.2f}", severity=Severity.INFO)],
			)
			sensors.append(SensorConstant(name="CPU utilisation", val=status))

		if self.mem_utilisation is not None:
			status = Status(
				state=State.FAILING if self.mem_utilisation > 0.98 else State.PASSING,
				messages=[Log(message=f"ratio of request: {self.mem_utilisation:.2f}", severity=Severity.INFO)],)
			sensors.append(SensorConstant(name="MEM utilisation", val=status))

		restarts = self.restarts if self.restarts is not None else 0
		status = Status(
			state=State.FAILING if restarts >= 1 else State.PASSING,
			messages=[Log(message=f"restarts: {restarts:.2f}", severity=Severity.INFO)],
		)
		sensors.append(SensorConstant(name="Restarts", val=status))

		return sensors

	status = status_all


time = None  # TODO: make this refresh


class PrometheusContainerInstrumentor(Instrumentor):
	def __init__(self, api: PrometheusApi):
		self.api = api

		self.q_cpu_usage = PrometheusMultiplexer(
			api,
			'(sum (rate (container_cpu_usage_seconds_total {} [5m])) by (container , pod, namespace ) / on (container , pod , namespace) ((kube_pod_container_resource_limits {resource="cpu"} >0)*300))',  # noqa: E501
			("container", "pod", "namespace"),
		)
		self.q_mem_usage = PrometheusMultiplexer(
			api,
			'(sum (rate (container_cpu_usage_seconds_total {} [5m])) by (container, pod, namespace) / on (container, pod, namespace) ((kube_pod_container_resource_limits {resource="cpu"} >0)*300))',  # noqa: E501
			("container", "pod", "namespace"),)
		self.q_restarts = PrometheusMultiplexer(
			api,
			'sum(increase(kube_pod_container_status_restarts_total[1h]) > 0) by (container, pod, namespace)',
			("container", "pod", "namespace"),
		)

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		return [self.instrument_container(kwargs["namespace"], kwargs["pod_name"], kwargs["container_status"])]

	def instrument_container(self, namespace, pod, container_status) -> Scanner:
		container = container_status.name
		cpu = self.q_cpu_usage.result((container, pod, namespace))
		mem = self.q_mem_usage.result((container, pod, namespace))
		restarts = self.q_restarts.result((container, pod, namespace))

		return SystemContainer(f"Metrics for {container}", cpu, mem, restarts)

	def registrations(self) -> Registrations:
		return [
			(k8skind("Pod#container"), self)
		]


class RegistryPrometheus(InstrumentorRegistry):
	"""Registry for all Prometheus Instrumentors"""

	def __init__(self, api: PrometheusApi, instrumentors: InstrumentorRegistry.Registry | None = None):
		super().__init__(instrumentors)
		self.api = api

		self.register(k8skind("Pod#container"), PrometheusContainerInstrumentor(api))
