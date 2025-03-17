#!/usr/bin/env python3
"""A quick console application to check the health of a Kubernetes cluster."""

import logging

import click
import kr8s
from alpacalert.generic import ServiceBasic, SystemAll
from alpacalert.instrumentor import Kind
from alpacalert.instrumentors.k8s import InstrumentorK8sRegistry, K8s
from alpacalert.visualisers.console import Show, VisualiserConsole, mk_symbols

l = logging.getLogger(__name__)


def do_show_k8s(show, tgt):
	"""Run Alpacalert on a target in a Kubernetes cluster."""
	v = VisualiserConsole(symbols=mk_symbols("✅", "❌", "❔"), show=show)
	k8s = K8s(kr8s)

	instrumentor = InstrumentorK8sRegistry(k8s)
	systems = instrumentor.instrument(**tgt)

	my_cluster = ServiceBasic(name="cluster kind-kind", system=SystemAll(name="cluster kind-kind", scanners=systems))

	click.echo(v.visualise(my_cluster))


@click.command
@click.option("--show", type=click.Choice([e.value for e in Show]), help="What to display", default=Show.ALL.value)
@click.option("--namespace", type=click.STRING, help="The Kubernetes namespace", default="all")
def k8s(show, namespace):
	"""Run Alpacalert on an entire Kubernetes cluster (or a specific namespace)."""
	show = Show(show)

	do_show_k8s(show, dict(kind=Kind("kubernetes.io", "Clusters"), cluster="kind-kind", namespace=namespace))


@click.command
@click.option("--show", type=click.Choice([e.value for e in Show]), help="What to display", default=Show.ALL.value)
@click.option("--namespace")
@click.option("--kind")
@click.option("--name")
def k8s_obj(show, namespace: str, kind: str, name: str):
	"""Run Alpacalert on a specific resource in a Kubernetes cluster."""
	show = Show(show)
	[obj] = kr8s.get(kind, name, namespace=namespace)

	do_show_k8s(show, {"kind": Kind("kubernetes.io", obj.kind), obj.singular: obj})
