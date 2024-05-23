"""Instrument all Kubernetes objects"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Type

import kr8s

from alpacalert.generic import SensorConstant, SystemAll, SystemAny
from alpacalert.models import Instrumentor, InstrumentorError, Log, Scanner, Sensor, Severity, State, Status, System


class StorageClass(kr8s.objects.APIObject):
	kind = "StorageClass"
	version = "storage.k8s.io/v1"
	_asyncio = False
	endpoint = "storageclasses"
	plural = "storageclasses"
	singular = "storageclass"
	namespaced = False
	scalable = False


class SensorK8s(SensorConstant):
	"""Sense a K8s object"""


Registrations = Iterable[tuple[str, Type[Instrumentor]]]


@dataclass
class K8s:
	kr8s: kr8s

	def exists(self, kind: str, namespace: str, name: str) -> bool:
		"""Validate that a resource exists"""
		resources = kr8s.get(kind, name, namespace=namespace)
		return len(resources) > 0

	def get_all(self, kind: str, namespace: str = kr8s.ALL) -> list:
		return self.kr8s.get(kind, namespace=namespace)

	def get(self, kind: str, namespace: str, name: str) -> Optional[kr8s.objects.APIObject]:
		result = self.kr8s.get(kind, name, namespace=namespace)
		if len(result) == 1:
			return result[0]
		elif len(result) == 0:
			return None
		else:
			raise InstrumentorError(f"Multiple resources found for {kind=} {namespace=} {name=}")

	def children(self, kind: str, namespace: str, label_selector: dict) -> list[kr8s.objects.APIObject]:
		return self.kr8s.get(kind, namespace=namespace, label_selector=label_selector)


@dataclass
class InstrumentorKubernetes(Instrumentor, ABC):
	"""Base for all Kubernetes instrumentors"""

	k8s: K8s

	@classmethod
	@abstractmethod
	def registrations(cls) -> Registrations:
		"""Mappings of Kubernetes kind uris to instrumentors"""


@dataclass(frozen=True)
class InstrumentK8sReq:
	"""Request to instrument a Kubernetes object"""

	v: Any

	uri: str
	kind_uri: str


class InstrumentorK8s:
	def __init__(self, k8s: K8s, instrumentors: dict[str, InstrumentorKubernetes] | None = None):
		self.k8s = k8s

		if instrumentors:
			self.instrumentors = instrumentors

		else:
			self.instrumentors = {}


			default_instrumentors = [
				*InstrumentorNode.registrations(),
				*InstrumentorConfigmaps.registrations(),
				*InstrumentorSecrets.registrations(),
				*InstrumentorStorageclass.registrations(),
				*InstrumentorPVCs.registrations(),
				*InstrumentorPods.registrations(),
				*InstrumentorReplicaSets.registrations(),
				*InstrumentorDeployments.registrations(),
				*InstrumentorDaemonset.registrations(),
				*InstrumentorStatefulsets.registrations(),
				*InstrumentorJobs.registrations(),
				*InstrumentorServices.registrations(),
				*InstrumentorIngresses.registrations(),
			]

			for instrumentor in default_instrumentors:
				self.register_instrumentor(instrumentor[0], instrumentor[1])

	def register_instrumentor(self, kind_uri: str, instrumentor: InstrumentorKubernetes):
		self.instrumentors[kind_uri] = instrumentor


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


@dataclass
class InstrumentorNode(InstrumentorKubernetes):
	"""Instrument K8s nodes"""

	def instrument(self, node: kr8s.objects.Node) -> Scanner:
		"""Instrument a Kubernetes node"""
		return SystemAll(name=node.name, scanners=evaluate_conditions({"Ready"}, {"MemoryPressure", "DiskPressure", "PIDPressure"})(node.status.conditions))

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/api/v1/nodes", cls)]


class InstrumentorConfigmaps(InstrumentorKubernetes):
	"""Instrument Kubernetes configmaps. Basically just an existance check"""

	def instrument(self, configmap: kr8s.objects.ConfigMap) -> Scanner:
		"""Instrument a Kubernetes configmap"""
		return SensorConstant(
			name=f"configmap {configmap.name} exists",
			val=Status(
				state=State.from_bool(self.k8s.exists("configmap", configmap.namespace, configmap.name)),
			),
		)

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/api/v1/configmaps", cls)]


class InstrumentorSecrets(InstrumentorKubernetes):
	"""Instrument Kubernetes secrets. Basically just an existance check"""

	def instrument(self, secret: kr8s.objects.ConfigMap) -> Scanner:
		"""Instrument a Kubernetes secret"""
		return SensorConstant(
			name=f"secret {secret.name} exists",
			val=Status(
				state=State.from_bool(self.k8s.exists("secret", secret.namespace, secret.name)),
			),
		)

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/api/v1/secrets", cls)]


class InstrumentorStorageclass(InstrumentorKubernetes):
	"""Instrument Kubernetes storageclass"""

	def instrument(self, storageclass):
		"""Instrument a Kubernetes storageclass"""

		return SensorConstant(
			name=f"storageclass {storageclass.name} exists",
			val=Status(
				state=State.from_bool(self.k8s.exists("StorageClasses", storageclass.namespace, storageclass.name)),
			),
		)

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/apis/storage.k8s.io/v1/storageclasses", cls)]


class InstrumentorPVCs(InstrumentorKubernetes):
	"""Instrument Kubernetes PVCs"""

	def instrument(self, pvc: kr8s.objects.PersistentVolumeClaim) -> Scanner:
		"""Instrument a Kubernetes PVC"""
		match pvc.status.phase:
			case "Pending":
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))
			case "Bound":
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.PASSING))
			case _:
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))

		storageclass_sensor = InstrumentorStorageclass(self.k8s).exists(pvc.namespace, pvc.spec.storageClassName)

		return SystemAll(name=f"pvc {pvc.name}", scanners=[phase_sensor, storageclass_sensor])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/app/v1/persistentvolumeclaims", cls)]


class InstrumentorPods(InstrumentorKubernetes):
	"""Instrument Kubernetes Pods in a namespace"""

	def instrument(self, pod: kr8s.objects.Pod) -> Scanner:
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
			container_sensor = SystemAll(name="containers", scanners=[self.instrument_container(e) for e in pod.status.containerStatuses])
		else:
			container_sensor = SensorConstant.failing(name="containers", messages=[])  # TODO: more meaningful recovery
		scanners = [
			*pod_sensors,
			phase_sensor,
			container_sensor,
			SystemAll(name="volumes", scanners=[self.instrument_volume(pod, v["name"], v) for v in pod.spec.volumes]),
		]

		return SystemAll(name=f"pod {pod.name}", scanners=scanners)

	class Container(InstrumentorKubernetes):
		def instrument(self, container_status) -> Scanner:
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

		@classmethod
		def registrations(cls) -> Registrations:
			return [("/api/v1/pods#container", cls)]

	class Volume(InstrumentorKubernetes):
		def instrument(self, req: tuple[kr8s.objects.Pod, str, Any]) -> Scanner:
			"""Instrument volumes on a pod"""
			pod, volume_name, volume = req

			if "configMap" in volume:
				configmap = self.k8s.get("configmaps", pod.namespace, volume["configMap"]["name"])
				return SystemAll(name=f"volume {volume_name}", scanners=[InstrumentorConfigmaps.instrument_configmap(configmap)])
			elif "hostPath" in volume:
				return SensorConstant.passing(f"hostMount {volume_name}", [])
			elif "projected" in volume:
				return SystemAll(name=f"projected volume {volume_name}", scanners=[self.instrument_volume(pod, str(i), v) for i, v in enumerate(volume["projected"]["sources"])])
			elif "downwardAPI" in volume:
				return SensorConstant.passing(f"{volume_name} downwardAPI", [])  # TODO: validate
			elif "serviceAccountToken" in volume:
				return SensorConstant.passing(f"{volume_name} serviceAccountToken", [])  # TODO: include more information on service account
			elif "persistentVolumeClaim" in volume:
				pvc = self.k8s.get("pvc", pod.namespace, volume["persistentVolumeClaim"]["claimName"])
				return InstrumentorPVCs(self.k8s).instrument_pvc(pvc)
			else:
				return SensorConstant.passing(f"volume {volume_name} cannot be instrumented", [])

		@classmethod
		def registrations(cls) -> Registrations:
			return [("/api/v1/pods#volume", cls)]

	@classmethod
	def registrations(cls) -> Registrations:
		return [
			("/api/v1/pods", cls),
			*cls.Container.registrations(),
			*cls.Volume.registrations(),
		]


def replica_statuses(target: int, kinds: set[str], status) -> System:
	"""Compute statuses for the number of replicas"""

	# TODO: make a real instrumentor?

	return SystemAll(name="replicas", scanners=[SensorConstant(name=kind, val=Status(state=State.from_bool(status.get(kind) == target))) for kind in kinds])


class InstrumentorReplicaSets(InstrumentorKubernetes):
	"""Instrument kubernetes ReplicaSets"""

	def instrument(self, replicaset: kr8s.objects.ReplicaSet) -> Scanner:
		"""Instrument a ReplicaSet."""
		count_sensors = replica_statuses(replicaset.spec.replicas, {"replicas", "availableReplicas", "readyReplicas"}, replicaset.status)
		pod_sensors = SystemAll(
			name="pods",
			scanners=[InstrumentorPods(self.k8s).instrument_pod(e) for e in self.k8s.children("pods", replicaset.namespace, label_selector=replicaset.spec.selector.matchLabels)],
		)  # TODO: need to filter ownerReferences too

		return SystemAll(name=replicaset.name, scanners=[count_sensors, pod_sensors])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/apis/apps/v1/replicasets", cls)]


class InstrumentorDeployments(InstrumentorKubernetes):
	"""Instrument kubernetes deployments"""

	def instrument(self, deployment: kr8s.objects.Deployment) -> Scanner:
		"""Instrument a deployment"""
		status_sensors = evaluate_conditions({"Progressing", "Available"}, set())(deployment.status.conditions)
		count_sensor = replica_statuses(deployment.spec.replicas, {"replicas", "availableReplicas", "readyReplicas", "updatedReplicas"}, deployment.status)
		replicaset_sensor = SystemAll(
			name="replicasets",
			scanners=[
				InstrumentorReplicaSets(self.k8s).instrument_replicaset(e)
				for e in self.k8s.children("replicasets", deployment.namespace, label_selector=deployment.spec.selector.matchLabels)
			],
		)
		return SystemAll(name=deployment.name, scanners=[*status_sensors, count_sensor, replicaset_sensor])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/apis/apps/v1/deployments", cls)]


class InstrumentorDaemonset(InstrumentorKubernetes):
	"""Instrument Kubernetes daemonsets"""

	def instrument(self, daemonset: kr8s.objects.DaemonSet) -> Scanner:
		count_sensor = replica_statuses(
			daemonset.status.desiredNumberScheduled, {"currentNumberScheduled", "numberAvailable", "numberReady", "updatedNumberScheduled"}, daemonset.status
		)
		pod_sensor = SystemAll(
			name="pods",
			scanners=[InstrumentorPods(self.k8s).instrument_pod(e) for e in self.k8s.children("pods", daemonset.namespace, label_selector=daemonset.spec.selector.matchLabels)],
		)  # TODO: need to filter ownerReferences too
		misscheduled_sensor = SensorConstant(name="numberMisscheduled", val=Status(state=State.from_bool(daemonset.status.numberMisscheduled == 0)))

		return SystemAll(name=f"daemonset {daemonset.name}", scanners=[count_sensor, misscheduled_sensor, pod_sensor])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/apis/apps/v1/daemonsets", cls)]


class InstrumentorStatefulsets(InstrumentorKubernetes):
	"""Instrument kubernetes statefulsets"""

	def instrument(self, statefulset: kr8s.objects.StatefulSet) -> Scanner:
		"""Instrument a statefulset"""
		count_sensor = replica_statuses(statefulset.spec.replicas, {"availableReplicas", "currentReplicas", "replicas", "updatedReplicas"}, statefulset.status)
		collision_sensor = SensorConstant(name="collisionCount", val=Status(state=State.from_bool(statefulset.status.collisionCount == 0)))
		pod_sensor = SystemAll(
			name="pods",
			scanners=[InstrumentorPods(self.k8s).instrument_pod(e) for e in self.k8s.children("pods", statefulset.namespace, label_selector=statefulset.spec.selector.matchLabels)],
		)  # TODO: need to filter ownerReferences too

		return SystemAll(name=f"statefulset {statefulset.name}", scanners=[count_sensor, collision_sensor, pod_sensor])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("apis/apps/v1/statefulsets", cls)]


class InstrumentorJobs(InstrumentorKubernetes):
	"""Instrument Kubernetes jobs"""

	def instrument(self, job: kr8s.objects.Job) -> Scanner:
		status_sensors = evaluate_conditions({"Complete"}, set())(job.status.conditions)

		pods = self.k8s.children("pods", job.namespace, label_selector=job.spec.selector.matchLabels)
		if pods:
			pod_sensor = SystemAll(name="pods", scanners=[InstrumentorPods(self.k8s).instrument_pod(e) for e in pods])
		else:
			pod_sensor = SensorConstant.passing(name="pods", messages=[Log(message="No pods found", severity=Severity.INFO)])

		return SystemAll(name=job.name, scanners=[*status_sensors, pod_sensor])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/apis/batch/v1/jobs", cls)]


class InstrumentorServices(InstrumentorKubernetes):
	"""Instrument Kubernetes services"""

	# TODO: Consider using Endpoints resources

	def instrument(self, service: kr8s.objects.Service) -> Scanner:
		"""Instrument a service"""
		if "selector" in service.spec:
			endpoint_pods = self.k8s.children("pods", service.namespace, label_selector=service.spec.selector)
			endpoint_sensors = SystemAny(
				name="enpoints",
				scanners=[InstrumentorPods(self.k8s).instrument_pod(e) for e in endpoint_pods],
			)
		else:
			endpoint_sensors = SensorConstant.passing("endpoints", messages=[Log(message="Service does not use selectors", severity=Severity.INFO)])
		return SystemAll(name=service.name, scanners=[endpoint_sensors])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/api/v1/services", cls)]


class InstrumentorIngresses(InstrumentorKubernetes):
	"""Instrument Kubernetes ingresses"""

	class Path(InstrumentorKubernetes):
		def instrument(self, namespace: str, path):
			"""Instrument a path of an ingress rule"""
			backend = path.backend
			if "service" in backend:
				service = self.k8s.get("services", namespace, backend.service.name)  # the service must exist in the same NS as the ingress
				return InstrumentorServices(self.k8s).instrument_service(service)
			elif "resource" in backend:
				return SensorConstant.passing("resource", [])  # TODO: resolve object references
			else:
				return SensorConstant.passing(f"path {path.path} cannot be instrumented", [])

		@classmethod
		def registrations(cls) -> Registrations:
			return [("/apis/networking.k8s.io/v1/ingresses#path", cls)]

	def instrument(self, ingress: kr8s.objects.Ingress) -> Scanner:
		"""Instrument a Kubernetes ingress"""
		path_sensors = []
		for rule_number, rule in enumerate(ingress.spec.rules):
			for path_number, path in enumerate(rule.http.paths):
				path_sensors.append(
					SystemAll(
						name=f"path {rule_number}:{path_number} {path.path}",
						scanners=[self.instrument_path(ingress.namespace, path)],
					)
				)
		return SystemAll(name=ingress.name, scanners=path_sensors)

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/apis/networking.k8s.io/v1/ingresses", cls), *cls.Path.registrations()]


# class InstrumentorK8s(Instrumentor, BaseModel):
# 	"""Instrument Kubernetes objects"""
#
# 	def instrument(self) -> list[Scanner]:
# 		pass
