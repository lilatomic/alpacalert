import itertools

from pydantic import BaseModel

from alpacalert.models import Scanner, Service


class ConsoleVisualiser(BaseModel):
	"""Visualise an alpacalert Service to the console"""

	def visualise(self, service: Service):
		"""Visualise an alpacalert Service"""
		return "\n".join(self._visualise_scanner(service, indent=0)) + "\n"

	def _visualise_scanner(self, scanner: Scanner, indent: int) -> list[str]:
		indent_s = "\t" * indent
		this = f"{indent_s}{str(scanner.status().state)} : {scanner.name}"
		children = [self._visualise_scanner(e, indent + 1) for e in scanner.children()]

		return [
			this, *itertools.chain.from_iterable(children)
		]
