package ca.lilatomic.alpacalert

sealed trait Scanner {
	val name: String

	def status(): Status
}

trait Sensor() extends Scanner {
}

trait System() extends Scanner {
	def children(): Seq[Scanner]
}

trait Service() extends Scanner {
	def children(): Seq[Scanner]
}