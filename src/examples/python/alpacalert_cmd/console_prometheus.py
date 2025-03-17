
import click
import kr8s
from alpacalert.generic import ServiceBasic, SystemAll
from alpacalert.instrumentor import InstrumentorRegistry, Kind
from alpacalert.instrumentors.k8s import InstrumentorK8sRegistry, K8s
from alpacalert.instrumentors.prometheus import PrometheusApi, RegistryPrometheus
from alpacalert.visualisers.console import Show, VisualiserConsole, mk_symbols
from requests import Session


@click.command
@click.option("--show", type=click.Choice([e.value for e in Show]), help="What to display", default=Show.ALL.value)
def prometheus(show):
	show = Show(show)
	v = VisualiserConsole(symbols=mk_symbols("✅", "❌", "❔"), show=show)

	session = Session()

	p = PrometheusApi(session=session, base_url="http://localhost:9090")

	registry = InstrumentorRegistry()
	registry.extend(InstrumentorK8sRegistry(K8s(kr8s)))
	registry.extend(RegistryPrometheus(p))

	tgt = dict(kind=Kind("kubernetes.io", "Clusters"), cluster="kind-kind", namespace="all")

	systems = registry.instrument(**tgt)

	my_cluster = ServiceBasic(name="cluster kind-kind", system=SystemAll(name="cluster kind-kind", scanners=systems))

	click.echo(v.visualise(my_cluster))


if __name__ == "__main__":
	prometheus()
