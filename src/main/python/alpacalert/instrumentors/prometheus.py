import datetime
from dataclasses import dataclass

import requests

import alpacalert.instrumentors.prometheus_models as m
from alpacalert.instrumentor import InstrumentorError


@dataclass
class PrometheusApi:
	"""Interface for Prometheus API"""

	base_url: str
	session: requests.Session

	def call(self, req: requests.Request) -> requests.Response:
		"""Send a request to the Prometheus API"""
		return self.session.send(self.session.prepare_request(req))

	def query_instant(self, query: str, time: datetime.datetime, timeout: int = 30, limit=0) -> m.PromResponse[m.DataInstant[m.InstantVector]]:
		"""Make an Instant query"""
		res = self.call(requests.Request("POST", self.base_url + "/api/v1/query", params={"query": query, "time": time.isoformat(), "limit": limit, "timeout": timeout}))
		if not res.ok:
			raise InstrumentorError(res)

		return m.PromResponse[m.DataInstant[m.InstantVector]].model_validate_json(res.content)
