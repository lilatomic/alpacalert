from typing import Sequence

from alpacalert.models import Scanner, Sensor, Status


class SensorRaises(Sensor):
	"""A sensor that raises an exception during evaluation"""

	def status(self) -> Status:
		raise Exception("SensorRaises always raises an exception")

	def children(self) -> Sequence[Scanner]:
		raise Exception("SensorRaises always raises an exception")
