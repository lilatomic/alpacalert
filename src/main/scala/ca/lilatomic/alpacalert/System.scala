package ca.lilatomic.alpacalert

import ca.lilatomic.alpacalert.Sensor
import zio.{UIO, ZIO}

class SystemPar(val name: String, val sensors: Seq[Sensor]) extends System() {
	override def status(): UIO[Status] = ZIO.collectAll(
		sensors.map(_.status())
	).map(_.reduce(Status.|))

	override def children(): Seq[Sensor] = sensors
}

class SystemSeq(val name: String, val sensors: Seq[Sensor]) extends System() {
	override def status(): UIO[Status] = ZIO.collectAll(
		sensors.map(_.status())
	).map(_.reduce(Status.&))

	override def children(): Seq[Sensor] = sensors
}
