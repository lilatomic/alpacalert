#!/usr/bin/env python3
"""A quick console application to check all your Grafana alerts."""

import json

import click
from alpacalert.generic import ServiceBasic
from alpacalert.instrumentor import Kind
from alpacalert.instrumentors.grafana import GrafanaApi, RegistryGrafana
from alpacalert.visualisers.console import Show, VisualiserConsole, mk_symbols
from requests.sessions import Session


@click.command
@click.option("--cfg", default=json.dumps({"url": "https://play.grafana.org"}))
@click.option("--show", type=click.Choice([e.value for e in Show]), help="What to display", default=Show.ALL.value)
def grafana(cfg, show):
	"""Show alerts for a whole Grafana instance"""
	show = Show(show)
	v = VisualiserConsole(symbols=mk_symbols("✅", "❌", "❔"), show=show)

	cfg = json.loads(cfg)
	session = Session()
	if "auth" in cfg:
		if isinstance(cfg["auth"], list):
			session.auth = tuple(cfg["auth"])
		else:
			session.auth = cfg["auth"]

	registry = RegistryGrafana(GrafanaApi(cfg["url"], session))

	systems = registry.instrument(
		Kind("grafana.org/alerts", "grafana"),
	)
	assert len(systems) == 1

	my_cluster = ServiceBasic(name="Grafana play.grafana.org", system=systems[0])

	click.echo(v.visualise(my_cluster))
