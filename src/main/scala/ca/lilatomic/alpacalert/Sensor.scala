package ca.lilatomic.alpacalert

trait Sensor[A] {
	def sense(): A
}
