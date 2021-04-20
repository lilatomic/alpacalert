package ca.lilatomic.alpacalert.sensors

import ca.lilatomic.alpacalert.{Sensor, Status}
import io.circe._
import io.circe.generic.auto._
import io.circe.parser._
import io.circe.syntax._
import sttp.client3._
import sttp.client3.circe._
import sttp.model.Uri
import zio._

class GrafanaSensor(val id: Integer, val dashboardUid: String, val name: String, val state: String, val url: String) extends Sensor() {
	override def status(): Status = {
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
	val fromConfig: ZLayer[Has[GrafanaConnectionConfig], Nothing, GrafanaConnection] = ZLayer.fromService { cfg =>
		new Service {
			val request = basicRequest.get(cfg.url).response(asJson[List[GrafanaAlert]])
			val backend = HttpURLConnectionBackend()

			override def getAlerts() = {
				val response = request.send(backend).body
				response match {
					case Left(e) => Task.fail(e)
					case Right(l) => {
						val sensors = l.map(alert2sensor(_))
						val sensorsById = sensors.map(e => (e.id, e)).toMap
						Task.succeed(sensorsById)
					}
				}
			}
		}
	}

	val demoGrafana: ZLayer[Any, Nothing, GrafanaConnection] = {
		ZLayer.succeed(GrafanaConnectionConfig(uri"https://play.grafana.org/api/alerts", GrafanaConnectionConfig.AuthNone)) >>> fromConfig
	}

	def alert2sensor(a: GrafanaAlert): GrafanaSensor = new GrafanaSensor(a.id, a.dashboardUid, a.name, a.state, a.url)

	def getAlerts(): RIO[GrafanaConnection, Map[Integer, GrafanaSensor]] = ZIO.accessM(_.get.getAlerts())

	trait Service {
		def getAlerts(): Task[Map[Integer, GrafanaSensor]]
		//		def getSensorById(id: Integer): Option[Sensor]
	}
}

case class GrafanaConnectionConfig(url: Uri, auth: GrafanaConnectionConfig.Auth)

object GrafanaConnectionConfig {

	sealed trait Auth

	case class AuthBasic(user: String, password: String) extends Auth

	case class AuthToken(token: String) extends Auth

	object AuthNone extends Auth
}