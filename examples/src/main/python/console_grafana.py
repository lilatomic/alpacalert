#!/usr/bin/env python3
"""A quick console application to check all your Grafana alerts."""

from alpacalert.generic import ServiceBasic
from alpacalert.instrumentor import Kind
from alpacalert.instrumentors.grafana import GrafanaApi, RegistryGrafana
from alpacalert.visualisers.console import VisualiserConsole, mk_symbols
from requests.sessions import Session

if __name__ == "__main__":
	v = VisualiserConsole(symbols=mk_symbols("✅", "❌", "❔"))
	session = Session()
	session.auth = ("admin", "admin")
	grafana = GrafanaApi("https://play.grafana.org", session)

	registry = RegistryGrafana(grafana)

	systems = registry.instrument(
		Kind("grafana.org/alerts", "grafana"),
	)
	assert len(systems) == 1

	my_cluster = ServiceBasic(name="Grafana play.grafana.org", system=systems[0])

	print(v.visualise(my_cluster))
