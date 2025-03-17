"""Generic Scanner components"""

import operator
from dataclasses import dataclass
from functools import reduce
from typing import Sequence

from alpacalert.models import Log, Scanner, Sensor, Service, State, Status, System


class ScannerError(Exception):
	"""Exception while scanning"""


def status_any(self):
	statuses = [sensor.status() for sensor in self.children()]
	state = reduce(operator.or_, (status.state for status in statuses))
	return Status(state=state)


@dataclass
class SystemAny(System):
	"""System that is PASSING if any of its Sensors are PASSING"""

	name: str
	scanners: Sequence[Scanner]

	def status(self) -> Status:
		statuses = [sensor.status() for sensor in self.scanners]
		state = reduce(operator.or_, (status.state for status in statuses))
		return Status(state=state)

	def children(self) -> Sequence[Scanner]:
		return self.scanners


def status_all(self):
	try:
		statuses = [sensor.status() for sensor in self.children()]
		state = reduce(operator.and_, (status.state for status in statuses))
		return Status(state=state)
	except Exception as e:
		raise ScannerError(f"error instrumenting {type(self)}") from e


@dataclass
class SystemAll(System):
	"""System that is PASSING if all of its Sensors are PASSING"""

	name: str
	scanners: Sequence[Scanner]

	def status(self) -> Status:
		statuses = [sensor.status() for sensor in self.scanners]
		state = reduce(operator.and_, (status.state for status in statuses))
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
