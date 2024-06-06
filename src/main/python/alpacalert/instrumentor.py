from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Iterable

from alpacalert.models import Scanner


@dataclass(frozen=True)
class Kind:
	namespace: str
	name: str


Registrations = Iterable[tuple[Kind, "Instrumentor"]]


class Instrumentor:
	registry: InstrumentorRegistry

	@abstractmethod
	def registrations(self) -> Registrations:
		"""The Instrumentors that should be added for each Kind"""

	@abstractmethod
	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		"""Add scanners for an object"""


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
		self.instrumentors[kind] = instrumentor


class InstrumentorError(Exception):
	"""An error instrumenting an object"""
