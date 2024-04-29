from typing import Callable

import kr8s
from pydantic import BaseModel

from alpacalert.generic import SensorConstant, SystemAll
from alpacalert.models import Instrumentor, Log, Scanner, Sensor, Severity, State, Status


def condition_is(condition, passing_if: bool) -> State:
	return State.PASSING if condition["status"].lower() == str(passing_if).lower() else State.FAILING


def evaluate_conditions(passing_if_true: set[str], passing_if_false: set[str]) -> Callable[[list[dict]], list[Sensor]]:
	def evaluate_condition(conditions) -> list[Sensor]:
		sensors = []
		for condition in conditions:
			condition_type = condition["type"]
			if condition_type in passing_if_true:
				state = condition_is(condition, True)
			elif condition_type in passing_if_false:
				state = condition_is(condition, False)
			else:
				continue

			if "message" in condition:
				loglevel = Severity.INFO if state is State.PASSING else Severity.WARN
				logs = [
					Log(
						message=condition["message"],
						severity=loglevel,
					)
				]
			else:
				logs = []

			sensors.append(SensorConstant(name=condition_type, val=Status(state=state, messages=logs)))
		return sensors

	return evaluate_condition


class InstrumentorNode(Instrumentor, BaseModel):
	"""Instrument K8s nodes"""

	cluster_name: str

	@staticmethod
	def instrument_node(node: kr8s.objects.Node) -> Scanner:
		return SystemAll(name=node.name, scanners=evaluate_conditions({"Ready"}, {"MemoryPressure", "DiskPressure", "PIDPressure"})(node.status.conditions))

	def instrument(self) -> list[Scanner]:
		"""Get information about k8s nodes"""
		nodes = kr8s.get("nodes")
		return [self.instrument_node(node) for node in nodes]


class InstrumentorConfigmaps(Instrumentor, BaseModel):
	"""Instrument Kubernetes configmaps. Basically just an existance check"""

	@staticmethod
	def instrument_configmap(configmap: kr8s.objects.ConfigMap) -> Scanner:
		return SensorConstant(name=f"configmap {configmap.name} exists", val=Status(state=State.PASSING))

	@staticmethod
	def exists(name: str) -> Scanner:
		if any(e.name == "name" for e in kr8s.get("configmaps")):
			state = State.PASSING
		else:
			state = State.FAILING

		return SensorConstant(name=f"configmap {name} exists", val=Status(state=state))

	def instrument(self) -> list[Scanner]:
		return [self.instrument_configmap(configmap) for configmap in kr8s.get("configmaps")]


class InstrumentorSecrets(Instrumentor, BaseModel):
	"""Instrument Kubernetes secrets. Basically just an existance check"""

	@staticmethod
	def instrument_secret(secret: kr8s.objects.ConfigMap) -> Scanner:
		return SensorConstant(name=f"secret {secret.name} exists", val=Status(state=State.PASSING))

	@staticmethod
	def exists(name: str) -> Scanner:
		if any(e.name == "name" for e in kr8s.get("secrets")):
			state = State.PASSING
		else:
			state = State.FAILING

		return SensorConstant(name=f"secret {name} exists", val=Status(state=state))

	def instrument(self) -> list[Scanner]:
		return [self.instrument_secret(secret) for secret in kr8s.get("secrets")]


class InstrumentorPods(Instrumentor, BaseModel):
	"""Instrument Kubernetes Pods in a namespace"""

	namespace: str

	@staticmethod
	def instrument_pod(pod: kr8s.objects.Pod) -> Scanner:
		pod_sensors = evaluate_conditions({"Initialized", "Ready", "ContainersReady", "PodScheduled"}, {})
		container_sensors = [InstrumentorPods.instrument_container(e) for e in pod.status.containerStatuses]
		scanners = [
			*pod_sensors(pod.status.conditions),
			SensorConstant(name="phase is running", val=Status(state=State.PASSING if pod.status.phase == "Running" else State.FAILING)),
			*container_sensors,
		]

		return SystemAll(name=pod.name, scanners=scanners)

	@staticmethod
	def instrument_container(container_status) -> Scanner:
		if container_status.ready and container_status.started:
			state = State.PASSING
		else:
			state = State.FAILING

		# TODO: add state as message
		return SensorConstant(name=f"Pod is running: {container_status.name}", val=Status(state=state))

	def instrument(self) -> list[Scanner]:
		pods = kr8s.get("pods")
		return [self.instrument_pod(pod) for pod in pods]


class InstrumentorK8s(Instrumentor, BaseModel):
	"""Instrument Kubernetes objects"""

	def instrument(self) -> list[Scanner]:
		pass