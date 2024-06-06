#!/usr/bin/env python3
"""A quick console application to check all your Grafana alerts."""

from alpacalert.generic import ServiceBasic, SystemAll
from alpacalert.instrumentor import InstrumentorRegistry, Kind
from alpacalert.instrumentors.grafana import GrafanaApi, GrafanaObjRef, InstrumentorAlert, InstrumentorAlertRule, InstrumentorAlertRuleGroup, InstrumentorGrafana
from alpacalert.visualisers.console import VisualiserConsole, mk_symbols
from requests.sessions import Session

if __name__ == "__main__":
	v = VisualiserConsole(symbols=mk_symbols("✅", "❌", "❔"))
	session = Session()
	session.auth = ("admin", "admin")
	grafana = GrafanaApi("https://play.grafana.org", session)

	ia = InstrumentorAlert(grafana)
	iar = InstrumentorAlertRule(grafana)
	iarg = InstrumentorAlertRuleGroup(grafana)
	ig = InstrumentorGrafana(grafana)

	registry = InstrumentorRegistry(
		dict(
			[
				*ia.registrations(),
				*iar.registrations(),
				*iarg.registrations(),
				*ig.registrations(),
			]
		)
	)

	systems = registry.instrument(Kind("grafana.org/alerts", "grafana"), )
	assert len(systems) == 1

	my_cluster = ServiceBasic(name="Grafana play.grafana.org", system=systems[0])

	print(v.visualise(my_cluster))
