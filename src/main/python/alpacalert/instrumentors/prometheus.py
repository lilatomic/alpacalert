import datetime
import functools
from dataclasses import dataclass
from typing import Any

import requests
from cachetools import cached, FIFOCache

import alpacalert.instrumentors.prometheus_models as m
from alpacalert.generic import SensorConstant, status_all
from alpacalert.instrumentor import InstrumentorError
from alpacalert.models import Log, Scanner, Severity, State, Status, System


@dataclass
class PrometheusApi:
	"""Interface for Prometheus API"""

	base_url: str
	session: requests.Session

	def call(self, req: requests.Request) -> requests.Response:
		"""Send a request to the Prometheus API"""
		return self.session.send(self.session.prepare_request(req))

	def query_instant(self, query: str, time: datetime.datetime = None, timeout: int = 30, limit=0) -> m.PromResponse[m.DataInstant[m.InstantVector]]:
		"""Make an Instant query"""
		res = self.call(requests.Request("POST", self.base_url + "/api/v1/query", params={"query": query, "time": time.isoformat() if time else None, "limit": limit, "timeout": timeout}))
		if not res.ok:
			raise InstrumentorError(res)

		return m.PromResponse[m.DataInstant[m.InstantVector]].model_validate_json(res.content)


@dataclass
class PrometheusMultiplexer:
	"""Separate a prometheus query result into separate sensors"""

	api: PrometheusApi
	query: str
	groupby: tuple[str, ...] | None = None

	@cached(cache=FIFOCache(maxsize=7), key=lambda s, t: t)
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
	cpu_utilisation: int | None
	mem_utilisation: int | None
	restarts: int | None

	def children(self):
		"""Instrument a container"""
		sensors = []

		if self.cpu_utilisation is not None:
			status = Status(state=State.FAILING if self.cpu_utilisation > 1 else State.PASSING, messages=[Log(message=f"ratio of request: {self.cpu_utilisation:2f}", severity=Severity.INFO)])
			sensors.append(SensorConstant(name="CPU utilisation", val=status))

		if self.mem_utilisation is not None:
			status = Status(state=State.FAILING if self.mem_utilisation > 1 else State.PASSING, messages=[Log(message=f"ratio of request: {self.mem_utilisation:2f}", severity=Severity.INFO)])
			sensors.append(SensorConstant(name="MEM utilisation", val=status))

		status = Status(state=State.FAILING if self.restarts is not None and self.restarts > 1 else State.PASSING, messages=[Log(message=f"restarts: {self.restarts}", severity=Severity.INFO)])
		sensors.append(SensorConstant(name="Restarts", val=status))

		return sensors

	status = status_all


time = None  # TODO: make this refresh


class PrometheusContainerInstrumentor:
	def __init__(self, api: PrometheusApi):
		self.api = api

		self.q_cpu_usage = PrometheusMultiplexer(api,
			'(sum (rate (container_cpu_usage_seconds_total {} [5m])) by (namespace , pod, container ) / on (container , pod , namespace) ((kube_pod_container_resource_limits {resource="cpu"} >0)*300))'
		)
		self.q_mem_usage = PrometheusMultiplexer(api, '(sum (rate (container_cpu_usage_seconds_total {} [5m])) by (container, pod, namespace) / on (container, pod, namespace) ((kube_pod_container_resource_limits {resource="cpu"} >0)*300))')
		self.q_restarts = PrometheusMultiplexer(api, 'sum(increase(kube_pod_container_status_restarts_total[1h]) > 0) by (container, pod, namespace)')

	def instrument(self, namespace, pod, container) -> list[Scanner]:
		cpu = self.q_cpu_usage.result((container, pod, namespace))
		mem = self.q_mem_usage.result((container, pod, namespace))
		restarts = self.q_restarts.result((container, pod, namespace))

		return [SystemContainer(container, cpu, mem, restarts)]
