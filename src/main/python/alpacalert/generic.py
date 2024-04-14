"""Generic Scanner components"""
import itertools
import operator
from functools import reduce

from pydantic import BaseModel

from alpacalert.models import Log, Sensor, Service, State, Status, System


class SystemAny(System, BaseModel):
	"""System that is PASSING if any of its Sensors are PASSING"""

	sensors: list[Sensor]

	def status(self) -> Status:
		statuses = [sensor.status() for sensor in self.sensors]
		state = reduce(operator.or_, statuses)
		return Status(
			state=state,
			messages=list(itertools.chain.from_iterable(status.messages for status in statuses))
		)


class SystemAll(System, BaseModel):
	"""System that is PASSING if all of its Sensors are PASSING"""

	sensors: list[Sensor]

	def status(self) -> Status:
		statuses = [sensor.status() for sensor in self.sensors]
		state = reduce(operator.and_, statuses)
		return Status(
			state=state,
			messages=list(itertools.chain.from_iterable(status.messages for status in statuses))
		)


class ServiceBasic(Service, BaseModel):
	"""A basic Service that relies on a single System"""

	system: System

	def status(self) -> Status:
		return self.system.status()


class SensorConstant(Sensor, BaseModel):
	"""
	A Sensor that provides a constant value.

	Useful to construct Sensors which don't determine their own status.
	"""
	_status: Status

	def status(self) -> Status:
		return self._status

	@classmethod
	def failing(cls, messages: list[Log]):
		"""Helper for failing sensors"""

		return cls(_status=Status(state=State.FAILING, messages=messages))

	@classmethod
	def passing(cls, messages: list[Log]):
		"""Helper for passing sensors"""

		return cls(_status=Status(state=State.PASSING, messages=messages))
