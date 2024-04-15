import kr8s
from pydantic import BaseModel

from alpacalert.generic import SensorConstant, SystemAll
from alpacalert.models import Instrumentor, Log, Scanner, Severity, State, Status


def condition_is(condition, passing_if: bool) -> State:
	return State.PASSING if condition["status"].lower() == str(passing_if).lower() else State.FAILING


class InstrumentorNode(Instrumentor, BaseModel):
	"""Instrument K8s nodes"""

	cluster_name: str

	def instrument_node(self, node: kr8s.objects.Node) -> Scanner:
		pressure_types = {'MemoryPressure', 'DiskPressure', 'PIDPressure'}
		ready = 'Ready'

		sensors = []
		for condition in node.status.conditions:
			condition_type = condition["type"]
			if condition_type in pressure_types:
				state = condition_is(condition, False)
			elif condition_type == ready:
				state = condition_is(condition, True)
			else:
				continue

			loglevel = Severity.INFO if state is State.PASSING else Severity.WARN

			sensors.append(
				SensorConstant(
					name=condition_type,
					val=Status(
						state=state,
						messages=[Log(
							message=condition["message"],
							severity=loglevel,
						)]
					)
				)
			)

		return SystemAll(
			name=node.name,
			scanners=sensors
		)

	def instrument(self) -> list[Scanner]:
		"""Get information about k8s nodes"""
		nodes = kr8s.get("nodes")
		return [self.instrument_node(node) for node in nodes]


class InstrumentorK8s(Instrumentor, BaseModel):
	"""Instrument Kubernetes objects"""

	def instrument(self) -> list[Scanner]:
		pass
