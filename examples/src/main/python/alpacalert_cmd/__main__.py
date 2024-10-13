"""CLI-tool demonstrating Alpacalert"""

import click
from alpacalert_cmd import console_grafana, console_kubernetes


@click.group()
def entrypoint():
	"""alpacalert multitool"""


entrypoint.add_command(console_grafana.grafana)
entrypoint.add_command(console_kubernetes.k8s)
entrypoint.add_command(console_kubernetes.k8s_obj)

if __name__ == "__main__":
	entrypoint()
