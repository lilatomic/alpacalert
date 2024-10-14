"""Models for Prometheus alerts"""
# pylint: disable=C0115

from datetime import datetime
from enum import Enum
from typing import List, Optional
from typing_extensions import TypedDict

from pydantic import BaseModel


class State(str, Enum):
	normal = "Normal"
	alerting = "Alerting"
	pending = "Pending"
	nodata = "NoData"
	error = "Error"


class Labels(TypedDict):
	alertname: str
	grafana_folder: str
	__name__: Optional[str]


class Annotations(TypedDict):
	pass


class Alert(BaseModel):
	labels: Labels
	annotations: Annotations
	state: State
	activeAt: datetime
	value: str


class Data(BaseModel):
	alerts: List[Alert]


class PrometheusResponse(BaseModel):
	status: str
	data: Data
