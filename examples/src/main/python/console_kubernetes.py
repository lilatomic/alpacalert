#!/usr/bin/env python3
"""A quick console application to check the health of a Kubernetes cluster."""

import kr8s
from alpacalert.generic import ServiceBasic, SystemAll
from alpacalert.instrumentor import Kind
from alpacalert.instrumentors.k8s import InstrumentorK8sRegistry, K8s
from alpacalert.visualisers.console import VisualiserConsole, mk_symbols


if __name__ == "__main__":
	v = VisualiserConsole(symbols=mk_symbols("✅", "❌", "❔"))
	k8s = K8s(kr8s)

	instrumentor = InstrumentorK8sRegistry(k8s)
	systems = instrumentor.instrument(Kind("kubernetes.io", "Clusters"), "kind-kind")

	my_cluster = ServiceBasic(name="cluster kind-kind", system=SystemAll(name="cluster kind-kind", scanners=systems))

	print(v.visualise(my_cluster))