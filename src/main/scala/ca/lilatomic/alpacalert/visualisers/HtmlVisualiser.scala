package ca.lilatomic.alpacalert.visualisers

import ca.lilatomic.alpacalert.{Scanner, Status}

object HtmlVisualiser {


	def visualise(scanners: Seq[Scanner]): String =
		root(
			scanners.map(e => tag("ul", tag("li", visualiseItem(e)))).mkString
		)

	def visualiseItem(scanner: Scanner): String = {
		tag("div",
			statusComponent(scanner.status())
				+ (scanner match {
				case s: ca.lilatomic.alpacalert.Sensor => " sensor " + tag("strong", s.name)
				case s: ca.lilatomic.alpacalert.System =>
					tag("strong", scanner.name)
						+ tag("ul",
						s.children().map(e => tag("li", visualiseItem(e))).mkString
					)
				case s: ca.lilatomic.alpacalert.Service => " Service " + tag("strong", s.name)
					+ tag("ul",
					s.children().map(e => tag("li", visualiseItem(e))).mkString
				)
			})
		)
	}

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
