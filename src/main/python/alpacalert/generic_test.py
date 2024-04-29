import pytest

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
