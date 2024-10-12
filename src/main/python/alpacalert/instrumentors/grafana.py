from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Iterable, TypeVar

import requests
from cachetools import TTLCache, cached

from alpacalert.generic import status_all
from alpacalert.instrumentor import Instrumentor, InstrumentorError, InstrumentorRegistry, Kind, Registrations
from alpacalert.instrumentors import grafana_models as m
from alpacalert.models import Log, Scanner, Sensor, Severity, State, Status, System, flatten

T = TypeVar("T")


@dataclass(frozen=True)
class GrafanaObjRef:
	name: str
	p: dict[str, str] = field(default_factory=dict)


# org: int | str # TODO


@dataclass
class GrafanaApi:
	base_url: str
	session: requests.Session

	def call(self, req: requests.Request):
		return self.session.send(self.session.prepare_request(req))

	@cached(cache=TTLCache(maxsize=1, ttl=60), key=lambda s: None)
	def request_alertgroups(self) -> list[m.Group]:
		res = self.call(requests.Request("GET", self.base_url + "/api/prometheus/grafana/api/v1/rules"))
		if not res.ok:
			raise InstrumentorError(res)

		return m.GrafanaAlertsResponse.model_validate_json(res.content).data.groups

	def index_alertgroups(self, groups: list[m.Group]) -> dict[str, dict[str, tuple[m.Group, m.Rule]]]:
		return {e.name: {f.name: (e, f) for f in e.rules} for e in groups}

	def by_name(self, obj: Iterable[T]) -> dict[str, T]:
		return {e.name: e for e in obj}

	def get_folder(self, folder: str) -> list[m.Group]:
		return [e for e in (self.request_alertgroups()) if e.file == folder]

	def get_folders(self) -> set[str]:
		return {e.file for e in self.request_alertgroups()}

	def get_group(self, group: str) -> m.Group:
		group_names = self.by_name(self.request_alertgroups())

		if group not in group_names:
			raise InstrumentorError(f"alert group not found {group=}")
		return group_names[group]

	def get_rule(self, group: str, name: str) -> m.Rule:
		group = self.get_group(group)
		rules_by_name = self.by_name(group.rules)

		if name not in rules_by_name:
			raise InstrumentorError(f"rule not found {group=}, {name=}")
		return rules_by_name[name]


@dataclass
class SensorAlert(Sensor):
	"""Sensor for a Grafana alert"""

	alert: m.Alert
	state_when_pending: State = State.PASSING

	kind: ClassVar[Kind] = Kind("grafana.org/alerts", "alert")

	@property
	def name(self) -> str:
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

	def children(self) -> list[Scanner]:
		return []


@dataclass
class InstrumentorAlert(Instrumentor):
	api: GrafanaApi

	def registrations(self) -> Registrations:
		return [
			(SensorAlert.kind, self),
		]

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		return [SensorAlert(**kwargs)]


@dataclass
class ScannerRule(System):
	rule: m.Rule
	alerts: list[SensorAlert]
	state_when_pending: State = State.PASSING

	kind: ClassVar[Kind] = Kind("grafana.org/alerts", "alertrule")

	@property
	def name(self) -> str:
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

	def children(self) -> list[Scanner]:
		return self.alerts


@dataclass
class InstrumentorAlertRule(Instrumentor):
	api: GrafanaApi

	def registrations(self) -> Registrations:
		return [
			(ScannerRule.kind, self),
		]

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		rule = kwargs["rule"]
		if isinstance(rule, GrafanaObjRef):
			rule = self.api.get_rule(rule.p["group"], rule.name)
		elif isinstance(rule, m.Rule):
			rule = rule
		else:
			raise InstrumentorError(f"cannot instantiate ScannerRule for unknown type {type(rule)}")
		return [ScannerRule(rule, flatten([registry.instrument(SensorAlert.kind, alert=e) for e in rule.alerts]))]


@dataclass
class ScannerGroup(System):
	group: m.Group
	rules: list[ScannerRule]

	kind: ClassVar[Kind] = Kind("grafana.org/alerts", "group")

	@property
	def name(self) -> str:
		return self.group.name

	status = status_all

	def children(self) -> list[Scanner]:
		return self.rules


@dataclass
class InstrumentorAlertRuleGroup(Instrumentor):
	api: GrafanaApi

	def registrations(self) -> Registrations:
		return [
			(ScannerGroup.kind, self),
		]

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		group = kwargs["group"]
		if isinstance(group, GrafanaObjRef):
			group = self.api.get_group(group.name)
		elif isinstance(group, m.Group):
			group = group
		else:
			raise InstrumentorError(f"cannot instantiate ScannerGroup for unknown type {type(group)}")

		return [ScannerGroup(group, flatten(registry.instrument(ScannerRule.kind, rule=e) for e in group.rules))]


@dataclass
class ScannerFolder(System):
	"""Grafana Alert Folders aren't returned by the endpoint in a structure. They must be assembled from the labels"""

	folder_name: str
	groups: list[ScannerGroup]

	kind: ClassVar[Kind] = Kind("grafana.org/alerts", "folder")

	@property
	def name(self) -> str:
		return self.folder_name

	status = status_all

	def children(self) -> list[Scanner]:
		return self.groups


@dataclass
class InstrumentorAlertFolder(Instrumentor):
	api: GrafanaApi

	def registrations(self) -> Registrations:
		return [
			(ScannerFolder.kind, self),
		]

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		folder_name = kwargs["folder"]
		groups = self.api.get_folder(folder_name)

		return [ScannerFolder(folder_name, flatten(registry.instrument(ScannerGroup.kind, group=GrafanaObjRef(group.name)) for group in groups))]


@dataclass
class ScannerGrafana(System):
	name: str
	groups: list[ScannerGroup]

	kind: ClassVar[Kind] = Kind("grafana.org/alerts", "grafana")

	status = status_all

	def children(self) -> list[Scanner]:
		return self.groups


@dataclass
class InstrumentorGrafana(Instrumentor):
	api: GrafanaApi

	def registrations(self) -> Registrations:
		return [
			(ScannerGrafana.kind, self),
		]

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		name = kwargs.get("name", "Grafana")

		folders = self.api.get_folders()
		return [ScannerGrafana(name, flatten(registry.instrument(ScannerFolder.kind, folder=e) for e in folders))]


class RegistryGrafana(InstrumentorRegistry):
	def __init__(self, grafana: GrafanaApi, instrumentors: InstrumentorRegistry.Registry | None = None):
		super().__init__(instrumentors)
		self.grafana = grafana

		grafana_instrumentors = [
			InstrumentorAlert,
			InstrumentorAlertRule,
			InstrumentorAlertRuleGroup,
			InstrumentorAlertFolder,
			InstrumentorGrafana,
		]
		for cls in grafana_instrumentors:
			instrumentor = cls(grafana)
			for kind, instrumentor in instrumentor.registrations():
				self.register(kind, instrumentor)
