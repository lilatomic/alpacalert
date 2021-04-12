package ca.lilatomic.alpacalert

sealed trait Status {}

trait Up extends Status

trait Down extends Status

object Status {
	def &(a: Status, b: Status): Status = a match {
		case _: Up => b
		case _: Down => Down
	}

	def |(a: Status, b: Status): Status = a match {
		case _: Up => Up
		case _: Down => b
	}

	object Up extends Up

	object Down extends Down

	object NotFound extends Down
}