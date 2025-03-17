"""Models for AlertManager"""
# pylint: disable=C0115

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel
from typing_extensions import NotRequired, TypedDict


# Define Enums
class AlertState(str, Enum):
	normal = "Normal"
	normal_error = "Normal (Error)"
	alerting = "Alerting"
	alerting_nodata = "Alerting (NoData)"
	alerting_error = "Alerting (Error)"
	pending = "Pending"
	pending_nodata = "Pending (NoData)"
	nodata = "NoData"
	error = "Error"
	inactive = "inactive"


class HealthEnum(str, Enum):
	ok = "ok"
	error = "error"
	unknown = "unknown"
	nodata = "nodata"


# Define TypedDicts
class Labels(TypedDict):
	alertname: str
	grafana_folder: str
	__name__: NotRequired[str]


class Annotations(TypedDict):
	pass


class Alert(BaseModel):
	labels: Labels
	annotations: Annotations
	state: AlertState
	activeAt: datetime
	value: str

	def name(self):
		"""Resolve the name of this alert from its multiple models"""
		if "__name__" in self.labels:
			return self.labels["__name__"]
		elif "alertname" in self.labels:
			return self.labels["alertname"]
		else:
			return "Alert"


class Totals(BaseModel):
	normal: int = 0
	error: int = 0
	nodata: int = 0
	alerting: int = 0


class RuleState(str, Enum):
	"""Rule states are prometheus states"""

	inactive = "inactive"
	pending = "pending"
	firing = "firing"


class Rule(BaseModel):
	state: RuleState
	name: str
	query: str
	duration: Optional[int] = 0
	alerts: List[Alert]
	totals: Totals
	totalsFiltered: Totals
	health: HealthEnum
	type: str
	lastEvaluation: datetime
	evaluationTime: float


class Group(BaseModel):
	name: str
	file: str
	rules: List[Rule]
	totals: Dict[str, int]
	interval: int
	lastEvaluation: datetime
	evaluationTime: float


class Data(BaseModel):
	groups: List[Group]
	totals: Dict[str, int]


class GrafanaAlertsResponse(BaseModel):
	status: str
	data: Data
