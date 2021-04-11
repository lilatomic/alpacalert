package ca.lilatomic.alpacalert.sensors

import sttp.client3._

import zio._
import ca.lilatomic.alpacalert.{Sensor, Status}
import io.circe._, io.circe.generic.auto._, io.circe.parser._, io.circe.syntax._
import sttp.client3.circe._

class Grafana(val id: Integer, val name: String, val state: String, val url: String) extends Sensor {
	override def sense(): Status = {
		state match {
			case "alerting" => Status.Down
			case "ok" => Status.Up
			case "no_data" => Status.Down
		}
	}
}

case class GrafanaAlert
(
	id: Integer,
	dashboardUid: String,
	panelId: Integer,
	name: String,
	state: String,
	url: String
)

type GrafanaConnection = Has[GrafanaConnection.Service]

object GrafanaConnection {

	val demoGrafana: ZLayer[Any, Nothing, GrafanaConnection] = ZLayer.succeed(
		new Service {
			val request = basicRequest.get(uri"https://play.grafana.org/api/alerts").response(asJson[List[GrafanaAlert]].getRight)
			val backend = HttpURLConnectionBackend()

			override def getAlerts() = {
				val response = request.send(backend).body
				val sensors = response.map(alert2sensor(_))
				IO(sensors.toList)
			}

			def alert2sensor(a: GrafanaAlert): Sensor = new Sensor {
				override def sense(): Status = Status.Up
			}
		})

	def getAlerts(): RIO[GrafanaConnection, List[Sensor]] = ZIO.accessM(_.get.getAlerts())

	trait Service {
		def getAlerts(): IO[Throwable, List[Sensor]]
	}
}
