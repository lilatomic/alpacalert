# pylint: disable=redefined-outer-name,missing-module-docstring,missing-function-docstring,unused-argument

import pytest

from alpacalert.conftest import SensorRaises
from alpacalert.generic import SensorConstant, SystemAll, SystemOptional
from alpacalert.models import State


class TestState:
	@pytest.mark.parametrize(
		"state1, state2, expected",
		[
			(State.PASSING, State.PASSING, State.PASSING),
			(State.PASSING, State.FAILING, State.FAILING),
			(State.PASSING, State.UNKNOWN, State.UNKNOWN),
			(State.FAILING, State.PASSING, State.FAILING),
			(State.FAILING, State.FAILING, State.FAILING),
			(State.FAILING, State.UNKNOWN, State.FAILING),
			(State.UNKNOWN, State.PASSING, State.UNKNOWN),
			(State.UNKNOWN, State.FAILING, State.FAILING),
			(State.UNKNOWN, State.UNKNOWN, State.UNKNOWN),
		],
	)
	def test_and_operation(self, state1, state2, expected):
		assert state1 & state2 == expected
		assert state2 & state1 == expected

	@pytest.mark.parametrize(
		"state1, state2, expected",
		[
			(State.PASSING, State.PASSING, State.PASSING),
			(State.PASSING, State.FAILING, State.PASSING),
			(State.PASSING, State.UNKNOWN, State.PASSING),
			(State.FAILING, State.PASSING, State.PASSING),
			(State.FAILING, State.FAILING, State.FAILING),
			(State.FAILING, State.UNKNOWN, State.UNKNOWN),
			(State.UNKNOWN, State.PASSING, State.PASSING),
			(State.UNKNOWN, State.FAILING, State.UNKNOWN),
			(State.UNKNOWN, State.UNKNOWN, State.UNKNOWN),
		],
	)
	def test_or_operation(self, state1, state2, expected):
		assert state1 | state2 == expected
		assert state2 | state1 == expected


class TestSystemOptional:
	def test_passes_when_child_failing(self):
		s = SystemOptional(name="test", scanner=SensorConstant.failing("test-sensor", []))
		assert s.status().state == State.PASSING

	def test_registers_passing_as_child(self):
		s = SystemOptional(name="test", scanner=SensorConstant.failing("test-sensor", []))
		parent = SystemAll(name="test-parent", scanners=[s])
		assert parent.status().state == State.PASSING

	def test_passing_when_child_raises(self):
		s = SystemOptional(name="test", scanner=SensorRaises())
		parent = SystemAll(name="test-parent", scanners=[s])
		assert parent.status().state == State.PASSING
