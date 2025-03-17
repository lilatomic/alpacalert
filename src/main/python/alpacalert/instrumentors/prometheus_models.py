"""Models for Prometheus alerts"""
# pylint: disable=C0115

from datetime import datetime
from enum import Enum, auto
from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel
from typing_extensions import TypedDict


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


T = TypeVar("T")


class PromResponse(BaseModel, Generic[T]):
	status: Literal["success"] | Literal["error"]
	data: T

	# Only set if status is "error". The data field may still hold additional data.
	errorType: Optional[str] = None
	error: Optional[str] = None

	# Only set if there were warnings while executing the request.
	# There will still be data in the data field.
	warnings: Optional[str] = None
	# Only set if there were info-level annotations while executing the request.
	infos: Optional[str] = None


class ResultType(str, Enum):
	matrix = auto()
	vector = auto()
	scalar = auto()
	string = auto()


class BoundaryRule(Enum):
	open_left = 0
	open_right = 1
	open_both = 2
	closed_both = 3


class Histogram(BaseModel):
	count: int
	sum: int
	buckets: list[tuple[BoundaryRule, float, float, int]]


class DataInstant(BaseModel, Generic[T]):
	resultType: ResultType
	result: list[T]


class InstantVectorValue(BaseModel):
	metric: dict[str, str]
	value: tuple[datetime, float]


class InstantVectorHistogram(BaseModel):
	metric: dict[str, str]
	histogram: Histogram


InstantVector = InstantVectorHistogram | InstantVectorValue
