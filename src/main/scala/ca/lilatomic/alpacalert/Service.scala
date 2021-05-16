package ca.lilatomic.alpacalert

import ca.lilatomic.alpacalert.System
import zio.UIO

/**
 * a service with some basic metadata
 */
class BasicService(val name: String, val system: System) extends Service() {
	override def status(): UIO[Status] = system.status()

	override def children(): Seq[Scanner] = Seq(system)
}