package ca.lilatomic.alpacalert
import zio.UIO

sealed trait Scanner {
	val name: String

	def status(): UIO[Status]
}

trait Sensor() extends Scanner {
}

trait System() extends Scanner {
	def children(): Seq[Scanner]
}

trait Service() extends Scanner {
	def children(): Seq[Scanner]
}