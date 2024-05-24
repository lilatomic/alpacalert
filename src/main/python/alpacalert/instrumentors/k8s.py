"""Instrument all Kubernetes objects"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Type

import kr8s

from alpacalert.generic import SensorConstant, SystemAll, SystemAny, status_all
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


Registrations = Iterable[tuple[str, Type[Scanner]]]


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


@dataclass
class SensorKubernetes(ABC):
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


class InstrumentorK8s(Instrumentor):
	def __init__(self, k8s: K8s, instrumentors: dict[str, InstrumentorKubernetes] | None = None):
		self.k8s = k8s

		if instrumentors:
			self.instrumentors = instrumentors

		else:
			self.instrumentors = {}

			default_instrumentors = [
				*SensorNode.registrations(),
				*SensorConfigmaps.registrations(),
				*SensorSecrets.registrations(),
				*SensorStorageclass.registrations(),
				*SensorPVCs.registrations(),
				*SensorPods.registrations(),
				*SensorReplicaSets.registrations(),
				*SensorDeployments.registrations(),
				*SensorDaemonset.registrations(),
				*SensorStatefulsets.registrations(),
				*SensorJob.registrations(),
				*SensorServices.registrations(),
				*SensorIngresses.registrations(),
			]

			for sensor in default_instrumentors:
				self.register_sensor(sensor[0], sensor[1])

	def instrument(self) -> list[Scanner]:
		scanners = []

		for kind, sensor in self.instrumentors.items():
			if "#" in kind:
				continue
			objs = self.k8s.get_all(kind)
			for obj in objs:
				try:
					scanners.append(sensor(self.k8s, obj))
				except Exception as e:
					raise InstrumentorError(f"Failed to instrument {kind=} {obj.name}") from e

		return scanners

	def register_sensor(self, kind_uri: str, instrumentor: InstrumentorKubernetes):
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
class SensorNode(SensorKubernetes, System):
	"""Instrument K8s nodes"""

	node: kr8s.objects.Node

	@property
	def name(self) -> str:
		return f"node {self.node.name}"

	def children(self) -> list[Scanner]:
		"""Instrument a Kubernetes node"""
		return evaluate_conditions({"Ready"}, {"MemoryPressure", "DiskPressure", "PIDPressure"})(self.node.status.conditions)

	status = status_all

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Nodes", cls)]


@dataclass
class SensorConfigmaps(SensorKubernetes, Sensor):
	"""Instrument Kubernetes configmaps. Basically just an existance check"""

	configmap: kr8s.objects.ConfigMap | K8sObjRef

	@property
	def name(self) -> str:
		return f"configmap {self.configmap.name} exists"

	def status(self) -> Status:
		return Status(
			state=State.from_bool(self.k8s.exists("configmap", self.configmap.namespace, self.configmap.name)),
		)

	def children(self) -> list[Scanner]:
		return []

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Configmap", cls)]


@dataclass
class SensorSecrets(SensorKubernetes, Sensor):
	"""Instrument Kubernetes secrets. Basically just an existance check"""

	secret: kr8s.objects.ConfigMap | K8sObjRef

	@property
	def name(self):
		return (f"secret {self.secret.name} exists",)

	def status(self) -> Status:
		return Status(
			state=State.from_bool(self.k8s.exists("secret", self.secret.namespace, self.secret.name)),
		)

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Secret", cls)]

	def children(self) -> list[Scanner]:
		return []


@dataclass
class SensorStorageclass(SensorKubernetes, Sensor):
	"""Instrument Kubernetes storageclass"""

	storageclass: StorageClass | K8sObjRef

	@property
	def name(self):
		return f"storageclass {self.storageclass.name} exists"

	def status(self) -> Status:
		return Status(
			state=State.from_bool(self.k8s.exists("StorageClasses", self.storageclass.namespace, self.storageclass.name)),
		)

	@classmethod
	def registrations(cls) -> Registrations:
		return [("StorageClass", cls)]

	def children(self) -> list[Scanner]:
		return []


@dataclass
class SensorPVCs(SensorKubernetes):
	"""Instrument Kubernetes PVCs"""

	pvc: kr8s.objects.PersistentVolumeClaim

	@property
	def name(self) -> str:
		return f"pvc {self.pvc.name}"

	def children(self) -> list[Scanner]:
		match self.pvc.status.phase:
			case "Pending":
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))
			case "Bound":
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.PASSING))
			case _:
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))

		storageclass_sensor = SensorStorageclass(self.k8s, K8sObjRef("StorageClass", self.pvc.namespace, self.pvc.spec.storageClassName))

		return [phase_sensor, storageclass_sensor]

	status = status_all

	@classmethod
	def registrations(cls) -> Registrations:
		return [("PersistentVolumeClaim", cls)]


@dataclass
class SensorPods(SensorKubernetes, System):
	"""Instrument Kubernetes Pods in a namespace"""

	pod: kr8s.objects.Pod

	@property
	def name(self) -> str:
		return f"pod {self.pod.name}"

	def children(self) -> list[Scanner]:
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
				pod_sensors = evaluate_conditions({"Initialized", "Ready", "ContainersReady", "PodScheduled"}, set())(self.pod.status.conditions)
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))
			case "Unknown":
				pod_sensors = []
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.UNKNOWN))

		if "containerStatuses" in self.pod.status:
			container_sensor = SystemAll(name="containers", scanners=[self.Container(self.k8s, e) for e in self.pod.status.containerStatuses])
		else:
			container_sensor = SensorConstant.failing(name="containers", messages=[])  # TODO: more meaningful recovery
		scanners = [
			*pod_sensors,
			phase_sensor,
			container_sensor,
			SystemAll(name="volumes", scanners=[self.Volume(self.k8s, self.pod, v["name"], v) for v in self.pod.spec.volumes]),
		]
		return scanners

	status = status_all

	@dataclass
	class Container(SensorKubernetes, Sensor):
		container_status: Any

		@property
		def name(self):
			return f"Container status: {self.container_status.name}"

		def status(self) -> Status:
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

			return Status(state=state, messages=[Log(message=message, severity=Severity.INFO)])

		def children(self) -> list[Sensor]:
			return []

		@classmethod
		def registrations(cls) -> Registrations:
			return [("Pods#container", cls)]

	@dataclass
	class Volume(SensorKubernetes, System):
		pod: kr8s.objects.Pod
		volume_name: str
		volume: Any

		@property
		def name(self):
			return f"volume {self.volume_name}"

		def children(self) -> list[Scanner]:
			"""Instrument volumes on a pod"""
			if "configMap" in self.volume:
				configmap = self.k8s.get("configmaps", self.pod.namespace, self.volume["configMap"]["name"])
				return [SystemAll(name="configmap", scanners=[SensorConfigmaps(self.k8s, configmap)])]
			elif "hostPath" in self.volume:
				return [SensorConstant.passing(f"hostMount {self.volume_name}", [])]
			elif "projected" in self.volume:
				return [
					SystemAll(
						name="projected volume",
						scanners=[SensorPods.Volume(self.k8s, self.pod, str(i), v) for i, v in enumerate(self.volume["projected"]["sources"])],
					)
				]
			elif "downwardAPI" in self.volume:
				return [SensorConstant.passing("downwardAPI", [])]  # TODO: validate
			elif "serviceAccountToken" in self.volume:
				return [SensorConstant.passing("serviceAccountToken", [])]  # TODO: include more information on service account
			elif "persistentVolumeClaim" in self.volume:
				pvc = self.k8s.get("pvc", self.pod.namespace, self.volume["persistentVolumeClaim"]["claimName"])
				return [SensorPVCs(self.k8s, pvc)]
			else:
				return [SensorConstant.passing(f"volume {self.volume_name} cannot be instrumented", [])]

		status = status_all

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
class SensorReplicaSets(SensorKubernetes, System):
	"""Instrument kubernetes ReplicaSets"""

	replicaset: kr8s.objects.ReplicaSet

	@property
	def name(self) -> str:
		return f"replicaset {self.replicaset.name}"

	def children(self) -> list[Scanner]:
		"""Instrument a ReplicaSet."""
		count_sensors = replica_statuses(self.replicaset.spec.replicas, {"replicas", "availableReplicas", "readyReplicas"}, self.replicaset.status)
		pod_sensors = SystemAll(
			name="pods",
			scanners=[SensorPods(self.k8s, e) for e in self.k8s.children("pods", self.replicaset.namespace, label_selector=self.replicaset.spec.selector.matchLabels)],
		)  # TODO: need to filter ownerReferences too

		return [count_sensors, pod_sensors]

	status = status_all

	@classmethod
	def registrations(cls) -> Registrations:
		return [("ReplicaSets", cls)]


@dataclass
class SensorDeployments(SensorKubernetes, System):
	"""Instrument kubernetes deployments"""

	deployment: kr8s.objects.Deployment

	@property
	def name(self) -> str:
		return f"deployment {self.deployment.name}"

	def children(self) -> list[Scanner]:
		"""Instrument a deployment"""
		status_sensors = evaluate_conditions({"Progressing", "Available"}, set())(self.deployment.status.conditions)
		count_sensor = replica_statuses(self.deployment.spec.replicas, {"replicas", "availableReplicas", "readyReplicas", "updatedReplicas"}, self.deployment.status)
		replicaset_sensor = SystemAll(
			name="replicasets",
			scanners=[
				SensorReplicaSets(self.k8s, e) for e in self.k8s.children("replicasets", self.deployment.namespace, label_selector=self.deployment.spec.selector.matchLabels)
			],
		)
		return [*status_sensors, count_sensor, replicaset_sensor]

	status = status_all

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Deployment", cls)]


@dataclass
class SensorDaemonset(SensorKubernetes, System):
	"""Instrument Kubernetes daemonsets"""

	daemonset: kr8s.objects.DaemonSet

	@property
	def name(self) -> str:
		return f"daemonset {self.daemonset.name}"

	def children(self) -> list[Scanner]:
		count_sensor = replica_statuses(
			self.daemonset.status.desiredNumberScheduled, {"currentNumberScheduled", "numberAvailable", "numberReady", "updatedNumberScheduled"}, self.daemonset.status
		)
		pod_sensor = SystemAll(
			name="pods",
			scanners=[SensorPods(self.k8s, e) for e in self.k8s.children("pods", self.daemonset.namespace, label_selector=self.daemonset.spec.selector.matchLabels)],
		)  # TODO: need to filter ownerReferences too
		misscheduled_sensor = SensorConstant(name="numberMisscheduled", val=Status(state=State.from_bool(self.daemonset.status.numberMisscheduled == 0)))

		return [count_sensor, misscheduled_sensor, pod_sensor]

	status = status_all

	@classmethod
	def registrations(cls) -> Registrations:
		return [("DaemonSet", cls)]


@dataclass
class SensorStatefulsets(SensorKubernetes):
	"""Instrument kubernetes statefulsets"""

	statefulset: kr8s.objects.StatefulSet

	@property
	def name(self) -> str:
		return f"statefulset {self.statefulset.name}"

	def children(self) -> list[Scanner]:
		"""Instrument a statefulset"""
		count_sensor = replica_statuses(self.statefulset.spec.replicas, {"availableReplicas", "currentReplicas", "replicas", "updatedReplicas"}, self.statefulset.status)
		collision_sensor = SensorConstant(name="collisionCount", val=Status(state=State.from_bool(self.statefulset.status.collisionCount == 0)))
		pod_sensor = SystemAll(
			name="pods",
			scanners=[SensorPods(self.k8s, e) for e in self.k8s.children("pods", self.statefulset.namespace, label_selector=self.statefulset.spec.selector.matchLabels)],
		)  # TODO: need to filter ownerReferences too

		return [count_sensor, collision_sensor, pod_sensor]

	status = status_all

	@classmethod
	def registrations(cls) -> Registrations:
		return [("StatefulSet", cls)]


@dataclass
class SensorJob(SensorKubernetes, System):
	"""Instrument Kubernetes jobs"""

	job: kr8s.objects.Job

	@property
	def name(self) -> str:
		return f"job {self.job.name}"

	def children(self) -> list[Scanner]:
		status_sensors = evaluate_conditions({"Complete"}, set())(self.job.status.conditions)

		pods = self.k8s.children("pods", self.job.namespace, label_selector=self.job.spec.selector.matchLabels)
		if pods:
			pod_sensor = SystemAll(name="pods", scanners=[SensorPods(self.k8s, e) for e in pods])
		else:
			pod_sensor = SensorConstant.passing(name="pods", messages=[Log(message="No pods found", severity=Severity.INFO)])

		return [*status_sensors, pod_sensor]

	status = status_all

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Jobs", cls)]


@dataclass
class SensorServices(SensorKubernetes, System):
	"""Instrument Kubernetes services"""

	# TODO: Consider using Endpoints resources
	# TODO: implement this as custom logic? or just status_any

	service: kr8s.objects.Service

	@property
	def name(self):
		return f"service {self.service.name}"

	def children(self) -> list[Scanner]:
		"""Instrument a service"""
		if "selector" in self.service.spec:
			endpoint_pods = self.k8s.children("pods", self.service.namespace, label_selector=self.service.spec.selector)
			endpoint_sensors = [
				SystemAny(
					name="enpoints",
					scanners=[SensorPods(self.k8s, e) for e in endpoint_pods],
				)
			]
		else:
			endpoint_sensors = [SensorConstant.passing("endpoints", messages=[Log(message="Service does not use selectors", severity=Severity.INFO)])]
		return [SystemAll(name=self.service.name, scanners=endpoint_sensors)]

	status = status_all

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Services", cls)]


@dataclass
class SensorIngresses(SensorKubernetes, System):
	"""Instrument Kubernetes ingresses"""

	@dataclass
	class Path(SensorKubernetes, Sensor):
		name: str
		namespace: str
		path: Any

		def status(self) -> Status:
			"""Instrument a path of an ingress rule"""
			backend = self.path.backend
			if "service" in backend:
				service = self.k8s.get("services", self.namespace, backend.service.name)  # the service must exist in the same NS as the ingress
				return SensorServices(self.k8s, service).status()
			elif "resource" in backend:
				return Status(state=State.PASSING)  # TODO: resolve object references
			else:
				return Status(state=State.PASSING, messages=[Log(message=f"path {self.path.path} cannot be instrumented", severity=Severity.INFO)])

		def children(self) -> list[Scanner]:
			backend = self.path.backend
			if "service" in backend:
				service = self.k8s.get("services", self.namespace, backend.service.name)  # the service must exist in the same NS as the ingress
				return [SensorServices(self.k8s, service)]
			else:
				return []

		@classmethod
		def registrations(cls) -> Registrations:
			return [("Ingress#path", cls)]

	ingress: kr8s.objects.Ingress

	@property
	def name(self) -> str:
		return f"ingress {self.ingress.name}"

	def children(self) -> list[Scanner]:
		"""Instrument a Kubernetes ingress"""
		path_sensors = []
		for rule_number, rule in enumerate(self.ingress.spec.rules):
			for path_number, path in enumerate(rule.http.paths):
				path_sensors.append(self.Path(self.k8s, f"path {rule_number}:{path_number} {path.path}", self.ingress.namespace, path))
		return path_sensors

	status = status_all

	@classmethod
	def registrations(cls) -> Registrations:
		return [("Ingress", cls), *cls.Path.registrations()]
