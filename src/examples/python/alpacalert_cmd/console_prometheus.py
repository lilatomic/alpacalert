import datetime

import click
from alpacalert.instrumentors.prometheus import PrometheusApi
from alpacalert.visualisers.console import Show, VisualiserConsole, mk_symbols
from requests import Session


@click.command
@click.option("--show", type=click.Choice([e.value for e in Show]), help="What to display", default=Show.ALL.value)
def prometheus(show):
	show = Show(show)
	v = VisualiserConsole(symbols=mk_symbols("✅", "❌", "❔"), show=show)

	session = Session()

	p = PrometheusApi(session=session, base_url="http://localhost:9090")

	r = p.query_instant("container_memory_rss", datetime.datetime.now(datetime.UTC))

	print({e.metric["pod"]: e.value[1] for e in r.data.result})


if __name__ == "__main__":
	prometheus()
