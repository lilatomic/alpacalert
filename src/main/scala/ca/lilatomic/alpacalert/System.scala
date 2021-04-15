package ca.lilatomic.alpacalert

import ca.lilatomic.alpacalert.Sensor

class SystemPar(val name: String, val sensors: Seq[Sensor]) extends System() {
	override def status(): Status = sensors.map(_.status()).reduce(Status.|)

	override def children(): Seq[Sensor] = sensors
}

class SystemSeq(val name: String, val sensors: Seq[Sensor]) extends System() {
	override def status(): Status = sensors.map(_.status()).reduce(Status.&)

	override def children(): Seq[Sensor] = sensors
}
