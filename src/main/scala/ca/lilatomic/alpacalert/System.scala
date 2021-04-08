package ca.lilatomic.alpacalert

trait System {
	def status(): Status
}

class SystemPar(val sensors: Seq[Sensor]) extends Service {
	override def status(): Status = sensors.map(_.sense()).reduce(Status.|)
}

class SystemSeq(val sensors: Seq[Sensor]) extends Service {
	override def status(): Status = sensors.map(_.sense()).reduce(Status.&)
}
