package ca.lilatomic.alpacalert.sensors

import ca.lilatomic.alpacalert.{Sensor, Status}

class NotFoundSensor(override val name: String) extends Sensor {
	override def status() = Status.NotFound
}
