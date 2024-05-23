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
class K8sObjRef:
	"""A reference to a K8s object. Useful for checking if an object exists"""

	kind: str
	namespace: str
	name: str


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

	node: kr8s.objects.Node

	def instrument(self) -> Scanner:
		"""Instrument a Kubernetes node"""
		return SystemAll(name=self.node.name, scanners=evaluate_conditions({"Ready"}, {"MemoryPressure", "DiskPressure", "PIDPressure"})(self.node.status.conditions))

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Nodes", cls)]


@dataclass
class InstrumentorConfigmaps(InstrumentorKubernetes):
	"""Instrument Kubernetes configmaps. Basically just an existance check"""

	configmap: kr8s.objects.ConfigMap

	def instrument(self) -> Scanner:
		"""Instrument a Kubernetes configmap"""
		return SensorConstant(
			name=f"configmap {self.configmap.name} exists",
			val=Status(
				state=State.from_bool(self.k8s.exists("configmap", self.configmap.namespace, self.configmap.name)),
			),
		)

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Configmap", cls)]


@dataclass
class InstrumentorSecrets(InstrumentorKubernetes):
	"""Instrument Kubernetes secrets. Basically just an existance check"""

	secret: kr8s.objects.ConfigMap | K8sObjRef

	def instrument(self) -> Scanner:
		"""Instrument a Kubernetes secret"""
		return SensorConstant(
			name=f"secret {self.secret.name} exists",
			val=Status(
				state=State.from_bool(self.k8s.exists("secret", self.secret["namespace"], self.secret["name"])),
			),
		)

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Secret", cls)]


@dataclass
class InstrumentorStorageclass(InstrumentorKubernetes):
	"""Instrument Kubernetes storageclass"""

	storageclass: StorageClass | K8sObjRef

	def instrument(self):
		"""Instrument a Kubernetes storageclass"""

		return SensorConstant(
			name=f"storageclass {self.storageclass.name} exists",
			val=Status(
				state=State.from_bool(self.k8s.exists("StorageClasses", self.storageclass.namespace, self.storageclass.name)),
			),
		)

	@classmethod
	def registrations(cls) -> Registrations:
		return [("StorageClass", cls)]


@dataclass
class InstrumentorPVCs(InstrumentorKubernetes):
	"""Instrument Kubernetes PVCs"""

	pvc: kr8s.objects.PersistentVolumeClaim

	def instrument(self) -> Scanner:
		"""Instrument a Kubernetes PVC"""
		match self.pvc.status.phase:
			case "Pending":
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))
			case "Bound":
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.PASSING))
			case _:
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))

		storageclass_sensor = InstrumentorStorageclass(self.k8s, K8sObjRef("StorageClass", self.pvc.namespace, self.pvc.spec.storageClassName)).instrument()

		return SystemAll(name=f"pvc {self.pvc.name}", scanners=[phase_sensor, storageclass_sensor])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/app/v1/persistentvolumeclaims", cls)]


@dataclass
class InstrumentorPods(InstrumentorKubernetes):
	"""Instrument Kubernetes Pods in a namespace"""

	pod: kr8s.objects.Pod

	def instrument(self) -> Scanner:
		"""Instrument a Pod"""
		match self.pod.status.phase:
			case "Pending":
				pod_sensors = evaluate_conditions({"PodScheduled"}, set())(self.pod.status.conditions)
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.UNKNOWN))
			case "Running":
				pod_sensors = evaluate_conditions({"Initialized", "Ready", "ContainersReady", "PodScheduled"}, set())(self.pod.status.conditions)
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.PASSING))
			case "Succeeded":
				pod_sensors = evaluate_conditions({"Initialized", "PodScheduled"}, {"Ready", "ContainersReady"})(self.pod.status.conditions)
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.PASSING))
			case "Failed":
				...  # TODO
			case "Unknown":
				...  # TODO

		if "containerStatuses" in self.pod.status:
			container_sensor = SystemAll(name="containers", scanners=[self.Container(self.k8s, e).instrument() for e in self.pod.status.containerStatuses])
		else:
			container_sensor = SensorConstant.failing(name="containers", messages=[])  # TODO: more meaningful recovery
		scanners = [
			*pod_sensors,
			phase_sensor,
			container_sensor,
			SystemAll(name="volumes", scanners=[self.Volume(self.k8s, self.pod, v["name"], v).instrument() for v in self.pod.spec.volumes]),
		]

		return SystemAll(name=f"pod {self.pod.name}", scanners=scanners)

	@dataclass
	class Container(InstrumentorKubernetes):
		container_status: Any

		def instrument(self) -> Scanner:
			"""Instrument a container"""
			# TODO: add state as message
			if "running" in self.container_status.state:
				state = State.from_bool(self.container_status.ready and self.container_status.started)
				message = "running"
			elif "terminated" in self.container_status.state:
				terminated_successfully = self.container_status.get("state", {}).get("terminated", {}).get("reason") == "Completed"
				state = State.from_bool(not self.container_status.ready and not self.container_status.started and terminated_successfully)
				message = "terminated"
			elif "waiting" in self.container_status.state:
				state = State.FAILING
				message = "waiting"
			else:
				state = State.UNKNOWN
				message = "unknown state"

			return SensorConstant(name=f"Container status: {self.container_status.name}", val=Status(state=state, messages=[Log(message=message, severity=Severity.INFO)]))

		@classmethod
		def registrations(cls) -> Registrations:
			return [("Pods#container", cls)]

	@dataclass
	class Volume(InstrumentorKubernetes):
		pod: kr8s.objects.Pod
		volume_name: str
		volume: Any

		def instrument(self) -> Scanner:
			"""Instrument volumes on a pod"""
			if "configMap" in self.volume:
				configmap = self.k8s.get("configmaps", self.pod.namespace, self.volume["configMap"]["name"])
				return SystemAll(name=f"volume {self.volume_name}", scanners=[InstrumentorConfigmaps(self.k8s, configmap).instrument()])
			elif "hostPath" in self.volume:
				return SensorConstant.passing(f"hostMount {self.volume_name}", [])
			elif "projected" in self.volume:
				return SystemAll(
					name=f"projected volume {self.volume_name}",
					scanners=[InstrumentorPods.Volume(self.k8s, self.pod, str(i), v).instrument() for i, v in enumerate(self.volume["projected"]["sources"])],
				)
			elif "downwardAPI" in self.volume:
				return SensorConstant.passing(f"{self.volume_name} downwardAPI", [])  # TODO: validate
			elif "serviceAccountToken" in self.volume:
				return SensorConstant.passing(f"{self.volume_name} serviceAccountToken", [])  # TODO: include more information on service account
			elif "persistentVolumeClaim" in self.volume:
				pvc = self.k8s.get("pvc", self.pod.namespace, self.volume["persistentVolumeClaim"]["claimName"])
				return InstrumentorPVCs(self.k8s, pvc).instrument()
			else:
				return SensorConstant.passing(f"volume {self.volume_name} cannot be instrumented", [])

		@classmethod
		def registrations(cls) -> Registrations:
			return [("Pods#volume", cls)]

	@classmethod
	def registrations(cls) -> Registrations:
		return [
			("Pods", cls),
			*cls.Container.registrations(),
			*cls.Volume.registrations(),
		]


def replica_statuses(target: int, kinds: set[str], status) -> System:
	"""Compute statuses for the number of replicas"""

	# TODO: make a real instrumentor?

	return SystemAll(name="replicas", scanners=[SensorConstant(name=kind, val=Status(state=State.from_bool(status.get(kind) == target))) for kind in kinds])


@dataclass
class InstrumentorReplicaSets(InstrumentorKubernetes):
	"""Instrument kubernetes ReplicaSets"""

	replicaset: kr8s.objects.ReplicaSet

	def instrument(self) -> Scanner:
		"""Instrument a ReplicaSet."""
		count_sensors = replica_statuses(self.replicaset.spec.replicas, {"replicas", "availableReplicas", "readyReplicas"}, self.replicaset.status)
		pod_sensors = SystemAll(
			name="pods",
			scanners=[
				InstrumentorPods(self.k8s, e).instrument() for e in self.k8s.children("pods", self.replicaset.namespace, label_selector=self.replicaset.spec.selector.matchLabels)
			],
		)  # TODO: need to filter ownerReferences too

		return SystemAll(name=self.replicaset.name, scanners=[count_sensors, pod_sensors])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("ReplicaSets", cls)]


@dataclass
class InstrumentorDeployments(InstrumentorKubernetes):
	"""Instrument kubernetes deployments"""

	deployment: kr8s.objects.Deployment

	def instrument(self) -> Scanner:
		"""Instrument a deployment"""
		status_sensors = evaluate_conditions({"Progressing", "Available"}, set())(self.deployment.status.conditions)
		count_sensor = replica_statuses(self.deployment.spec.replicas, {"replicas", "availableReplicas", "readyReplicas", "updatedReplicas"}, self.deployment.status)
		replicaset_sensor = SystemAll(
			name="replicasets",
			scanners=[
				InstrumentorReplicaSets(self.k8s, e).instrument()
				for e in self.k8s.children("replicasets", self.deployment.namespace, label_selector=self.deployment.spec.selector.matchLabels)
			],
		)
		return SystemAll(name=self.deployment.name, scanners=[*status_sensors, count_sensor, replicaset_sensor])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Deployment", cls)]


@dataclass
class InstrumentorDaemonset(InstrumentorKubernetes):
	"""Instrument Kubernetes daemonsets"""

	daemonset: kr8s.objects.DaemonSet

	def instrument(self) -> Scanner:
		count_sensor = replica_statuses(
			self.daemonset.status.desiredNumberScheduled, {"currentNumberScheduled", "numberAvailable", "numberReady", "updatedNumberScheduled"}, self.daemonset.status
		)
		pod_sensor = SystemAll(
			name="pods",
			scanners=[
				InstrumentorPods(self.k8s, e).instrument() for e in self.k8s.children("pods", self.daemonset.namespace, label_selector=self.daemonset.spec.selector.matchLabels)
			],
		)  # TODO: need to filter ownerReferences too
		misscheduled_sensor = SensorConstant(name="numberMisscheduled", val=Status(state=State.from_bool(self.daemonset.status.numberMisscheduled == 0)))

		return SystemAll(name=f"daemonset {self.daemonset.name}", scanners=[count_sensor, misscheduled_sensor, pod_sensor])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/apis/apps/v1/daemonsets", cls)]


@dataclass
class InstrumentorStatefulsets(InstrumentorKubernetes):
	"""Instrument kubernetes statefulsets"""

	statefulset: kr8s.objects.StatefulSet

	def instrument(self) -> Scanner:
		"""Instrument a statefulset"""
		count_sensor = replica_statuses(self.statefulset.spec.replicas, {"availableReplicas", "currentReplicas", "replicas", "updatedReplicas"}, self.statefulset.status)
		collision_sensor = SensorConstant(name="collisionCount", val=Status(state=State.from_bool(self.statefulset.status.collisionCount == 0)))
		pod_sensor = SystemAll(
			name="pods",
			scanners=[
				InstrumentorPods(self.k8s,e).instrument()
				for e in self.k8s.children("pods", self.statefulset.namespace, label_selector=self.statefulset.spec.selector.matchLabels)
			],
		)  # TODO: need to filter ownerReferences too

		return SystemAll(name=f"statefulset {self.statefulset.name}", scanners=[count_sensor, collision_sensor, pod_sensor])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("apis/apps/v1/statefulsets", cls)]


@dataclass
class InstrumentorJobs(InstrumentorKubernetes):
	"""Instrument Kubernetes jobs"""

	job: kr8s.objects.Job

	def instrument(self) -> Scanner:
		status_sensors = evaluate_conditions({"Complete"}, set())(self.job.status.conditions)

		pods = self.k8s.children("pods", self.job.namespace, label_selector=self.job.spec.selector.matchLabels)
		if pods:
			pod_sensor = SystemAll(name="pods", scanners=[InstrumentorPods(self.k8s, e).instrument() for e in pods])
		else:
			pod_sensor = SensorConstant.passing(name="pods", messages=[Log(message="No pods found", severity=Severity.INFO)])

		return SystemAll(name=self.job.name, scanners=[*status_sensors, pod_sensor])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Jobs", cls)]


@dataclass
class InstrumentorServices(InstrumentorKubernetes):
	"""Instrument Kubernetes services"""

	# TODO: Consider using Endpoints resources

	service: kr8s.objects.Service

	def instrument(self) -> Scanner:
		"""Instrument a service"""
		if "selector" in self.service.spec:
			endpoint_pods = self.k8s.children("pods", self.service.namespace, label_selector=self.service.spec.selector)
			endpoint_sensors = SystemAny(
				name="enpoints",
				scanners=[InstrumentorPods(self.k8s, e).instrument() for e in endpoint_pods],
			)
		else:
			endpoint_sensors = SensorConstant.passing("endpoints", messages=[Log(message="Service does not use selectors", severity=Severity.INFO)])
		return SystemAll(name=self.service.name, scanners=[endpoint_sensors])

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Services", cls)]


@dataclass
class InstrumentorIngresses(InstrumentorKubernetes):
	"""Instrument Kubernetes ingresses"""

	@dataclass
	class Path(InstrumentorKubernetes):
		namespace: str
		path: Any

		def instrument(self):
			"""Instrument a path of an ingress rule"""
			backend = self.path.backend
			if "service" in backend:
				service = self.k8s.get("services", self.namespace, backend.service.name)  # the service must exist in the same NS as the ingress
				return [InstrumentorServices(self.k8s, service).instrument()]
			elif "resource" in backend:
				return [SensorConstant.passing("resource", [])]  # TODO: resolve object references
			else:
				return [SensorConstant.passing(f"path {self.path.path} cannot be instrumented", [])]

		@classmethod
		def registrations(cls) -> Registrations:
			return [("/apis/networking.k8s.io/v1/ingresses#path", cls)]

	ingress: kr8s.objects.Ingress

	def instrument(self) -> Scanner:
		"""Instrument a Kubernetes ingress"""
		path_sensors = []
		for rule_number, rule in enumerate(self.ingress.spec.rules):
			for path_number, path in enumerate(rule.http.paths):
				path_sensors.append(
					SystemAll(
						name=f"path {rule_number}:{path_number} {path.path}",
						scanners=self.Path(self.k8s, self.ingress.namespace, path).instrument(),
					)
				)
		return SystemAll(name=self.ingress.name, scanners=path_sensors)

	@classmethod
	def registrations(cls) -> Registrations:
		return [("/apis/networking.k8s.io/v1/ingresses", cls), *cls.Path.registrations()]
