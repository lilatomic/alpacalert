# pylint: disable=redefined-outer-name,missing-module-docstring,missing-function-docstring,unused-argument

from textwrap import dedent

from alpacalert.generic import SensorConstant, ServiceBasic, SystemAll, SystemAny
from alpacalert.models import Log, Severity, State, Status
from alpacalert.visualisers.console import VisualiserConsole


def test_console_visualiser():
	"""A basic test of the console visualiser"""
	s = ServiceBasic(
		name="test_service",
		system=SystemAny(
			name="test_system_0",
			scanners=[
				SystemAll(
					name="test_system_1",
					scanners=[
						SensorConstant(name="test_sensor_0", val=Status(state=State.PASSING, messages=[Log(message="test message 0", severity=Severity.WARN)])),
						SensorConstant(name="test_sensor_1", val=Status(state=State.FAILING)),
					],
				),
				SensorConstant(name="test_sensor_2", val=Status(state=State.PASSING)),
			],
		),
	)
	v = VisualiserConsole()

	r = v.visualise(s)

	expected = dedent(
		"""\
		passing : test_service
			passing : test_system_0
				failing : test_system_1
					passing : test_sensor_0
					- WARN: test message 0
					failing : test_sensor_1
				passing : test_sensor_2
		"""
	)

	assert expected == r
