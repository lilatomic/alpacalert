from textwrap import dedent

from alpacalert.generic import SensorConstant, ServiceBasic, SystemAll, SystemAny
from alpacalert.models import State, Status
from alpacalert.visualisers.console import ConsoleVisualiser


def test_console_visualiser():
	"""A basic test of the console visualiser"""
	s = ServiceBasic(
		name='test_service',
		system=SystemAny(
			name='test_system_0',
			scanners=[
				SystemAll(
					name='test_system_1',
					scanners=[
						SensorConstant(
							name="test_sensor_0",
							val=Status(state=State.PASSING)
						),
						SensorConstant(
							name="test_sensor_1",
							val=Status(state=State.FAILING)
						),
					]
				),
				SensorConstant(
					name="test_sensor_2",
					val=Status(state=State.PASSING)
				)
			]
		)
	)
	v = ConsoleVisualiser()

	r = v.visualise(s)

	expected = dedent(
		"""\
		State.PASSING : test_service
			State.PASSING : test_system_0
				State.FAILING : test_system_1
					State.PASSING : test_sensor_0
					State.FAILING : test_sensor_1
				State.PASSING : test_sensor_2
		"""
	)

	assert expected == r
