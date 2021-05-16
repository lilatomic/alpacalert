package ca.lilatomic.alpacalert.visualisers

import ca.lilatomic.alpacalert._
import zio.{UIO, ZIO}

object ConsoleVisualiser {
	def statusComponent(status: Status): String = status match {
		case _: ca.lilatomic.alpacalert.Up => "[°]"
		case _: ca.lilatomic.alpacalert.Down => "[×]"
	}

	def render_children(indent: Int, children: Seq[Scanner]): UIO[String] = {
		ZIO.reduceAll(ZIO.succeed(""), children.map(visualise(_, indent + 1)))(_.concat(_))
	}

	def visualise(scanner: Scanner, indent: Integer = 0): UIO[String] =
		for {
			status: Status <- scanner.status()
			statusStr: String = mkIndent(indent) + statusComponent(status) + ""
			scannerStr: String <- (scanner match {
				case s: ca.lilatomic.alpacalert.Sensor => ZIO.succeed(s.name)
				case s: ca.lilatomic.alpacalert.System => for {
					c <- render_children(indent, s.children())
				} yield (s.name + c)
				case s: ca.lilatomic.alpacalert.Service => for {
					c <- render_children(indent, s.children())
				} yield (s.name + c)
			})
		} yield (statusStr + scannerStr)

	private def mkIndent(i: Integer): String = "\n" + ("\t" * i)
}
