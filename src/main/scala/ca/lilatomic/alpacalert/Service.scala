package ca.lilatomic.alpacalert

trait Service(val name: String) {
	def status(): Status
}

/**
 * a service with some basic metadata
 */
class BasicService(name: String, val system: System) extends Service(name) {
	override def status(): Status = system.status()
}