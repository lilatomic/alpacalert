package ca.lilatomic.alpacalert

import ca.lilatomic.alpacalert.System

/**
 * a service with some basic metadata
 */
class BasicService(val name: String, val system: System) extends Service() {
	override def status(): Status = system.status()

	override def children(): Seq[Scanner] = Seq(system)
}