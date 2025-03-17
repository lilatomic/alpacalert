"""Instrumentors convert an external system into Sensors, Systems, and Services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import chain
from typing import Iterable

from alpacalert.generic import SystemAll
from alpacalert.models import Scanner


@dataclass(frozen=True)
class Kind:
	"""
	The kind of resource to instrument.

	Kinds have 2 components:
	- namespace: the project that this kind belongs to. For example, `kubernetes.io`
	- name: the name of this kind. For example, `StorageClass`
	"""

	namespace: str
	name: str


Registrations = Iterable[tuple[Kind, "Instrumentor"]]


class Instrumentor(ABC):
	"""
	Instrumentors convert an external system into Sensors, Systems, and Services.

	For example:
	- transforming Grafana dashboards into Services with alerts as their Sensors
	- creating a System for a virtual machine with Sensors checking for available memory, CPU, and disk space
	- transforming Kubernetes objects into Systems based on their dependent resources
	"""

	registry: InstrumentorRegistry

	@abstractmethod
	def registrations(self) -> Registrations:
		"""The Instrumentors that should be added for each Kind"""

	@abstractmethod
	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		"""Add scanners for an object"""


@dataclass
class InstrumentorComposite(Instrumentor):
	"""An instrumentor that contains other instrumentors"""
	registry: InstrumentorRegistry
	kind: Kind
	instrumentors: list[Instrumentor]

	def registrations(self) -> Registrations:
		return [(self.kind, self)]

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs):
		return [SystemAll(
			name=f"{kind.namespace}/{kind.name}", scanners=list(chain.from_iterable(instrumentor.instrument(registry, kind, **kwargs) for instrumentor in self.instrumentors))
		)]


class InstrumentorRegistry:
	"""
	Instrument an external entity by generating Sensors, Systems, or Services.
	"""

	Registry = dict[Kind, Instrumentor]

	def __init__(self, instrumentors: Registry | None = None):
		self.instrumentors: InstrumentorRegistry.Registry
		if instrumentors:
			self.instrumentors = instrumentors
		else:
			self.instrumentors = {}

	def instrument(self, kind: Kind, **kwargs) -> list[Scanner]:
		"""
		Instrument an external entity by generating Sensors, Systems, or Services.
		"""
		instrumentor = self.instrumentors.get(kind)
		if instrumentor:
			try:
				return instrumentor.instrument(self, kind, **kwargs)
			except Exception as e:
				raise InstrumentorError(f"failed to instrument {kind=}") from e
		else:
			raise InstrumentorError(f"no provider {kind=}")

	def register(self, kind: Kind, instrumentor: Instrumentor):
		"""Register an Instrumentor for a Kind. The instrumentor will be called for every instance of the Kind."""
		if existing := self.instrumentors.get(kind):
			if isinstance(existing, InstrumentorComposite):
				n = [*existing.instrumentors, instrumentor]
			else:
				n = [existing, instrumentor]
			self.instrumentors[kind] = InstrumentorComposite(self, kind, n)
		else:
			self.instrumentors[kind] = instrumentor

	def register_many(self, registrations: Registrations):
		"""Register multiple Instrumentors."""
		for kind, instrumentor in registrations:
			self.register(kind, instrumentor)

	def extend(self, other: InstrumentorRegistry):
		"""Add all registrations from another instrumentor to this one."""
		for kind, instrumentor in other.instrumentors.items():
			self.register(kind, instrumentor)


class InstrumentorError(Exception):
	"""An error instrumenting an object"""
