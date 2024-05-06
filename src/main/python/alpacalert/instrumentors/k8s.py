"""Instrument all Kubernetes objects"""

from abc import ABC
from dataclasses import dataclass
from typing import Callable

import kr8s
from pydantic import BaseModel

from alpacalert.generic import SensorConstant, SystemAll, SystemAny
from alpacalert.models import Instrumentor, Log, Scanner, Sensor, Severity, State, Status, System


class StorageClass(kr8s.objects.APIObject):
	kind = "StorageClass"
	version = "storage.k8s.io/v1"
	_asyncio = False
	endpoint = "storageclasses"
	plural = "storageclasses"
	singular = "storageclass"
	namespaced = False
	scalable = False


@dataclass
class K8s:
	kr8s: kr8s

	def exists(self, kind: str, namespace: str, name: str) -> bool:
		"""Validate that a resource exists"""
		resources = kr8s.get(kind, name, namespace=namespace)
		return len(resources) > 0

	def list(self, kind: str, namespace: str = kr8s.ALL) -> list:
		return self.kr8s.get(kind, namespace=namespace)


class InstrumentorKubernetes(Instrumentor, BaseModel, ABC):
	"""Base for all Kubernetes instrumentors"""

	k8s: K8s


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

			maybe_message = condition.get("message") or condition.get("reason")
			if maybe_message:
				loglevel = Severity.INFO if state is State.PASSING else Severity.WARN
				logs = [
					Log(
						message=maybe_message,
						severity=loglevel,
					)
				]
			else:
				logs = []

			sensors.append(SensorConstant(name=condition_type, val=Status(state=state, messages=logs)))
		return sensors

	return evaluate_condition


class InstrumentorNode(InstrumentorKubernetes):
	"""Instrument K8s nodes"""

	cluster_name: str

	@staticmethod
	def instrument_node(node: kr8s.objects.Node) -> Scanner:
		"""Instrument a Kubernetes node"""
		return SystemAll(name=node.name, scanners=evaluate_conditions({"Ready"}, {"MemoryPressure", "DiskPressure", "PIDPressure"})(node.status.conditions))

	def instrument(self) -> list[Scanner]:
		"""Get information about k8s nodes"""
		return [self.instrument_node(node) for node in (self.k8s.list("nodes"))]


class InstrumentorConfigmaps(InstrumentorKubernetes):
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
		return [self.instrument_configmap(configmap) for configmap in self.k8s.list("configmaps")]


class InstrumentorSecrets(InstrumentorKubernetes):
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
				state=State.from_bool(any(e.name == name for e in kr8s.get("secrets"))),
			),
		)

	def instrument(self) -> list[Scanner]:
		return [self.instrument_secret(secret) for secret in self.k8s.list("secrets")]


class InstrumentorStorageclass(InstrumentorKubernetes):
	"""Instrument Kubernetes storageclass"""

	@staticmethod
	def instrument_storageclass(storageclass):
		"""Instrument a Kubernetes storageclass"""

		return SensorConstant(name=f"storageclass {storageclass.name} exists", val=Status(state=State.PASSING))

	@staticmethod
	def exists(name: str) -> Scanner:
		"""Validate that a Kubernetes configmap exists"""
		return SensorConstant(
			name=f"storageclass {name} exists",
			val=Status(
				state=State.from_bool(any(e.name == name for e in kr8s.get("StorageClasses"))),
			),
		)

	def instrument(self) -> list[Scanner]:
		storageclasses = self.k8s.list("storageclass")
		return [self.instrument_storageclass(storageclass) for storageclass in storageclasses]


class InstrumentorPVCs(InstrumentorKubernetes):
	"""Instrument Kubernetes PVCs"""

	@staticmethod
	def instrument_pvc(pvc: kr8s.objects.PersistentVolumeClaim) -> Scanner:
		"""Instrument a Kubernetes PVC"""
		match pvc.status.phase:
			case "Pending":
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))
			case "Bound":
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.PASSING))
			case _:
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))

		storageclass_sensor = InstrumentorStorageclass.exists(pvc.spec.storageClassName)

		return SystemAll(name=pvc.name, scanners=[phase_sensor, storageclass_sensor])

	def instrument(self) -> list[Scanner]:
		return [self.instrument_pvc(pvc) for pvc in (self.k8s.list("pvcs"))]


class InstrumentorPods(InstrumentorKubernetes):
	"""Instrument Kubernetes Pods in a namespace"""

	@staticmethod
	def instrument_pod(pod: kr8s.objects.Pod) -> Scanner:
		"""Instrument a Pod"""
		match pod.status.phase:
			case "Pending":
				pod_sensors = evaluate_conditions({"PodScheduled"}, set())(pod.status.conditions)
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.UNKNOWN))
			case "Running":
				pod_sensors = evaluate_conditions({"Initialized", "Ready", "ContainersReady", "PodScheduled"}, set())(pod.status.conditions)
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.PASSING))
			case "Succeeded":
				pod_sensors = evaluate_conditions({"Initialized", "PodScheduled"}, {"Ready", "ContainersReady"})(pod.status.conditions)
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.PASSING))
			case "Failed":
				...  # TODO
			case "Unknown":
				...  # TODO

		if "containerStatuses" in pod.status:
			container_sensor = SystemAll(name="containers", scanners=[InstrumentorPods.instrument_container(e) for e in pod.status.containerStatuses])
		else:
			container_sensor = SensorConstant.failing(name="containers", messages=[])  # TODO: more meaningful recovery
		scanners = [
			*pod_sensors,
			phase_sensor,
			container_sensor,
			SystemAll(name="volumes", scanners=[InstrumentorPods.instrument_volume(pod, v["name"], v) for v in pod.spec.volumes]),
		]

		return SystemAll(name=f"pod {pod.name}", scanners=scanners)

	@staticmethod
	def instrument_container(container_status) -> Scanner:
		"""Instrument a container"""
		# TODO: add state as message
		if "running" in container_status.state:
			state = State.from_bool(container_status.ready and container_status.started)
			message = "running"
		elif "terminated" in container_status.state:
			terminated_successfully = container_status.get("state", {}).get("terminated", {}).get("reason") == "Completed"
			state = State.from_bool(not container_status.ready and not container_status.started and terminated_successfully)
			message = "terminated"
		elif "waiting" in container_status.state:
			state = State.FAILING
			message = "waiting"
		else:
			state = State.UNKNOWN
			message = "unknown state"

		return SensorConstant(name=f"Container status: {container_status.name}", val=Status(state=state, messages=[Log(message=message, severity=Severity.INFO)]))

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
		elif "persistentVolumeClaim" in volume:
			[pvc] = kr8s.get("pvc", volume["persistentVolumeClaim"]["claimName"], namespace=pod.namespace)
			return InstrumentorPVCs.instrument_pvc(pvc)
		else:
			return SensorConstant.passing(f"volume {volume_name} cannot be instrumented", [])

	def instrument(self) -> list[Scanner]:
		pods = self.k8s.list("pods")
		return [self.instrument_pod(pod) for pod in pods]


def replica_statuses(target: int, kinds: set[str], status) -> System:
	"""Compute statuses for the number of replicas"""
	return SystemAll(name="replicas", scanners=[SensorConstant(name=kind, val=Status(state=State.from_bool(status.get(kind) == target))) for kind in kinds])


class InstrumentorReplicaSets(InstrumentorKubernetes):
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
		replicasets = self.k8s.list("replicasets")
		return [self.instrument_replicaset(replicaset) for replicaset in replicasets]


class InstrumentorDeployments(InstrumentorKubernetes):
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
		return [self.instrument_deployment(deployment) for deployment in (self.k8s.list("deployments"))]


class InstrumentorDaemonset(InstrumentorKubernetes):
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
		return [self.instrument_daemonset(e) for e in (self.k8s.list("daemonsets"))]


class InstrumentorStatefulsets(InstrumentorKubernetes):
	"""Instrument kubernetes statefulsets"""

	@staticmethod
	def instrument_statefulset(statefulset: kr8s.objects.StatefulSet) -> Scanner:
		"""Instrument a statefulset"""
		count_sensor = replica_statuses(statefulset.spec.replicas, {"availableReplicas", "currentReplicas", "replicas", "updatedReplicas"}, statefulset.status)
		collision_sensor = SensorConstant(name="collisionCount", val=Status(state=State.from_bool(statefulset.status.collisionCount == 0)))
		pod_sensor = SystemAll(
			name="pods", scanners=[InstrumentorPods.instrument_pod(e) for e in kr8s.get("pods", label_selector=statefulset.spec.selector.matchLabels)]
		)  # TODO: need to filter ownerReferences too

		return SystemAll(name=statefulset.name, scanners=[count_sensor, collision_sensor, pod_sensor])

	def instrument(self) -> list[Scanner]:
		return [self.instrument_statefulset(statefulset) for statefulset in self.k8s.list("statefulsets")]


class InstrumentorJobs(InstrumentorKubernetes):
	"""Instrument Kubernetes jobs"""

	@staticmethod
	def instrument_job(job: kr8s.objects.Job) -> Scanner:
		status_sensors = evaluate_conditions({"Complete"}, set())(job.status.conditions)

		pods = kr8s.get("pods", label_selector=job.spec.selector.matchLabels)
		if pods:
			pod_sensor = SystemAll(name="pods", scanners=[InstrumentorPods.instrument_pod(e) for e in pods])
		else:
			pod_sensor = SensorConstant.passing(name="pods", messages=[Log(message="No pods found", severity=Severity.INFO)])

		return SystemAll(name=job.name, scanners=[*status_sensors, pod_sensor])

	def instrument(self) -> list[Scanner]:
		return [self.instrument_job(job) for job in self.k8s.list("jobs")]


class InstrumentorServices(InstrumentorKubernetes):
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
		return [self.instrument_service(service) for service in (self.k8s.list("services"))]


class InstrumentorIngresses(InstrumentorKubernetes):
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


# class InstrumentorK8s(Instrumentor, BaseModel):
# 	"""Instrument Kubernetes objects"""
#
# 	def instrument(self) -> list[Scanner]:
# 		pass
