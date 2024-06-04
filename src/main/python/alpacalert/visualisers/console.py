import itertools
from dataclasses import dataclass, field

from alpacalert.models import Log, Scanner, Service, Visualiser, Status, State


def mk_symbols(passing: str, failing: str, unknown: str):
	return {
		State.PASSING: passing,
		State.FAILING: failing,
		State.UNKNOWN: unknown,
	}


@dataclass
class VisualiserConsole(Visualiser):
	"""Visualise an alpacalert Service to the console"""

	symbols: dict[State, str] = field(default_factory=lambda: mk_symbols(State.PASSING.value, State.FAILING.value, State.UNKNOWN.value))

	def visualise(self, service: Service):
		"""Visualise an alpacalert Service"""
		return "\n".join(self._visualise_scanner(service, indent=0)) + "\n"

	def _visualise_log(self, log: Log, indent: int) -> str:
		indent_s = "\t" * indent
		return f"{indent_s}- {log.severity.name}: {log.message}"

	def _visualise_scanner(self, scanner: Scanner, indent: int) -> list[str]:
		indent_s = "\t" * indent
		status = scanner.status()
		this = f"{indent_s}{self.symbols[status.state]} : {scanner.name}"
		logs = [self._visualise_log(log, indent) for log in status.messages]
		children = [self._visualise_scanner(e, indent + 1) for e in scanner.children()]

		return [this, *logs, *itertools.chain.from_iterable(children)]
