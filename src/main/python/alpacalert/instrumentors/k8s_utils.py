"""
General utilities for Kubernetes
"""

from dataclasses import dataclass

import kr8s

from alpacalert.models import Log, Severity, State, Status


@dataclass
class FindKeyInObject:
	"""Find a key in an object like a Secret or a ConfigMap"""

	name: str
	path: str

	@staticmethod
	def keyset(target: list[kr8s.objects.APIObject]) -> set[str]:
		o = set()
		for t in target:
			o.update(t.raw.get("data", {}))
			o.update(t.raw.get("binaryData", {}))
		return o

	def find_path(self, keyset) -> Status:
		if not keyset:
			return Status(state=State.FAILING, messages=[Log(message=f"{self.name} has no data", severity=Severity.ERROR)])

		if self.path not in keyset:
			return Status(state=State.FAILING, messages=[Log(message=f"{self.name} has no key {self.path}", severity=Severity.ERROR)])
		return Status(state=State.PASSING, messages=[Log(message=f"{self.name} has key {self.path}", severity=Severity.INFO)])

	def find(self, tgts: list[kr8s.objects.APIObject]) -> Status:
		return self.find_path(self.keyset(tgts))
