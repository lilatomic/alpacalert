"""Generic Scanner components"""

import operator
from functools import reduce

from pydantic import BaseModel

from alpacalert.models import Log, Scanner, Sensor, Service, State, Status, System


class SystemAny(System, BaseModel):
	"""System that is PASSING if any of its Sensors are PASSING"""

	scanners: list[Scanner]

	def status(self) -> Status:
		statuses = [sensor.status() for sensor in self.scanners]
		state = reduce(operator.or_, (status.state for status in statuses))
		return Status(state=state)

	def children(self) -> list[Scanner]:
		return self.scanners


class SystemAll(System, BaseModel):
	"""System that is PASSING if all of its Sensors are PASSING"""

	scanners: list[Scanner]

	def status(self) -> Status:
		statuses = [sensor.status() for sensor in self.scanners]
		state = reduce(operator.and_, (status.state for status in statuses))
		return Status(state=state)

	def children(self) -> list[Scanner]:
		return self.scanners


class ServiceBasic(Service, BaseModel):
	"""A basic Service that relies on a single System"""

	system: System

	def status(self) -> Status:
		return self.system.status()

	def children(self) -> list[Scanner]:
		return [self.system]


class SensorConstant(Sensor, BaseModel):
	"""
	A Sensor that provides a constant value.

	Useful to construct Sensors which don't determine their own status.
	"""

	val: Status

	def status(self) -> Status:
		return self.val

	def children(self) -> list[Scanner]:
		return []

	@classmethod
	def failing(cls, messages: list[Log]):
		"""Helper for failing sensors"""

		return cls(_status=Status(state=State.FAILING, messages=messages))

	@classmethod
	def passing(cls, messages: list[Log]):
		"""Helper for passing sensors"""

		return cls(_status=Status(state=State.PASSING, messages=messages))
