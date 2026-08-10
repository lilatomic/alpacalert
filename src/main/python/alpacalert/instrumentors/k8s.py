"""Instrument all Kubernetes objects"""

import itertools
import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Sequence, Type

import kr8s

from alpacalert.generic import SensorConstant, SystemAll, SystemAny, SystemOptional, status_all
from alpacalert.instrumentor import Instrumentor, InstrumentorError, InstrumentorRegistry, Kind, Registrations
from alpacalert.models import Log, Scanner, Sensor, Severity, State, Status, System, flatten

lc = logging.getLogger("alpacalert.cache")


class StorageClass(kr8s.objects.APIObject):
	"""Kr8s descriptor for StorageClasses"""

	kind = "StorageClass"
	version = "storage.k8s.io/v1"
	_asyncio = False
	endpoint = "storageclasses"
	plural = "storageclasses"
	singular = "storageclass"
	namespaced = False
	scalable = False


def k8skind(kind: str) -> Kind:
	"""Make an Alpacalert Kind for the Kubernetes kind"""
	return Kind("kubernetes.io", kind)


@dataclass
class K8sObjRef:
	"""A reference to a K8s object. Useful for checking if an object exists"""

	kind: str
	namespace: str
	name: str

	def to_query(self):
		return {"kind": self.kind, "namespace": self.namespace, "name": self.name}


@dataclass
class K8s:
	"""Interface to Kubernetes"""

	def __str__(self):
		return f"K8s(context={self.kr8s.api().auth.kubeconfig.current_context})"

	def __repr__(self):
		return str(self)

	kr8s: kr8s.Api

	_cache_get_all: dict[tuple[str, str], dict[str, kr8s._objects.APIObject]] = field(default_factory=lambda: defaultdict(dict))

	def exists(self, kind: str, namespace: str, name: str) -> bool:
		"""Validate that a resource exists"""
		return self.get(kind, namespace, name) is not None

	def _add_to_cache(self, objs: list[kr8s._objects.APIObject]):
		for e in objs:
			self._cache_get_all[(e.kind, e.namespace)][e.name] = e

	def get_all(self, kind: str, namespace: str = kr8s.ALL) -> list:
		"""Get all Kubernetes objects of a kind"""
		k = (kind, namespace)
		if k in self._cache_get_all:
			lc.debug("cache hit %s", k)
			return list(self._cache_get_all[k].values())
		else:
			lc.debug("cache miss %s", k)
			v = list(self.kr8s.get(kind, namespace=namespace))
			self._add_to_cache(v)
			return v

	def get(self, kind: str, namespace: str, name: str) -> Optional[kr8s.objects.APIObject]:
		"""Get a single Kubernetes object"""
		k = (kind, namespace)
		if k not in self._cache_get_all:
			lc.debug("cache miss %s", k)
			self.get_all(kind, namespace)
		else:
			lc.debug("cache hit %s", k)

		result = self._cache_get_all[(kind, namespace)].get(name, None)
		return result
		# raise InstrumentorError(f"Multiple resources found for {kind=} {namespace=} {name=}")

	def children(self, kind: str, namespace: str, label_selector: dict) -> list[kr8s.objects.APIObject]:
		"""Find child objects of a Kubernetes object by their label selector"""
		k = (kind, namespace)
		lc.debug("uncacheable label lookup %s", k)
		return self.kr8s.get(kind, namespace=namespace, label_selector=label_selector)

	@staticmethod
	def _is_owner_ref(ref, owner: kr8s.objects.APIObject) -> bool:
		return ref["kind"] == owner.kind and ref["apiVersion"] == owner.version and ref["name"] == owner.name

	def owned(self, kind: str, namespace: str, owner: kr8s.objects.APIObject) -> list[kr8s.objects.APIObject]:
		"""Find objects that are owned by the object"""
		k = (kind, namespace)
		lc.debug("cacheable owner lookup %s", k)
		objs_of_type = self.get_all(kind, namespace)
		return [e for e in objs_of_type if any(self._is_owner_ref(o, owner) for o in e.metadata.get("ownerReferences", []))]


@dataclass
class SensorKubernetes(Scanner, ABC):
	"""Base for all Kubernetes instrumentors"""

	registry: InstrumentorRegistry
	k8s: K8s

	Registrations = Iterable[tuple[str, Type["SensorKubernetes"]]]

	@classmethod
	@abstractmethod
	def registrations(cls) -> Registrations:
		"""The Instrumentors that should be added for each Kind"""

	def __str__(self):
		return f"{self.__class__.__name__}(name={self.name})"


@dataclass
class InstrumentorK8s(Instrumentor):
	"""Instrument an entire Kubernetes cluster"""

	k8s: K8s
	_registrations: Sequence[Kind]
	k8s_sensor_cls: type[SensorKubernetes]

	def registrations(self) -> Registrations:
		return tuple((e, self) for e in self._registrations)

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		return [self.k8s_sensor_cls(registry, k8s=self.k8s, **kwargs)]

	def __str__(self):
		return f"K8sInstrumentor(k8s={self.k8s})"


class InstrumentorK8sRegistry(InstrumentorRegistry):
	"""Registry of all Kubernetes Instrumentors."""

	def __init__(self, k8s: K8s, sensors: SensorKubernetes.Registrations | None = None):
		super().__init__()
		self.k8s = k8s

		_sensors: SensorKubernetes.Registrations
		if sensors is None:
			_sensors = [
				*SensorCluster.registrations(),
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
				*SensorCronJob.registrations(),
				*SensorJob.registrations(),
				*SensorServices.registrations(),
				*SensorIngresses.registrations(),
			]
		else:
			_sensors = sensors

		for sensor in _sensors:
			kind = k8skind(sensor[0])
			instrumentor = InstrumentorK8s(k8s, (kind,), sensor[1])
			self.register(kind, instrumentor)

	def __str__(self):
		return f"K8sInstrumentor(k8s={self.k8s}, instrumentor_count={len(self.instrumentors)})"


def condition_is(condition, passing_if: bool) -> State:
	"""Evaluate the truthiness of a Kubernetes condition."""
	return State.from_bool(condition["status"].lower() == str(passing_if).lower())


def evaluate_conditions(passing_if_true: set[str], passing_if_false: set[str]) -> Callable[[Sequence[dict]], Sequence[Sensor]]:
	"""Evaluate "conditions" of a Kubernetes object"""

	def evaluate_condition(conditions: Sequence[dict]) -> Sequence[Sensor]:
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
class SensorCluster(SensorKubernetes, System):
	"""Maybe this is fake"""

	cluster: K8sObjRef
	namespace: str = kr8s.ALL

	@property
	def name(self) -> str:
		"""Name"""
		return "cluster"

	def children(self) -> list[Scanner]:
		scanners = []
		for kind, sensor in self.k8s_instrumentors():
			if "#" in kind:
				continue
			objs = self.k8s.get_all(kind, namespace=self.namespace)
			for obj in objs:
				try:
					scanners.append(sensor(self.registry, self.k8s, obj))
				except Exception as e:
					raise InstrumentorError(f"Failed to instrument {kind=} {obj.name}") from e

		return scanners

	status = status_all

	@classmethod
	def k8s_instrumentors(cls):
		"""All kubernetes instrumentors"""
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
			*SensorCronJob.registrations(),
			*SensorServices.registrations(),
			*SensorIngresses.registrations(),
		]
		return default_instrumentors

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("Clusters", cls)]


@dataclass
class SensorNode(SensorKubernetes, System):
	"""Instrument K8s nodes"""

	node: kr8s.objects.Node

	@property
	def name(self) -> str:
		"""Name"""
		return f"node {self.node.name}"

	def children(self) -> Sequence[Scanner]:
		"""Instrument a Kubernetes node"""
		return evaluate_conditions({"Ready"}, {"MemoryPressure", "DiskPressure", "PIDPressure"})(self.node.status.conditions)

	status = status_all

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("Nodes", cls)]


@dataclass
class SensorConfigmaps(SensorKubernetes, Sensor):
	"""Instrument Kubernetes configmaps. Basically just an existance check"""

	configmap: kr8s.objects.ConfigMap | K8sObjRef

	@property
	def name(self) -> str:
		"""Name"""
		return f"configmap {self.configmap.name} exists"

	def status(self) -> Status:
		return Status(
			state=State.from_bool(self.k8s.exists("ConfigMap", self.configmap.namespace, self.configmap.name)),
		)

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("ConfigMap", cls)]


@dataclass
class SensorSecrets(SensorKubernetes, Sensor):
	"""Instrument Kubernetes secrets. Basically just an existance check"""

	secret: kr8s.objects.ConfigMap | K8sObjRef

	@property
	def name(self):
		"""Name"""
		return (f"secret {self.secret.name} exists",)

	def status(self) -> Status:
		return Status(
			state=State.from_bool(self.k8s.exists("Secret", self.secret.namespace, self.secret.name)),
		)

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("Secret", cls)]


@dataclass
class SensorStorageclass(SensorKubernetes, Sensor):
	"""Instrument Kubernetes storageclass"""

	storageclass: StorageClass | K8sObjRef

	@property
	def name(self):
		"""Name"""
		return f"storageclass {self.storageclass.name} exists"

	def status(self) -> Status:
		return Status(state=State.from_bool(self.k8s.exists("StorageClass", self.storageclass.namespace, self.storageclass.name)))

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("StorageClass", cls)]


@dataclass
class SensorPVCs(SensorKubernetes):
	"""Instrument Kubernetes PVCs"""

	pvc: kr8s.objects.PersistentVolumeClaim

	@property
	def name(self) -> str:
		"""Name"""
		return f"pvc {self.pvc.name}"

	def children(self) -> list[Scanner]:
		match self.pvc.status.phase:
			case "Pending":
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))
			case "Bound":
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.PASSING))
			case _:
				phase_sensor = SensorConstant(name="phase", val=Status(state=State.FAILING))

		storage_class_ref = K8sObjRef("StorageClass", self.pvc.namespace, self.pvc.spec.storageClassName)
		storageclass_sensors = self.registry.instrument(k8skind("StorageClass"), storageclass=storage_class_ref)

		return [phase_sensor, *storageclass_sensors]

	status = status_all

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("PersistentVolumeClaim", cls)]


@dataclass
class SensorPods(SensorKubernetes, System):
	"""Instrument Kubernetes Pods in a namespace"""

	pod: kr8s.objects.Pod

	@property
	def name(self) -> str:
		"""Name"""
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

		container_sensor = self._instrument_containerlike(initcontainers=False)
		initcontainer_sensor = self._instrument_containerlike(initcontainers=True)

		scanners = [
			*pod_sensors,
			phase_sensor,
			*container_sensor,
			*initcontainer_sensor,
			SystemAll(
				name="volumes", scanners=flatten([self.registry.instrument(k8skind("Pod#volume"), pod=self.pod, volume_name=v["name"], volume=v) for v in self.pod.spec.volumes])
			),
		]
		return scanners

	def _instrument_containerlike(self, initcontainers: bool) -> list[Scanner]:
		container_sensors = []
		_status_key = "initContainerStatuses" if initcontainers else "containerStatuses"
		container_statuses = {e["name"]: e for e in self.pod.status.get(_status_key, [])}
		containers = self.pod.spec.get("initContainers", []) if initcontainers else self.pod.spec.containers
		for container in containers:
			container_sensors.append(
				self.registry.instrument(k8skind("Pod#container"), pod=self.pod, container=container, container_status=container_statuses.get(container["name"]))
			)

		sensor_name = "init containers" if initcontainers else "containers"
		if container_sensors:
			return [SystemAll(name=sensor_name, scanners=flatten(container_sensors))]
		else:
			if initcontainers:
				return []
			else:
				return [SensorConstant.failing(name="containers", messages=[])]

	status = status_all

	@dataclass
	class Container(SensorKubernetes, System):
		"""A container within a pod."""

		container: dict
		pod: kr8s.objects.Pod
		container_status: Any

		@property
		def name(self):
			"""Name"""
			return f"Container status: {self.container.name}"

		status = status_all

		def lifecycle_status(self) -> Status:
			"""Instrument a container"""
			# TODO: add state as message
			if "running" in self.container_status.state:
				state = State.from_bool(self.container_status.ready and self.container_status.started)
				messages = [Log(message="running", severity=Severity.INFO)]
			elif "terminated" in self.container_status.state:
				# 'ready' is not relevant for terminated containers, the exit code is sufficient
				exit_code = self.container_status.get("state", {}).get("terminated", {}).get("exitCode")
				termination_reason = self.container_status.get("state", {}).get("terminated", {}).get("reason")
				terminated_successfully = exit_code == 0
				state = State.from_bool(not self.container_status.started and terminated_successfully)
				if not terminated_successfully:
					messages = [Log(message=f"exited with exit code {exit_code} (reason: {termination_reason})", severity=Severity.ERROR)]
				else:
					messages = [Log(message=f"terminated successfully with exit code {exit_code} (reason: {termination_reason})", severity=Severity.INFO)]
			elif "waiting" in self.container_status.state:
				state = State.FAILING
				details = self.container_status.state.waiting
				if "reason" in details:
					if details.reason == "ImagePullBackOff":
						messages = [Log(message=json.dumps(details), severity=Severity.ERROR)]
					else:
						messages = [Log(message=details.reason, severity=Severity.INFO)]
				else:
					messages = [Log(message="waiting", severity=Severity.INFO)]
			else:
				state = State.UNKNOWN
				messages = [Log(message="unknown state", severity=Severity.INFO)]

			return Status(state=state, messages=messages)

		def children(self) -> list[Sensor]:
			o: list[Scanner] = [SensorConstant("container_status", self.lifecycle_status())]
			for volume_mount in self.container.get("volumeMounts", []):
				o.extend(self.registry.instrument(k8skind("Pod#volumemount"), pod=self.pod, mount=volume_mount))
			return o

		@classmethod
		def registrations(cls) -> SensorKubernetes.Registrations:
			return [("Pod#container", cls)]

	@dataclass
	class Volume(SensorKubernetes, System):
		"""A volume mounted by a pod."""

		pod: kr8s.objects.Pod
		volume_name: str
		volume: Any
		is_projection: bool = False  # projected volumes have a slightly different schema

		@property
		def name(self):
			"""Name"""
			return f"volume {self.volume_name}"

		@staticmethod
		def _optional_volume(s: Scanner, optional: bool) -> list[Scanner]:
			if optional:
				return [SystemOptional(name="optional", scanner=s)]
			else:
				return [s]

		# pylint: disable=too-many-return-statements
		def children(self) -> list[Scanner]:
			"""Instrument volumes on a pod"""

			if "configMap" in self.volume:
				sensor = SystemAll(
					name="configmap",
					scanners=flatten([(self.registry.instrument(k8skind("ConfigMap"), configmap=K8sObjRef("ConfigMap", self.pod.namespace, self.volume["configMap"]["name"])))]),
				)
				return self._optional_volume(sensor, optional=self.volume["configMap"].get("optional", False))
			elif "secret" in self.volume:
				tok_secret_name = "secretName" if not self.is_projection else "name"
				sensor = SystemAll(
					name="secret",
					scanners=flatten([(self.registry.instrument(k8skind("Secret"), secret=K8sObjRef("Secret", self.pod.namespace, self.volume["secret"][tok_secret_name])))]),
				)
				return self._optional_volume(sensor, optional=self.volume["secret"].get("optional", False))
			elif "hostPath" in self.volume:
				return [SensorConstant.passing(f"hostMount {self.volume_name}", [])]
			elif "projected" in self.volume:
				return [
					SystemAll(
						name="projected volume",
						scanners=flatten(
							[self.registry.instrument(k8skind("Pod#volume"), pod=self.pod, volume_name=str(i), volume=v, is_projection=True) for i, v in enumerate(self.volume["projected"]["sources"])]
						),
					)
				]
			elif "downwardAPI" in self.volume:
				return [SensorConstant.passing("downwardAPI", [])]  # TODO: validate
			elif "serviceAccountToken" in self.volume:
				return [SensorConstant.passing("serviceAccountToken", [])]  # TODO: include more information on service account
			elif "persistentVolumeClaim" in self.volume:
				pvc = self.k8s.get("PersistentVolumeClaim", self.pod.namespace, self.volume["persistentVolumeClaim"]["claimName"])
				return self.registry.instrument(k8skind("PersistentVolumeClaim"), pvc=pvc)
			else:
				return [SensorConstant.passing(f"volume {self.volume_name} cannot be instrumented", [])]

		status = status_all

		@classmethod
		def registrations(cls) -> SensorKubernetes.Registrations:
			return [("Pod#volume", cls)]

	@dataclass
	class VolumeSubPath(SensorKubernetes, Sensor):
		pod: kr8s.objects.Pod
		path: str
		volume: Any

		@property
		def name(self):
			return f"volume {self.volume['name']} subpath {self.path}"

		def status(self) -> Status:
			target = self.get_target(self.volume)
			if not target:
				return Status(state=State.FAILING, messages=[Log(message="volume not found", severity=Severity.ERROR)])

			return self.find_path(self.keyset(target))

		def get_target(self, volume, is_projection: bool = False) -> list[kr8s.objects.APIObject]:
			if "secret" in volume:
				tok_secret_name = "secretName" if not is_projection else "name"
				return [self.k8s.get("Secret", self.pod.namespace, volume["secret"][tok_secret_name])]
			elif "configMap" in volume:
				return [self.k8s.get("ConfigMap", self.pod.namespace, volume["configMap"]["name"])]
			elif "projected" in volume:
				return itertools.chain.from_iterable([self.get_target(nested, is_projection=True) for nested in volume["projected"]["sources"]])
			else:
				return []

		def keyset(self, target: list[kr8s.objects.APIObject]) -> set[str]:
			o = set()
			for t in target:
				o.update(t.raw.get("data", {}))
				o.update(t.raw.get("binaryData", {}))
			return o

		def find_path(self, keyset) -> Status:
			if not keyset:
				return Status(state=State.FAILING, messages=[Log(message=f"volume {self.volume.name} has no data", severity=Severity.ERROR)])

			if self.path not in keyset:
				return Status(state=State.FAILING, messages=[Log(message=f"volume {self.volume.name} has no key {self.path}", severity=Severity.ERROR)])
			return Status(state=State.PASSING, messages=[Log(message=f"volume {self.volume.name} has key {self.path}", severity=Severity.INFO)])

		@classmethod
		def registrations(cls) -> SensorKubernetes.Registrations:
			return [("Pod#volumesubpath", cls)]

	@dataclass
	class VolumeMount(SensorKubernetes, System):
		"""A volume mounted into a container"""

		pod: kr8s.objects.Pod
		mount: Any

		@property
		def name(self) -> str:
			return f"mount {self.mount['name']}"

		status = status_all

		def children(self) -> Sequence[Scanner]:
			scanners = []
			target_volume_name = self.mount["name"]

			defined_volumes = {v.get("name"): v for v in self.pod.spec.volumes}
			if target_volume_name not in defined_volumes:
				return [SensorConstant.failing(f"volume {target_volume_name} is defined", [Log(message="volume is not defined in the spec", severity=Severity.ERROR)])]
			else:
				volume = defined_volumes[target_volume_name]
				presence_sensor = SensorConstant(name=f"volume {target_volume_name} is defined", val=Status(state=State.PASSING))
				scanners.append(presence_sensor)

			if "subPath" in self.mount:
				scanners.extend(self.registry.instrument(k8skind("Pod#volumesubpath"), pod=self.pod, path=self.mount["subPath"], volume=volume))

			return [*scanners, *self.registry.instrument(k8skind("Pod#volume"), pod=self.pod, volume_name=target_volume_name, volume=volume)]

		@classmethod
		def registrations(cls) -> SensorKubernetes.Registrations:
			return [("Pod#volumemount", cls)]

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [
			("Pod", cls),
			*cls.Container.registrations(),
			*cls.Volume.registrations(),
			*cls.VolumeMount.registrations(),
			*cls.VolumeSubPath.registrations(),
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
		"""Name"""
		return f"replicaset {self.replicaset.name}"

	def children(self) -> list[Scanner]:
		"""Instrument a ReplicaSet."""
		if self.replicaset.spec.replicas:
			count_sensors = replica_statuses(self.replicaset.spec.replicas, {"replicas", "availableReplicas", "readyReplicas"}, self.replicaset.status)
			pod_sensors = SystemAll(
				name="pods",
				scanners=flatten(
					[
						self.registry.instrument(k8skind("Pod"), pod=e)
						for e in self.k8s.children("Pod", self.replicaset.namespace, label_selector=self.replicaset.spec.selector.matchLabels)
					]
				),
			)  # TODO: need to filter ownerReferences too
		else:
			count_sensors = replica_statuses(self.replicaset.spec.replicas, {"replicas"}, self.replicaset.status)
			pod_sensors = SensorConstant.passing("pods", [Log(message="replicaset requests no pods", severity=Severity.INFO)])

		return [count_sensors, pod_sensors]

	status = status_all

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("ReplicaSet", cls)]


@dataclass
class SensorDeployments(SensorKubernetes, System):
	"""Instrument kubernetes deployments"""

	deployment: kr8s.objects.Deployment

	@property
	def name(self) -> str:
		"""Name"""
		return f"deployment {self.deployment.name}"

	def children(self) -> list[Scanner]:
		"""Instrument a deployment"""
		status_sensors = evaluate_conditions({"Progressing", "Available"}, set())(self.deployment.status.conditions)
		count_sensor = replica_statuses(self.deployment.spec.replicas, {"replicas", "availableReplicas", "readyReplicas", "updatedReplicas"}, self.deployment.status)
		replicaset_sensor = SystemAll(
			name="replicasets",
			scanners=flatten(
				[
					self.registry.instrument(k8skind("ReplicaSet"), replicaset=e)
					for e in self.k8s.children("ReplicaSet", self.deployment.namespace, label_selector=self.deployment.spec.selector.matchLabels)
				]
			),
		)
		return [*status_sensors, count_sensor, replicaset_sensor]

	status = status_all

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("Deployment", cls)]


@dataclass
class SensorDaemonset(SensorKubernetes, System):
	"""Instrument Kubernetes daemonsets"""

	daemonset: kr8s.objects.DaemonSet

	@property
	def name(self) -> str:
		"""Name"""
		return f"daemonset {self.daemonset.name}"

	def children(self) -> list[Scanner]:
		count_sensor = replica_statuses(
			self.daemonset.status.desiredNumberScheduled, {"currentNumberScheduled", "numberAvailable", "numberReady", "updatedNumberScheduled"}, self.daemonset.status
		)
		pod_sensor = SystemAll(
			name="pods",
			scanners=flatten(
				[
					self.registry.instrument(k8skind("Pod"), pod=e)
					for e in self.k8s.children("Pod", self.daemonset.namespace, label_selector=self.daemonset.spec.selector.matchLabels)
				]
			),
		)  # TODO: need to filter ownerReferences too
		misscheduled_sensor = SensorConstant(name="numberMisscheduled", val=Status(state=State.from_bool(self.daemonset.status.numberMisscheduled == 0)))

		return [count_sensor, misscheduled_sensor, pod_sensor]

	status = status_all

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("DaemonSet", cls)]


@dataclass
class SensorStatefulsets(SensorKubernetes):
	"""Instrument kubernetes statefulsets"""

	statefulset: kr8s.objects.StatefulSet

	@property
	def name(self) -> str:
		"""Name"""
		return f"statefulset {self.statefulset.name}"

	def children(self) -> list[Scanner]:
		"""Instrument a statefulset"""
		count_sensor = replica_statuses(self.statefulset.spec.replicas, {"availableReplicas", "currentReplicas", "replicas", "updatedReplicas"}, self.statefulset.status)
		collision_sensor = SensorConstant(name="collisionCount", val=Status(state=State.from_bool(self.statefulset.status.collisionCount == 0)))
		pod_sensor = SystemAll(
			name="pods",
			scanners=flatten(
				[
					self.registry.instrument(k8skind("Pod"), pod=e)
					for e in self.k8s.children("Pod", self.statefulset.namespace, label_selector=self.statefulset.spec.selector.matchLabels)
				]
			),
		)  # TODO: need to filter ownerReferences too

		return [count_sensor, collision_sensor, pod_sensor]

	status = status_all

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("StatefulSet", cls)]


@dataclass
class SensorJob(SensorKubernetes, System):
	"""Instrument Kubernetes jobs"""

	job: kr8s.objects.Job

	@property
	def name(self) -> str:
		"""Name"""
		return f"job {self.job.name}"

	def children(self) -> list[Scanner]:
		status_sensors = evaluate_conditions({"Complete"}, set())(self.job.status.conditions)

		pods = self.k8s.children("Pod", self.job.namespace, label_selector=self.job.spec.selector.matchLabels)
		if pods:
			pod_sensor = SystemAll(name="pods", scanners=flatten([self.registry.instrument(k8skind("Pod"), pod=e) for e in pods]))
		else:
			pod_sensor = SensorConstant.passing(name="pods", messages=[Log(message="No pods found", severity=Severity.INFO)])

		return [*status_sensors, pod_sensor]

	status = status_all

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("Job", cls)]


@dataclass
class SensorCronJob(SensorKubernetes, System):
	cronjob: kr8s.objects.CronJob

	@property
	def name(self) -> str:
		"""Name"""
		return f"cronjob {self.cronjob.name}"

	def children(self) -> list[Scanner]:
		jobs = self.k8s.owned("Job", self.cronjob.namespace, self.cronjob)
		return [SystemAll(name="jobs", scanners=flatten(self.registry.instrument(k8skind("Job"), job=e) for e in jobs))]

	status = status_all

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("CronJob", cls)]


@dataclass
class SensorServices(SensorKubernetes, System):
	"""Instrument Kubernetes services"""

	# TODO: Consider using Endpoints resources
	# TODO: implement this as custom logic? or just status_any

	service: kr8s.objects.Service

	@property
	def name(self):
		"""Name"""
		return f"service {self.service.name}"

	def children(self) -> Sequence[Scanner]:
		"""Instrument a service"""
		if "selector" in self.service.spec:
			endpoint_pods = self.k8s.children("Pod", self.service.namespace, label_selector=self.service.spec.selector)
			endpoint_sensors = [
				SystemAny(
					name="enpoints",
					scanners=flatten([self.registry.instrument(k8skind("Pod"), pod=e) for e in endpoint_pods]),
				)
			]
		else:
			endpoint_sensors = [SensorConstant.passing("endpoints", messages=[Log(message="Service does not use selectors", severity=Severity.INFO)])]
		return [SystemAll(name=self.service.name, scanners=endpoint_sensors)]

	status = status_all

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("Service", cls)]


@dataclass
class SensorIngresses(SensorKubernetes, System):
	"""Instrument Kubernetes ingresses"""

	@dataclass
	class Path(SensorKubernetes, System):
		"""A path within an Ingress"""

		name: str
		namespace: str
		path: Any

		def status(self) -> Status:
			"""Instrument a path of an ingress rule"""
			backend = self.path.backend
			if "service" in backend:
				# TODO: use children like normal?
				service = self.k8s.get("Service", self.namespace, backend.service.name)  # the service must exist in the same NS as the ingress
				if service is None:
					return Status(state=State.FAILING, messages=[Log(message=f"service {backend.service.name} exist", severity=Severity.ERROR)])
				return SystemAll(name=service.name, scanners=self.registry.instrument(k8skind("Service"), service=service)).status()
			elif "resource" in backend:
				return Status(state=State.PASSING)  # TODO: resolve object references
			else:
				return Status(state=State.PASSING, messages=[Log(message=f"path {self.path.path} cannot be instrumented", severity=Severity.INFO)])

		def children(self) -> list[Scanner]:
			backend = self.path.backend
			if "service" in backend:
				service = self.k8s.get("Service", self.namespace, backend.service.name)  # the service must exist in the same NS as the ingress
				return flatten([self.registry.instrument(k8skind("Service"), service=service)])
			else:
				return []

		@classmethod
		def registrations(cls) -> SensorKubernetes.Registrations:
			return [("Ingress#path", cls)]

	ingress: kr8s.objects.Ingress

	@property
	def name(self) -> str:
		"""Name"""
		return f"ingress {self.ingress.name}"

	def children(self) -> list[Scanner]:
		"""Instrument a Kubernetes ingress"""
		path_sensors = []
		for rule_number, rule in enumerate(self.ingress.spec.rules):
			for path_number, path in enumerate(rule.http.paths):
				path_sensors.append(
					self.registry.instrument(k8skind("Ingress#path"), name=f"path {rule_number}:{path_number} {path.path}", namespace=self.ingress.namespace, path=path)
				)
		return flatten(path_sensors)

	status = status_all

	@classmethod
	def registrations(cls) -> SensorKubernetes.Registrations:
		return [("Ingress", cls), *cls.Path.registrations()]
