package ca.lilatomic.alpacalert

trait Sensor() {
	val name: String

	def status(): Status
}
