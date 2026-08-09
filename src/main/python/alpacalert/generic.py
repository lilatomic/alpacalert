"""Generic Scanner components"""

import operator
from dataclasses import dataclass
from functools import reduce
from typing import Sequence

from alpacalert.models import Log, Scanner, Sensor, Service, Severity, State, Status, System


class ScannerError(Exception):
	"""Exception while scanning"""


def status_any(self):
	state = reduce(operator.or_, (status.state for status in self.child_statuses()))
	return Status(state=state)


@dataclass
class SystemAny(System):
	"""System that is PASSING if any of its Sensors are PASSING"""

	name: str
	scanners: Sequence[Scanner]

	def status(self) -> Status:
		state = reduce(operator.or_, (status.state for status in self.child_statuses()))
		return Status(state=state)

	def children(self) -> Sequence[Scanner]:
		return self.scanners


def status_all(self):
	try:
		state = reduce(operator.and_, (status.state for status in self.child_statuses()))
		return Status(state=state)
	except Exception as e:
		raise ScannerError(f"error instrumenting {type(self)}") from e


@dataclass
class SystemAll(System):
	"""System that is PASSING if all of its Sensors are PASSING"""

	name: str
	scanners: Sequence[Scanner]

	def status(self) -> Status:
		state = reduce(operator.and_, (status.state for status in self.child_statuses()))
		return Status(state=state)

	def children(self) -> Sequence[Scanner]:
		return self.scanners


@dataclass
class ServiceBasic(Service):
	"""A basic Service that relies on a single System"""

	name: str
	system: System

	def status(self) -> Status:
		return self.system.status()

	def children(self) -> list[Scanner]:
		return [self.system]


@dataclass
class SensorConstant(Sensor):
	"""
	A Sensor that provides a constant value.

	Useful to construct Sensors which don't determine their own status.
	"""

	name: str
	val: Status

	def status(self) -> Status:
		return self.val

	def children(self) -> list[Scanner]:
		return []

	@classmethod
	def failing(cls, name: str, messages: list[Log]):
		"""Helper for failing sensors"""

		return cls(name=name, val=Status(state=State.FAILING, messages=messages))

	@classmethod
	def passing(cls, name: str, messages: list[Log]):
		"""Helper for passing sensors"""

		return cls(name=name, val=Status(state=State.PASSING, messages=messages))


@dataclass
class SystemOptional(System):
	"""
	An Service that relies on a single System, but does not require that system to be operational.

	This is useful for modeling optional dependencies.
	"""

	name: str
	scanner: Scanner

	def status(self) -> Status:
		return Status(state=State.PASSING)

	def children(self) -> list[Scanner]:
		return [self.scanner]

	def child_statuses(self) -> Sequence[Status]:
		try:
			return [self.scanner.status()]
		except Exception as e:
			return [
				Status(
					state=State.PASSING,
					messages=[
						Log(severity=Severity.INFO, message="System is optional"),
						Log(severity=Severity.INFO, message=str(e)),
					],
				)
			]
