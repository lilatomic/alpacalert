package ca.lilatomic.alpacalert.sensors

import ca.lilatomic.alpacalert.{Sensor, Status}
import zio.ZIO

class NotFoundSensor(override val name: String) extends Sensor {
	override def status() = ZIO.Succeed(Status.NotFound)
}
