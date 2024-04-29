import itertools

from alpacalert.models import Log, Scanner, Service, Visualiser


class VisualiserConsole(Visualiser):
	"""Visualise an alpacalert Service to the console"""

	def visualise(self, service: Service):
		"""Visualise an alpacalert Service"""
		return "\n".join(self._visualise_scanner(service, indent=0)) + "\n"

	def _visualise_log(self, log: Log, indent: int) -> str:
		indent_s = "\t" * indent
		return f"{indent_s}- {log.severity.name}: {log.message}"

	def _visualise_scanner(self, scanner: Scanner, indent: int) -> list[str]:
		indent_s = "\t" * indent
		status = scanner.status()
		this = f"{indent_s}{status.state.value} : {scanner.name}"
		logs = [self._visualise_log(log, indent) for log in status.messages]
		children = [self._visualise_scanner(e, indent + 1) for e in scanner.children()]

		return [this, *logs, *itertools.chain.from_iterable(children)]
