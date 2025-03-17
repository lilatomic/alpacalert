"""Instrument Grafana"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import ClassVar, Iterable, Protocol, Sequence, Type, TypeVar

import requests
from cachetools import TTLCache, cached

from alpacalert.generic import status_all
from alpacalert.instrumentor import Instrumentor, InstrumentorError, InstrumentorRegistry, Kind
from alpacalert.instrumentors import grafana_models as m
from alpacalert.models import Log, Scanner, Sensor, Severity, State, Status, System, flatten


class HasName(Protocol):
	"""Objects that have a name"""
	name: str


T = TypeVar('T', bound=HasName)


@dataclass(frozen=True)
class GrafanaObjRef:
	"""A reference to an object in Grafana"""

	name: str
	p: dict[str, str] = field(default_factory=dict)


# org: int | str # TODO: add support for organisations


@dataclass
class GrafanaApi:
	"""Interact with Grafana"""

	base_url: str
	session: requests.Session

	def call(self, req: requests.Request):
		"""Send a request"""
		return self.session.send(self.session.prepare_request(req))

	@cached(cache=TTLCache(maxsize=1, ttl=60), key=lambda s: None)
	def request_alertgroups(self) -> list[m.Group]:
		res = self.call(requests.Request("GET", self.base_url + "/api/prometheus/grafana/api/v1/rules"))
		if not res.ok:
			raise InstrumentorError(res)

		return m.GrafanaAlertsResponse.model_validate_json(res.content).data.groups

	def index_alertgroups(self, groups: list[m.Group]) -> dict[str, dict[str, tuple[m.Group, m.Rule]]]:
		"""Index rules by groups by their names"""
		return {e.name: {f.name: (e, f) for f in e.rules} for e in groups}

	def by_name(self, obj: Iterable[T]) -> dict[str, T]:
		"""Index a collection by name"""
		return {e.name: e for e in obj}

	def get_folder(self, folder: str) -> list[m.Group]:
		return [e for e in (self.request_alertgroups()) if e.file == folder]

	def get_folders(self) -> set[str]:
		"""Get the names of all folders"""
		return {e.file for e in self.request_alertgroups()}

	def get_group(self, group: str) -> m.Group:
		"""Get a single Alert group"""
		group_names = self.by_name(self.request_alertgroups())

		if group not in group_names:
			raise InstrumentorError(f"alert group not found {group=}")
		return group_names[group]

	def get_rule(self, group: str, name: str) -> m.Rule:
		"""Get an Alert rule"""
		group_obj = self.get_group(group)
		rules_by_name = self.by_name(group_obj.rules)

		if name not in rules_by_name:
			raise InstrumentorError(f"rule not found {group=}, {name=}")
		return rules_by_name[name]


class ScannerGrafanaType(Scanner, ABC):
	"""Parent for grafana scanners"""
	kind: ClassVar[Kind]


@dataclass
class InstrumentorGrafanaApi(Instrumentor, ABC):
	"""Instrument a whole Grafana instance"""
	api: GrafanaApi

	sensor_class: ClassVar[Type[ScannerGrafanaType]]

	def registrations(self) -> Iterable[tuple[Kind, InstrumentorGrafanaApi]]:
		return [(self.sensor_class.kind, self)]

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		return [self.sensor_class(**kwargs)]


@dataclass
class SensorAlert(Sensor, ScannerGrafanaType):
	"""Sensor for a Grafana alert"""

	alert: m.Alert
	state_when_pending: State = State.PASSING

	kind: ClassVar[Kind] = Kind("grafana.org/alerts", "alert")

	@property
	def name(self) -> str:
		"""Name"""
		return self.alert.name()

	def status(self) -> Status:
		match self.alert.state:
			case m.AlertState.normal:
				state = State.PASSING
			case m.AlertState.alerting | m.AlertState.alerting_nodata | m.AlertState.alerting_error:
				state = State.FAILING
			case m.AlertState.error | m.AlertState.normal_error:
				state = State.FAILING
			case m.AlertState.pending:
				state = self.state_when_pending
			case m.AlertState.nodata:
				state = State.UNKNOWN

		match state:
			case State.PASSING:
				severity = Severity.INFO
			case State.FAILING:
				severity = Severity.ERROR
			case State.UNKNOWN:
				severity = Severity.WARN

		return Status(state=state, messages=[Log(message=self.alert.state.value, severity=severity)])

	def children(self) -> Sequence[Scanner]:
		return []


@dataclass
class InstrumentorAlert(InstrumentorGrafanaApi):
	"""Instrument a Grafana Alert"""
	sensor_class = SensorAlert


@dataclass
class ScannerRule(System, ScannerGrafanaType):
	"""Scanner for a Grafana Alert rule"""

	rule: m.Rule
	alerts: list[SensorAlert]
	state_when_pending: State = State.PASSING

	kind: ClassVar[Kind] = Kind("grafana.org/alerts", "alertrule")

	@property
	def name(self) -> str:
		"""Name"""
		return self.rule.name

	def status(self) -> Status:
		match self.rule.state:
			case m.RuleState.pending:
				state = self.state_when_pending
			case m.RuleState.firing:
				state = State.FAILING
			case m.RuleState.inactive:
				state = State.PASSING

		match state:
			case State.PASSING:
				severity = Severity.INFO
			case State.FAILING:
				severity = Severity.ERROR
			case State.UNKNOWN:
				severity = Severity.WARN

		return Status(state=state, messages=[Log(message=self.rule.state.value, severity=severity)])

	def children(self) -> Sequence[Scanner]:
		return self.alerts


@dataclass
class InstrumentorAlertRule(InstrumentorGrafanaApi):
	"""Instrument an Alert rule"""
	sensor_class = ScannerRule

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		rule_arg = kwargs["rule"]
		if isinstance(rule_arg, GrafanaObjRef):
			rule = self.api.get_rule(rule_arg.p["group"], rule_arg.name)
		elif isinstance(rule_arg, m.Rule):
			rule = rule_arg
		else:
			raise InstrumentorError(f"cannot instantiate ScannerRule for unknown type {type(rule_arg)}")
		return [ScannerRule(rule, flatten([registry.instrument(SensorAlert.kind, alert=e) for e in rule.alerts]))]


@dataclass
class ScannerGroup(System, ScannerGrafanaType):
	"""Scanner for a Grafana Alert group"""

	group: m.Group
	rules: list[ScannerRule]

	kind: ClassVar[Kind] = Kind("grafana.org/alerts", "group")

	@property
	def name(self) -> str:
		"""Name"""
		return self.group.name

	status = status_all

	def children(self) -> Sequence[Scanner]:
		return self.rules


@dataclass
class InstrumentorAlertRuleGroup(InstrumentorGrafanaApi):
	"""Instrument an Alert group"""
	sensor_class = ScannerGroup

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		group_arg = kwargs["group"]
		if isinstance(group_arg, GrafanaObjRef):
			group = self.api.get_group(group_arg.name)
		elif isinstance(group_arg, m.Group):
			group = group_arg
		else:
			raise InstrumentorError(f"cannot instantiate ScannerGroup for unknown type {type(group_arg)}")

		return [ScannerGroup(group, flatten(registry.instrument(ScannerRule.kind, rule=e) for e in group.rules))]


@dataclass
class ScannerFolder(System, ScannerGrafanaType):
	"""Grafana Alert Folders aren't returned by the endpoint in a structure. They must be assembled from the labels"""

	folder_name: str
	groups: list[ScannerGroup]

	kind: ClassVar[Kind] = Kind("grafana.org/alerts", "folder")

	@property
	def name(self) -> str:
		"""Name"""
		return self.folder_name

	status = status_all

	def children(self) -> Sequence[Scanner]:
		return self.groups


@dataclass
class InstrumentorAlertFolder(InstrumentorGrafanaApi):
	"""Instrument a Grafana Alert folder"""
	sensor_class = ScannerFolder

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		folder_name = kwargs["folder"]
		groups = self.api.get_folder(folder_name)

		return [ScannerFolder(folder_name, flatten(registry.instrument(ScannerGroup.kind, group=GrafanaObjRef(group.name)) for group in groups))]


@dataclass
class ScannerGrafana(System, ScannerGrafanaType):
	"""Scanner for a Grafana instance"""

	name: str
	groups: list[ScannerGroup]

	kind: ClassVar[Kind] = Kind("grafana.org/alerts", "grafana")

	status = status_all

	def children(self) -> Sequence[Scanner]:
		return self.groups


@dataclass
class InstrumentorGrafana(InstrumentorGrafanaApi):
	"""Instrument a Grafana instance"""
	sensor_class = ScannerGrafana

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		name = kwargs.get("name", "Grafana")

		folders = self.api.get_folders()
		return [ScannerGrafana(name, flatten(registry.instrument(ScannerFolder.kind, folder=e) for e in folders))]


class RegistryGrafana(InstrumentorRegistry):
	"""Registry for all Grafana Instrumentors"""

	def __init__(self, grafana: GrafanaApi, instrumentors: InstrumentorRegistry.Registry | None = None):
		super().__init__(instrumentors)
		self.grafana = grafana

		grafana_instrumentors: Sequence[Type[InstrumentorGrafanaApi]] = [
			InstrumentorAlert,
			InstrumentorAlertRule,
			InstrumentorAlertRuleGroup,
			InstrumentorAlertFolder,
			InstrumentorGrafana,
		]
		for cls in grafana_instrumentors:
			instrumentor = cls(api=grafana)
			for kind, instrumentor in instrumentor.registrations():
				self.register(kind, instrumentor)
