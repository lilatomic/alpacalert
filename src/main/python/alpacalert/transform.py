from typing import Sequence

from alpacalert.models import Scanner


class NotFoundException(Exception):
	"""Query wasn't found"""


def find_scanners(scanners: Sequence[Scanner], name: str) -> Sequence[Scanner]:
	"""
	Find a scanner by name
	"""
	if name == "*":
		return scanners

	found = []
	for scanner in scanners:
		if scanner.name == name:
			found.append(scanner)

	if not found:
		raise NotFoundException(f"scanner not found in children {name=} n={len(scanners)}")
	return found


def find_path(scanners: Sequence[Scanner], path: Sequence[str]) -> Sequence[Scanner]:
	"""
	Find a scanner by path
	"""
	children = scanners
	tgts: Sequence[Scanner] = ()

	for i, segment in enumerate(path):
		try:
			tgts = find_scanners(children, segment)
		except NotFoundException as e:
			raise NotFoundException(f"scanner not found in path {i=} {segment=} {path=}") from e

		children = sum((list(tgt.children()) for tgt in tgts), start=[])

	return tgts
