#!/usr/bin/env python3
"""A quick console application to check the health of a Kubernetes cluster."""

import logging

import click

import kr8s
from alpacalert.generic import ServiceBasic, SystemAll
from alpacalert.instrumentor import Kind
from alpacalert.instrumentors.k8s import InstrumentorK8sRegistry, K8s
from alpacalert.visualisers.console import VisualiserConsole, mk_symbols, Show

l = logging.getLogger(__name__)

@click.command
@click.option("--show", type=click.Choice([e.value for e in Show]), help="What to display", default=Show.ALL.value)
@click.option("--namespace", type=click.STRING, help="The Kubernetes namespace", default="all")
def k8s(show, namespace):
	show = Show(show)

	logging.basicConfig()

	v = VisualiserConsole(symbols=mk_symbols("✅", "❌", "❔"), show=show)
	k8s = K8s(kr8s)

	instrumentor = InstrumentorK8sRegistry(k8s)
	systems = instrumentor.instrument(Kind("kubernetes.io", "Clusters"), cluster="kind-kind", namespace=namespace)

	my_cluster = ServiceBasic(name="cluster kind-kind", system=SystemAll(name="cluster kind-kind", scanners=systems))

	click.echo(v.visualise(my_cluster))
