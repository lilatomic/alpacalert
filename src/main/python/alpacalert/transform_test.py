from typing import Sequence

import pytest

from alpacalert.generic import SensorConstant, SystemAll
from alpacalert.models import Scanner, Sensor
from alpacalert.transform import NotFoundException, find_scanners, find_path


@pytest.fixture
def scanners() -> Sequence[Scanner]:
	return [
		SensorConstant.passing(name="S0", messages=[]),
		SensorConstant.passing(name="S1", messages=[]),
		SensorConstant.passing(name="Duplicate", messages=[]),
		SensorConstant.passing(name="Duplicate", messages=[]),
	]


class TestFind:
	def test_notfound(self, scanners: Sequence[Scanner]):
		with pytest.raises(NotFoundException):
			find_scanners(scanners, "DNE")

	def test_found(self, scanners: Sequence[Scanner]):
		assert find_scanners(scanners, "S0") == [scanners[0]]
		
	def test_star(self, scanners: Sequence[Scanner]):
		assert len(find_scanners(scanners, "*")) == len(scanners)

	def test_multiple(self, scanners: Sequence[Scanner]):
		assert len(find_scanners(scanners, "Duplicate")) == 2


@pytest.fixture
def scanners_tree(scanners: Sequence[Scanner]) -> Sequence[Scanner]:
	return [
		SensorConstant.passing(name="R0", messages=[]),
		SystemAll(name="N0", scanners=list(scanners)),
		SystemAll(name="N1", scanners=[SensorConstant.passing("N1.0", messages=[])]),
	]


class TestPath:
	def test_notfound(self, scanners_tree):
		with pytest.raises(NotFoundException):
			find_path(scanners_tree, ["DNE"])

	def test_notfound_at_path(self, scanners_tree):
		"""Test that an item which is at the root but not at the path is not found"""
		with pytest.raises(NotFoundException):
			find_path(scanners_tree, ["N0", "R0"])

	def test_at_root(self, scanners_tree):
		assert find_path(scanners_tree, ["R0"]) == [scanners_tree[0]]

	def test_at_path(self, scanners_tree, scanners):
		assert find_path(scanners_tree, ["N0", "S0"]) == [scanners[0]]

	def test_star_nonterminal(self, scanners_tree, scanners):
		found = find_path(scanners_tree, ["*", "N1.0"])
		assert len(found) == 1
		assert found[0].name == "N1.0"
