"""Instrument all Kubernetes objects"""

from typing import Callable

import kr8s
from pydantic import BaseModel

from alpacalert.generic import SensorConstant, SystemAll, SystemAny
from alpacalert.models import Instrumentor, Log, Scanner, Sensor, Severity, State, Status, System


def condition_is(condition, passing_if: bool) -> State:
	"""Evaluate the truthiness of a Kubernetes condition."""
	return State.from_bool(condition["status"].lower() == str(passing_if).lower())


def evaluate_conditions(passing_if_true: set[str], passing_if_false: set[str]) -> Callable[[list[dict]], list[Sensor]]:
	"""Evaluate "conditions" of a Kubernetes object"""

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
		"""Instrument a Kubernetes node"""
		return SystemAll(name=node.name, scanners=evaluate_conditions({"Ready"}, {"MemoryPressure", "DiskPressure", "PIDPressure"})(node.status.conditions))

	def instrument(self) -> list[Scanner]:
		"""Get information about k8s nodes"""
		nodes = kr8s.get("nodes")
		return [self.instrument_node(node) for node in nodes]


class InstrumentorConfigmaps(Instrumentor, BaseModel):
	"""Instrument Kubernetes configmaps. Basically just an existance check"""

	@staticmethod
	def instrument_configmap(configmap: kr8s.objects.ConfigMap) -> Scanner:
		"""Instrument a Kubernetes configmap"""
		return SensorConstant(name=f"configmap {configmap.name} exists", val=Status(state=State.PASSING))

	@staticmethod
	def exists(name: str) -> Scanner:
		"""Validate that a Kubernetes configmap exists"""
		return SensorConstant(
			name=f"configmap {name} exists",
			val=Status(
				state=State.from_bool(any(e.name == "name" for e in kr8s.get("configmaps"))),
			),
		)

	def instrument(self) -> list[Scanner]:
		return [self.instrument_configmap(configmap) for configmap in kr8s.get("configmaps")]


class InstrumentorSecrets(Instrumentor, BaseModel):
	"""Instrument Kubernetes secrets. Basically just an existance check"""

	@staticmethod
	def instrument_secret(secret: kr8s.objects.ConfigMap) -> Scanner:
		"""Instrument a Kubernetes secret"""
		return SensorConstant(name=f"secret {secret.name} exists", val=Status(state=State.PASSING))

	@staticmethod
	def exists(name: str) -> Scanner:
		"""Validate that a secret exists"""
		return SensorConstant(
			name=f"secret {name} exists",
			val=Status(
				state=State.from_bool(any(e.name == "name" for e in kr8s.get("secrets"))),
			),
		)

	def instrument(self) -> list[Scanner]:
		return [self.instrument_secret(secret) for secret in kr8s.get("secrets")]


class InstrumentorPods(Instrumentor, BaseModel):
	"""Instrument Kubernetes Pods in a namespace"""

	namespace: str

	@staticmethod
	def instrument_pod(pod: kr8s.objects.Pod) -> Scanner:
		"""Instrument a Pod"""
		pod_sensors = evaluate_conditions({"Initialized", "Ready", "ContainersReady", "PodScheduled"}, set())
		if "containerStatuses" in pod.status:
			container_sensor = SystemAll(name="containers", scanners=[InstrumentorPods.instrument_container(e) for e in pod.status.containerStatuses])
		else:
			container_sensor = SensorConstant.failing(name="containers")  # TODO: more meaningful recovery
		scanners = [
			*pod_sensors(pod.status.conditions),
			SensorConstant(name="phase is running", val=Status(state=State.PASSING if pod.status.phase == "Running" else State.FAILING)),
			container_sensor,
			SystemAll(name="volumes", scanners=[InstrumentorPods.instrument_volume(pod, v["name"], v) for v in pod.spec.volumes]),
		]

		return SystemAll(name=f"pod {pod.name}", scanners=scanners)

	@staticmethod
	def instrument_container(container_status) -> Scanner:
		"""Instrument a container"""
		# TODO: add state as message
		return SensorConstant(name=f"Pod is running: {container_status.name}", val=Status(state=State.from_bool(container_status.ready and container_status.started)))

	@staticmethod
	def instrument_volume(pod: kr8s.objects.Pod, volume_name: str, volume) -> Scanner:
		"""Instrument volumes on a pod"""
		if "configMap" in volume:
			[configmap] = kr8s.get("configmaps", volume["configMap"]["name"], namespace=pod.namespace)
			return SystemAll(name=f"volume {volume_name}", scanners=[InstrumentorConfigmaps.instrument_configmap(configmap)])
		elif "hostPath" in volume:
			return SensorConstant.passing(f"hostMount {volume_name}", [])
		elif "projected" in volume:
			return SystemAll(
				name=f"projected volume {volume_name}", scanners=[InstrumentorPods.instrument_volume(pod, str(i), v) for i, v in enumerate(volume["projected"]["sources"])]
			)
		elif "downwardAPI" in volume:
			return SensorConstant.passing(f"{volume_name} downwardAPI", [])  # TODO: validate
		elif "serviceAccountToken" in volume:
			return SensorConstant.passing(f"{volume_name} serviceAccountToken", [])  # TODO: include more information on service account
		else:
			return SensorConstant.passing(f"volume {volume_name} cannot be instrumented", [])

	def instrument(self) -> list[Scanner]:
		pods = kr8s.get("pods")
		return [self.instrument_pod(pod) for pod in pods]


def replica_statuses(target: int, kinds: set[str], status) -> System:
	"""Compute statuses for the number of replicas"""
	return SystemAll(name="replicas", scanners=[SensorConstant(name=kind, val=Status(state=State.from_bool(status.get(kind) == target))) for kind in kinds])


class InstrumentorReplicaSets(Instrumentor, BaseModel):
	"""Instrument kubernetes ReplicaSets"""

	@staticmethod
	def instrument_replicaset(replicaset: kr8s.objects.ReplicaSet) -> Scanner:
		"""Instrument a ReplicaSet."""
		count_sensors = replica_statuses(replicaset.spec.replicas, {"replicas", "availableReplicas", "readyReplicas"}, replicaset.status)
		pod_sensors = SystemAll(
			name="pods", scanners=[InstrumentorPods.instrument_pod(e) for e in kr8s.get("pods", label_selector=replicaset.spec.selector.matchLabels)]
		)  # TODO: need to filter ownerReferences too

		return SystemAll(name=replicaset.name, scanners=[count_sensors, pod_sensors])

	def instrument(self) -> list[Scanner]:
		replicasets = kr8s.get("replicasets")
		return [self.instrument_replicaset(replicaset) for replicaset in replicasets]


class InstrumentorDeployments(Instrumentor, BaseModel):
	"""Instrument kubernetes deployments"""

	@staticmethod
	def instrument_deployment(deployment: kr8s.objects.Deployment) -> Scanner:
		"""Instrument a deployment"""
		status_sensors = evaluate_conditions({"Progressing", "Available"}, set())(deployment.status.conditions)
		count_sensor = replica_statuses(deployment.spec.replicas, {"replicas", "availableReplicas", "readyReplicas", "updatedReplicas"}, deployment.status)
		replicaset_sensor = SystemAll(
			name="replicasets", scanners=[InstrumentorReplicaSets.instrument_replicaset(e) for e in kr8s.get("replicasets", label_selector=deployment.spec.selector.matchLabels)]
		)
		return SystemAll(name=deployment.name, scanners=[*status_sensors, count_sensor, replicaset_sensor])

	def instrument(self) -> list[Scanner]:
		deployments = kr8s.get("deployments")
		return [self.instrument_deployment(deployment) for deployment in deployments]


class InstrumentorDaemonset(Instrumentor, BaseModel):
	"""Instrument Kubernetes daemonsets"""

	@staticmethod
	def instrument_daemonset(daemonset: kr8s.objects.DaemonSet) -> Scanner:
		count_sensor = replica_statuses(
			daemonset.status.desiredNumberScheduled, {"currentNumberScheduled", "numberAvailable", "numberReady", "updatedNumberScheduled"}, daemonset.status
		)
		pod_sensor = SystemAll(
			name="pods", scanners=[InstrumentorPods.instrument_pod(e) for e in kr8s.get("pods", label_selector=daemonset.spec.selector.matchLabels)]
		)  # TODO: need to filter ownerReferences too
		misscheduled_sensor = SensorConstant(name="numberMisscheduled", val=Status(state=State.from_bool(daemonset.status.numberMisscheduled == 0)))

		return SystemAll(name=f"daemonset {daemonset.name}", scanners=[count_sensor, misscheduled_sensor, pod_sensor])

	def instrument(self) -> list[Scanner]:
		daemonsets = kr8s.get("daemonsets")
		return [self.instrument_daemonset(e) for e in daemonsets]


class InstrumentorServices(Instrumentor, BaseModel):
	"""Instrument Kubernetes services"""

	# TODO: Consider using Endpoints resources

	@staticmethod
	def instrument_service(service: kr8s.objects.Service) -> Scanner:
		"""Instrument a service"""
		endpoint_pods = kr8s.get("pods", label_selector=service.spec.selector)
		pod_sensor = SystemAny(
			name="enpoints",
			scanners=[InstrumentorPods.instrument_pod(e) for e in endpoint_pods],
		)
		return SystemAll(name=service.name, scanners=[pod_sensor])

	def instrument(self) -> list[Scanner]:
		services = kr8s.get("services")
		return [self.instrument_service(service) for service in services]


class InstrumentorIngresses(Instrumentor, BaseModel):
	"""Instrument Kubernetes ingresses"""

	@staticmethod
	def instrument_path(path):
		"""Instrument a path of an ingress rule"""
		backend = path.backend
		if "service" in backend:
			[service] = kr8s.get("services", backend.service.name)
			return InstrumentorServices.instrument_service(service)
		elif "resource" in backend:
			return SensorConstant.passing("resource", [])  # TODO: resolve object references
		else:
			return SensorConstant.passing(f"path {path.path} cannot be instrumented", [])

	@staticmethod
	def instrument_ingress(ingress: kr8s.objects.Ingress) -> Scanner:
		"""Instrument a Kubernetes ingress"""
		path_sensors = []
		for rule_number, rule in enumerate(ingress.spec.rules):
			for path_number, path in enumerate(rule.http.paths):
				path_sensors.append(
					SystemAll(
						name=f"path {rule_number}:{path_number} {path.path}",
						scanners=[InstrumentorIngresses.instrument_path(path)],
					)
				)
		return SystemAll(name=ingress.name, scanners=path_sensors)

	def instrument(self) -> list[Scanner]:
		ingresses = kr8s.get("ingresses")
		return [self.instrument_ingress(ingress) for ingress in ingresses]


class InstrumentorK8s(Instrumentor, BaseModel):
	"""Instrument Kubernetes objects"""

	def instrument(self) -> list[Scanner]:
		pass
