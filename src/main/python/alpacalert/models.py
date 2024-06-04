"""Alpacalert models."""

from __future__ import annotations

import itertools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, TypeVar

from pydantic import BaseModel


class Severity(Enum):
	"""Severity of a Message, per OpenTelemetry log SeverityText and SeverityNumber."""

	TRACE = 1
	DEBUG = 5
	INFO = 9
	WARN = 13
	ERROR = 17
	FATAL = 21


class Log(BaseModel):
	"""A message to be passed as part of a Status"""

	message: str
	severity: Severity


class State(Enum):
	"""The state of a Scanner"""

	PASSING = "passing"
	FAILING = "failing"
	UNKNOWN = "unknown"

	def __and__(self, other: State) -> State:
		"""
		The least favourable state.

		PASSING < UNKNOWN < FAILING
		"""
		match self:
			case State.PASSING:
				return other
			case State.FAILING:
				return State.FAILING
			case State.UNKNOWN:
				match other:
					case State.PASSING:
						return State.UNKNOWN
					case State.FAILING:
						return State.FAILING
					case State.UNKNOWN:
						return State.UNKNOWN

	def __or__(self, other: State) -> State:
		"""
		The most favourable state.

		PASSING > UNKNOWN > FAILING
		"""
		match self:
			case State.PASSING:
				return State.PASSING
			case State.FAILING:
				return other
			case State.UNKNOWN:
				match other:
					case State.PASSING:
						return State.PASSING
					case State.FAILING:
						return State.UNKNOWN
					case State.UNKNOWN:
						return State.UNKNOWN

	@classmethod
	def from_bool(cls, up: bool | None) -> State:
		"""Convert a tri-state boolean into a State"""
		match up:
			case True:
				return State.PASSING
			case False:
				return State.FAILING
			case None:
				return State.UNKNOWN


class Status(BaseModel):
	"""Status of a Scanner"""

	state: State
	messages: list[Log] = []


class Scanner(ABC):
	"""Common interface for Sensors, Systems, and Services"""

	name: str

	@abstractmethod
	def status(self) -> Status:
		"""The status of this scanner"""

	@abstractmethod
	def children(self) -> list[Scanner]:
		"""Detailed statuses"""


class Sensor(Scanner, ABC):
	"""
	These reach out to the world and measure something.

	That could be the status of a running process, available disk space, or availability of a healthcheck endpoint; for example.
	"""


class System(Scanner, ABC):
	"""
	These compose Sensors and other Systems into logical units of infrastructure.
	Systems also make determinations about their health by using data from their Sensors.
	"""


class Service(Scanner, ABC):
	"""
	These are capabilities that your infrastructure provides.

	These might be:
	- customer-facing, like the actual application
	- internal-facing, like a message queue
	- parts of your development infrastructure, like the status of build servers
	"""


class Visualiser(ABC):
	"""Visualise a Service"""

	@abstractmethod
	def visualise(self, service: Service):
		"""Visualise a Service"""


def flatten(its: Iterable[Iterable]) -> list:
	return list(itertools.chain.from_iterable(its))


class Instrumentor:
	@dataclass(frozen=True)
	class Kind:
		namespace: str
		name: str

	Registrations = Iterable[tuple[Kind, type["Instrumentor"]]]

	@abstractmethod
	def registrations(self) -> Instrumentor.Registrations: ...

	@abstractmethod
	def instrument(self, registry: InstrumentorRegistry, kind: Instrumentor.Kind, *arg, **kwargs) -> list[Scanner]: ...


class InstrumentorRegistry:
	"""
	Instrument an external entity by generating Sensors, Systems, or Services.
	"""

	Registry = dict[Instrumentor.Kind, Instrumentor]

	def __init__(self, instrumentors: Registry | None = None):
		self.instrumentors: InstrumentorRegistry.Registry
		if instrumentors:
			self.instrumentors = instrumentors
		else:
			self.instrumentors = {}

	def instrument(self, kind: Instrumentor.Kind, *args, **kwargs) -> list[Scanner]:
		"""
		Instrument an external entity by generating Sensors, Systems, or Services.
		"""
		instrumentor = self.instrumentors.get(kind)
		if instrumentor:
			try:
				return instrumentor.instrument(self, kind, *args, **kwargs)
			except Exception as e:
				raise InstrumentorError(f"failed to instrument {kind=}") from e
		else:
			raise InstrumentorError(f"no provider {kind=}")

	def register(self, kind: Instrumentor.Kind, instrumentor: Instrumentor):
		self.instrumentors[kind] = instrumentor


class InstrumentorError(Exception):
	"""An error instrumenting an object"""
