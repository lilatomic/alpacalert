import itertools
import json
import logging
from dataclasses import dataclass, field
from enum import Enum

from alpacalert.models import Log, Scanner, Service, Severity, State, Status, Visualiser

l = logging.getLogger(__name__)


def mk_symbols(passing: str, failing: str, unknown: str):
	return {
		State.PASSING: passing,
		State.FAILING: failing,
		State.UNKNOWN: unknown,
	}


class Show(Enum):
	ALL = "all"
	ONLY_FAILING = "only_failing"


@dataclass
class VisualiserConsole(Visualiser):
	"""Visualise an alpacalert Service to the console"""

	symbols: dict[State, str] = field(default_factory=lambda: mk_symbols(State.PASSING.value, State.FAILING.value, State.UNKNOWN.value))
	show: Show = Show.ALL

	def visualise(self, service: Service):
		"""Visualise an alpacalert Service"""
		return "\n".join(self._visualise_scanner(service, indent=0)) + "\n"

	def _visualise_log(self, log: Log, indent: int) -> str:
		indent_s = "\t" * indent
		return f"{indent_s}- {log.severity.name}: {log.message}"

	def _visualise_scanner(self, scanner: Scanner, indent: int) -> list[str]:
		indent_s = "\t" * indent
		try:
			status = scanner.status()
		except:  # noqa: E722
			ei = {"name": scanner.name, "type": type(scanner).__name__, "children": [str(e) for e in scanner.children()]}
			message = f"Unable to get status for {json.dumps(ei)}"
			l.error(message, exc_info=True)
			status = Status(state=State.UNKNOWN, messages=[Log(message=message, severity=Severity.ERROR)])
		if self.show == Show.ONLY_FAILING and status.state == State.PASSING:
			return []

		this = f"{indent_s}{self.symbols[status.state]} : {scanner.name}"
		logs = [self._visualise_log(log, indent) for log in status.messages]
		children = [self._visualise_scanner(e, indent + 1) for e in scanner.children()]

		return [this, *logs, *itertools.chain.from_iterable(children)]
