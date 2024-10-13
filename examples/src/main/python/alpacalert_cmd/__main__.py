"""CLI-tool demonstrating Alpacalert"""

import click
from alpacalert_cmd import console_grafana, console_kubernetes


@click.group()
def entrypoint():
	...

entrypoint.add_command(console_grafana.grafana)
entrypoint.add_command(console_kubernetes.k8s)

if __name__ == "__main__":
	entrypoint()
