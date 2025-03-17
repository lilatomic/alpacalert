# pylint: disable=redefined-outer-name,missing-module-docstring,missing-function-docstring,unused-argument

import kr8s
import pytest
from alpacalert.generic import ServiceBasic, SystemAll
from alpacalert.instrumentor import Kind
from alpacalert.instrumentors.k8s import InstrumentorK8sRegistry, K8s
from alpacalert.models import Scanner, State
from alpacalert.transform import NotFoundException, find_path


@pytest.fixture
def k8s() -> list[Scanner]:
	k8s = K8s(kr8s)
	instrumentor = InstrumentorK8sRegistry(k8s)
	systems = instrumentor.instrument(kind=Kind("kubernetes.io", "Clusters"), cluster="kind-kind")

	return [ServiceBasic(name="cluster kind-kind", system=SystemAll(name="cluster kind-kind", scanners=systems))]


def _idx_into(p: list[str] | str):
	_chain = ["cluster kind-kind", "cluster kind-kind", "cluster"]
	if isinstance(p, str):
		return [*_chain, p]
	return [*_chain, *p]


class TestPods:
	def test_pod_pending__unknown_phase(self, k8s):
		[pod] = find_path(k8s, _idx_into("pod pod-pending"))
		[phase] = find_path([pod], ["pod pod-pending", "phase"])
		assert phase.status().state == State.UNKNOWN

	def test_pod_failed__failed(self, k8s):
		[phase] = find_path(k8s, _idx_into(["pod pod-failed", "phase"]))
		assert phase.status().state == State.FAILING

	def test_instrumented_containers(self, k8s):
		"""Assert nested objects are tested"""
		assert len(find_path(k8s, _idx_into(["pod pod-failed", "containers"]))) == 1

	def test_instrumented_volumes(self, k8s):
		"""Assert nested objects are tested"""
		[projected_volume] = find_path(k8s, _idx_into(["pod pod-failed", "volumes", "*", "projected volume"]))
		volumes = [e.children() for e in projected_volume.children()]
		assert volumes[0][0].name == "serviceAccountToken"
		assert volumes[1][0].children()[0].name == "configmap kube-root-ca.crt exists"
		assert volumes[2][0].name == "downwardAPI"


class TestDeployment:
	def test_hierarchy(self, k8s):
		"""Tests that traversing the expected hierarchy can find a valid object"""
		pods = find_path(k8s, _idx_into(["deployment ingress-nginx-controller", "replicasets", "*", "pods", "*"]))
		assert len(pods) == 1
		assert pods[0].name.startswith("pod ingress-nginx-controller")


class TestCronjob:
	def test_hierarchy(self, k8s):
		"""Tests that traversing the expected hierarchy can find a valid object"""
		try:
			pods = find_path(k8s, _idx_into(["cronjob hello", "jobs", "*", "pods", "*"]))
			assert len(pods) > 0  # there might be several from leftover jobs
		except NotFoundException:
			print(k8s)
			raise
