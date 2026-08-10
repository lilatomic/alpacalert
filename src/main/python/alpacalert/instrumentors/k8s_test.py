import kr8s
from kr8s.objects import Pod

from alpacalert.instrumentors.k8s import InstrumentorK8sRegistry, K8s, k8skind
from alpacalert.models import Scanner, State
from alpacalert.visualisers.console import VisualiserConsole


class FakeK8s(K8s):
	def __init__(self, objs):
		super().__init__(None)
		self._add_to_cache(objs)

	def __str__(self):
		return "FakeK8s"


def init(*objs):
	return InstrumentorK8sRegistry(FakeK8s(objs))


v = VisualiserConsole()

cm0 = kr8s.objects.ConfigMap({"metadata": {"name": "test"}, "data": {"key-0": "value-0"}})


class TestVolumeMount:
	def test_no_volumes(self):
		t = {"name": "test-volume"}
		pod = self.mkpod(t, [])
		self.assert_status(init(pod).instrument(k8skind("Pod#volumemount"), pod=pod, mount=t), State.FAILING)

	def test_missing_volume(self):
		t = {"name": "test-volume"}
		pod = self.mkpod(t, [{"name": "test-other", "configMap": {"name": cm0.name}}])
		self.assert_status(init(pod).instrument(k8skind("Pod#volumemount"), pod=pod, mount=t), State.FAILING)

	def test_present_volume(self):
		t = {"name": "test-volume"}
		pod = self.mkpod(t, [{"name": "test-volume", "configMap": {"name": cm0.name}}])
		self.assert_status(init(pod, cm0).instrument(k8skind("Pod#volumemount"), pod=pod, mount=t), State.PASSING)

	def test_subpath_present(self):
		t = {"name": "test-volume", "subPath": "key-0"}
		pod = self.mkpod(t, [{"name": "test-volume", "configMap": {"name": cm0.name}}])
		self.assert_status(init(pod, cm0).instrument(k8skind("Pod#volumemount"), pod=pod, mount=t), State.PASSING)

	def test_subpath_absent(self):
		t = {"name": "test-volume", "subPath": "does_not_exist"}
		pod = self.mkpod(t, [{"name": "test-volume", "configMap": {"name": cm0.name}}])
		self.assert_status(init(pod, cm0).instrument(k8skind("Pod#volumemount"), pod=pod, mount=t), State.FAILING)

	def test_subpath_projected(self):
		t = {"name": "test-volume", "subPath": "key-0"}
		pod = self.mkpod(t, [{"name": "test-volume", "projected": {"sources": [{"configMap": {"name": cm0.name}}]}}])
		self.assert_status(init(pod, cm0).instrument(k8skind("Pod#volumemount"), pod=pod, mount=t), State.PASSING)

	def assert_status(self, r: list[Scanner], expected: State):
		assert len(r) == 1
		[r] = r
		assert r.status().state == expected, VisualiserConsole().visualise(r)

	def mkpod(self, mounts: dict[str, str], volumes: list) -> Pod:
		return kr8s.objects.Pod(
			{"metadata": {"name": "test-pod"}, "spec": {"containers": [{"name": "test-container", "image": "test-image", "volumeMounts": [mounts]}], "volumes": volumes}}
		)
