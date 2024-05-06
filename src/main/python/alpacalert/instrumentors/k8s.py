"""Instrument all Kubernetes objects"""

from abc import ABC
from dataclasses import dataclass
from typing import Callable, Optional

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

	cluster_name: str

	@staticmethod
	def instrument_node(node: kr8s.objects.Node) -> Scanner:
		"""Instrument a Kubernetes node"""
		return SystemAll(name=node.name, scanners=evaluate_conditions({"Ready"}, {"MemoryPressure", "DiskPressure", "PIDPressure"})(node.status.conditions))

	def instrument(self) -> list[Scanner]:
		"""Get information about k8s nodes"""
		return [self.instrument_node(node) for node in (self.k8s.get_all("nodes"))]


class InstrumentorConfigmaps(InstrumentorKubernetes):
	"""Instrument Kubernetes configmaps. Basically just an existance check"""

	@staticmethod
	def instrument_configmap(configmap: kr8s.objects.ConfigMap) -> Scanner:
		"""Instrument a Kubernetes configmap"""
		return SensorConstant(name=f"configmap {configmap.name} exists", val=Status(state=State.PASSING))

	def exists(self, namespace: str, name: str) -> Scanner:
		"""Validate that a Kubernetes configmap exists"""
		return SensorConstant(
			name=f"configmap {name} exists",
			val=Status(
				state=State.from_bool(self.k8s.exists("configmap", namespace, name)),
			),
		)

	def instrument(self) -> list[Scanner]:
		return [self.instrument_configmap(configmap) for configmap in self.k8s.get_all("configmaps")]


class InstrumentorSecrets(InstrumentorKubernetes):
	"""Instrument Kubernetes secrets. Basically just an existance check"""

	@staticmethod
	def instrument_secret(secret: kr8s.objects.ConfigMap) -> Scanner:
		"""Instrument a Kubernetes secret"""
		return SensorConstant(name=f"secret {secret.name} exists", val=Status(state=State.PASSING))

	def exists(self, namespace: str, name: str) -> Scanner:
		"""Validate that a secret exists"""
		return SensorConstant(
			name=f"secret {name} exists",
			val=Status(
				state=State.from_bool(self.k8s.exists("secret", namespace, name)),
			),
		)

	def instrument(self) -> list[Scanner]:
		return [self.instrument_secret(secret) for secret in self.k8s.get_all("secrets")]


class InstrumentorStorageclass(InstrumentorKubernetes):
	"""Instrument Kubernetes storageclass"""

	@staticmethod
	def instrument_storageclass(storageclass):
		"""Instrument a Kubernetes storageclass"""

		return SensorConstant(name=f"storageclass {storageclass.name} exists", val=Status(state=State.PASSING))

	def exists(self, namespace: str, name: str) -> Scanner:
		"""Validate that a Kubernetes configmap exists"""
		return SensorConstant(
			name=f"storageclass {name} exists",
			val=Status(
				state=State.from_bool(self.k8s.exists("StorageClasses", namespace, name)),
			),
		)

	def instrument(self) -> list[Scanner]:
		storageclasses = self.k8s.get_all("storageclass")
		return [self.instrument_storageclass(storageclass) for storageclass in storageclasses]


class InstrumentorPVCs(InstrumentorKubernetes):
	"""Instrument Kubernetes PVCs"""

	def instrument_pvc(self, pvc: kr8s.objects.PersistentVolumeClaim) -> Scanner:
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

	def instrument(self) -> list[Scanner]:
		return [self.instrument_pvc(pvc) for pvc in (self.k8s.get_all("pvcs"))]


class InstrumentorPods(InstrumentorKubernetes):
	"""Instrument Kubernetes Pods in a namespace"""

	def instrument_pod(self, pod: kr8s.objects.Pod) -> Scanner:
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

	def instrument_volume(self, pod: kr8s.objects.Pod, volume_name: str, volume) -> Scanner:
		"""Instrument volumes on a pod"""
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

	def instrument(self) -> list[Scanner]:
		pods = self.k8s.get_all("pods")
		return [self.instrument_pod(pod) for pod in pods]


def replica_statuses(target: int, kinds: set[str], status) -> System:
	"""Compute statuses for the number of replicas"""
	return SystemAll(name="replicas", scanners=[SensorConstant(name=kind, val=Status(state=State.from_bool(status.get(kind) == target))) for kind in kinds])


class InstrumentorReplicaSets(InstrumentorKubernetes):
	"""Instrument kubernetes ReplicaSets"""

	def instrument_replicaset(self, replicaset: kr8s.objects.ReplicaSet) -> Scanner:
		"""Instrument a ReplicaSet."""
		count_sensors = replica_statuses(replicaset.spec.replicas, {"replicas", "availableReplicas", "readyReplicas"}, replicaset.status)
		pod_sensors = SystemAll(
			name="pods",
			scanners=[InstrumentorPods(self.k8s).instrument_pod(e) for e in self.k8s.children("pods", replicaset.namespace, label_selector=replicaset.spec.selector.matchLabels)],
		)  # TODO: need to filter ownerReferences too

		return SystemAll(name=replicaset.name, scanners=[count_sensors, pod_sensors])

	def instrument(self) -> list[Scanner]:
		replicasets = self.k8s.get_all("replicasets")
		return [self.instrument_replicaset(replicaset) for replicaset in replicasets]


class InstrumentorDeployments(InstrumentorKubernetes):
	"""Instrument kubernetes deployments"""

	def instrument_deployment(self, deployment: kr8s.objects.Deployment) -> Scanner:
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

	def instrument(self) -> list[Scanner]:
		return [self.instrument_deployment(deployment) for deployment in (self.k8s.get_all("deployments"))]


class InstrumentorDaemonset(InstrumentorKubernetes):
	"""Instrument Kubernetes daemonsets"""

	def instrument_daemonset(self, daemonset: kr8s.objects.DaemonSet) -> Scanner:
		count_sensor = replica_statuses(
			daemonset.status.desiredNumberScheduled, {"currentNumberScheduled", "numberAvailable", "numberReady", "updatedNumberScheduled"}, daemonset.status
		)
		pod_sensor = SystemAll(
			name="pods",
			scanners=[InstrumentorPods(self.k8s).instrument_pod(e) for e in self.k8s.children("pods", daemonset.namespace, label_selector=daemonset.spec.selector.matchLabels)],
		)  # TODO: need to filter ownerReferences too
		misscheduled_sensor = SensorConstant(name="numberMisscheduled", val=Status(state=State.from_bool(daemonset.status.numberMisscheduled == 0)))

		return SystemAll(name=f"daemonset {daemonset.name}", scanners=[count_sensor, misscheduled_sensor, pod_sensor])

	def instrument(self) -> list[Scanner]:
		return [self.instrument_daemonset(e) for e in (self.k8s.get_all("daemonsets"))]


class InstrumentorStatefulsets(InstrumentorKubernetes):
	"""Instrument kubernetes statefulsets"""

	def instrument_statefulset(self, statefulset: kr8s.objects.StatefulSet) -> Scanner:
		"""Instrument a statefulset"""
		count_sensor = replica_statuses(statefulset.spec.replicas, {"availableReplicas", "currentReplicas", "replicas", "updatedReplicas"}, statefulset.status)
		collision_sensor = SensorConstant(name="collisionCount", val=Status(state=State.from_bool(statefulset.status.collisionCount == 0)))
		pod_sensor = SystemAll(
			name="pods",
			scanners=[InstrumentorPods(self.k8s).instrument_pod(e) for e in self.k8s.children("pods", statefulset.namespace, label_selector=statefulset.spec.selector.matchLabels)],
		)  # TODO: need to filter ownerReferences too

		return SystemAll(name=f"statefulset {statefulset.name}", scanners=[count_sensor, collision_sensor, pod_sensor])

	def instrument(self) -> list[Scanner]:
		return [self.instrument_statefulset(statefulset) for statefulset in self.k8s.get_all("statefulsets")]


class InstrumentorJobs(InstrumentorKubernetes):
	"""Instrument Kubernetes jobs"""

	def instrument_job(self, job: kr8s.objects.Job) -> Scanner:
		status_sensors = evaluate_conditions({"Complete"}, set())(job.status.conditions)

		pods = self.k8s.children("pods", job.namespace, label_selector=job.spec.selector.matchLabels)
		if pods:
			pod_sensor = SystemAll(name="pods", scanners=[InstrumentorPods(self.k8s).instrument_pod(e) for e in pods])
		else:
			pod_sensor = SensorConstant.passing(name="pods", messages=[Log(message="No pods found", severity=Severity.INFO)])

		return SystemAll(name=job.name, scanners=[*status_sensors, pod_sensor])

	def instrument(self) -> list[Scanner]:
		return [self.instrument_job(job) for job in self.k8s.get_all("jobs")]


class InstrumentorServices(InstrumentorKubernetes):
	"""Instrument Kubernetes services"""

	# TODO: Consider using Endpoints resources

	def instrument_service(self, service: kr8s.objects.Service) -> Scanner:
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

	def instrument(self) -> list[Scanner]:
		return [self.instrument_service(service) for service in (self.k8s.get_all("services"))]


class InstrumentorIngresses(InstrumentorKubernetes):
	"""Instrument Kubernetes ingresses"""

	def instrument_path(self, namespace: str, path):
		"""Instrument a path of an ingress rule"""
		backend = path.backend
		if "service" in backend:
			service = self.k8s.get("services", namespace, backend.service.name)  # the service must exist in the same NS as the ingress
			return InstrumentorServices(self.k8s).instrument_service(service)
		elif "resource" in backend:
			return SensorConstant.passing("resource", [])  # TODO: resolve object references
		else:
			return SensorConstant.passing(f"path {path.path} cannot be instrumented", [])

	def instrument_ingress(self, ingress: kr8s.objects.Ingress) -> Scanner:
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

	def instrument(self) -> list[Scanner]:
		return [self.instrument_ingress(ingress) for ingress in (self.k8s.get_all("ingresses"))]


# class InstrumentorK8s(Instrumentor, BaseModel):
# 	"""Instrument Kubernetes objects"""
#
# 	def instrument(self) -> list[Scanner]:
# 		pass
