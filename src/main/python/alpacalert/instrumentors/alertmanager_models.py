"""Models for AlertManager"""
# pylint: disable=C0115

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel
from typing_extensions import TypedDict


class Annotations(TypedDict):
	__orgId__: str


class Labels(TypedDict):
	__alert_rule_uid__: str
	alertname: str
	grafana_folder: str
	rulename: str
	datasource_uid: Optional[str]
	ref_id: Optional[str]


class Receiver(BaseModel):
	active: Optional[Any] = None
	integrations: Optional[Any] = None
	name: str


class State(str, Enum):
	unprocessed = "unprocessed"
	active = "active"
	suppressed = "suppressed"


class Status(BaseModel):
	inhibitedBy: List[str]
	silencedBy: List[str]
	state: State


class Alert(BaseModel):
	annotations: Annotations
	endsAt: datetime
	fingerprint: str
	receivers: List[Receiver]
	startsAt: datetime
	status: Status
	updatedAt: datetime
	generatorURL: str
	labels: Labels


class AlertGroupLabels(TypedDict):
	alertname: str
	grafana_folder: str


class AlertGroup(BaseModel):
	alerts: List[Alert]
	labels: AlertGroupLabels
	receiver: Receiver
