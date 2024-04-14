"""Generic Scanner components"""
import itertools
import operator
from functools import reduce

from pydantic import BaseModel

from alpacalert.models import Sensor, Status, System


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
