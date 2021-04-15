package ca.lilatomic.alpacalert

sealed trait Scanner {

}

trait Sensor() extends Scanner {
	val name: String

	def status(): Status
}

trait System() extends Scanner {
	val name: String

	def status(): Status

	def children(): Seq[Sensor]
}

trait Service() extends Scanner {
	val name: String

	def status(): Status
}