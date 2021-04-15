package ca.lilatomic.alpacalert

import ca.lilatomic.alpacalert.System

trait Service() {
	val name: String

	def status(): Status
}

/**
 * a service with some basic metadata
 */
class BasicService(val name: String, val system: System) extends Service() {
	override def status(): Status = system.status()
}