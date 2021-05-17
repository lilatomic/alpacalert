package ca.lilatomic.alpacalert.visualisers

import ca.lilatomic.alpacalert.{Scanner, Status}
import zio.{UIO, ZIO}

object HtmlVisualiser {
	def visualise(scanners: Seq[Scanner]): UIO[String] = {
		for {
			visualised: String <- ZIO.collectAll(for {
				s <- scanners
			} yield (visualiseItem(s))).map(e => e.reduce(_.concat(_)))
		} yield (root(
			tag("ul", tag("li", visualised))
		))
	}

	def renderChildren(children: Seq[Scanner]): UIO[String] = {
		ZIO.reduceAll(ZIO.succeed(""), children.map(visualiseItem(_).map(s => tag("li", s))))(_.concat(_))
	}

	def visualiseItem(scanner: Scanner): UIO[String] = for {
		status <- scanner.status()
		statusStr = statusComponent(status)
		scannerStr: String <- (scanner match {
			case s: ca.lilatomic.alpacalert.Sensor => ZIO.succeed(" sensor " + tag("strong", s.name))
			case s: ca.lilatomic.alpacalert.System => for {
				c <- renderChildren(s.children())
			} yield (
				" sensor " + tag("strong", scanner.name)
					+ tag("ul", c)
				)
			case s: ca.lilatomic.alpacalert.Service => for {
				c <- renderChildren(s.children())
			} yield (
				" Service " + tag("strong", s.name)
					+ tag("ul", c)
				)
		})
	} yield (
		tag("div",
			statusStr
				+ scannerStr
		))

	def statusComponent(status: Status): String = status match {
		case _: ca.lilatomic.alpacalert.Up => "\u2714️"
		case _: ca.lilatomic.alpacalert.Down => "\u274C"
	}

	def root(body: String, title: String = "\uD83D\uDEA8Alerts\uD83D\uDEA8"): String = tag("html",
		tag("head", "<meta charset=\"UTF-8\">" + tag("title", title)) +
			tag("body", tag("h1", "Complete Services Health") + body)
	)

	def tag(name: String, body: String): String = s"<${name}>${body}</${name}>"
}
