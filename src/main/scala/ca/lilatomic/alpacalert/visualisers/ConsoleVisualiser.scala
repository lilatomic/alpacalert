package ca.lilatomic.alpacalert.visualisers

import ca.lilatomic.alpacalert.{Scanner, Sensor, Service, Status, System}

object ConsoleVisualiser {
	def statusComponent(status: Status) = status match {
		case _: ca.lilatomic.alpacalert.Up => "[°]"
		case _: ca.lilatomic.alpacalert.Down => "[×]"
	}

	def visualise(scanner: Scanner, indent: Integer = 0): String = mkIndent(indent) + statusComponent(scanner.status()) + " " + (scanner match {
		case s: ca.lilatomic.alpacalert.Sensor => s.name
		case s: ca.lilatomic.alpacalert.System => s.name + s.children().map(visualise(_, indent + 1)).mkString("")
		case s: ca.lilatomic.alpacalert.Service => s.name + s.children().map(visualise(_, indent + 1)).mkString("")
	})

	private def mkIndent(i: Integer): String = "\n" + ("\t" * i)
}
