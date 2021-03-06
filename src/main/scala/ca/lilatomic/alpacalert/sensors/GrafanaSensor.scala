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
	override def status(): UIO[Status] = {
		state match {
			case "alerting" => ZIO.succeed(Status.Down)
			case "ok" => ZIO.succeed(Status.Up)
			case "no_data" => ZIO.succeed(Status.Down)
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
	val fromConfig: ZLayer[Has[GrafanaConnectionConfig], Nothing, GrafanaConnection] = ZLayer.fromService {
		ServiceImpl(_)
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

	class ServiceImpl(cfg: GrafanaConnectionConfig) extends Service {
		val request = basicRequest.get(cfg.url).response(asJson[List[GrafanaAlert]])
		val backend = HttpURLConnectionBackend()

		override def getAlerts() = {
			val request_auth = cfg.auth match {
				case auth: GrafanaConnectionConfig.AuthBasic => request.auth.basic(auth.user, auth.password)
				case auth: GrafanaConnectionConfig.AuthToken => request.auth.bearer(auth.token)
				case _: GrafanaConnectionConfig.AuthNone.type => request
			}

			val response = request_auth.send(backend).body

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

case class GrafanaConnectionConfig(url: Uri, auth: GrafanaConnectionConfig.Auth)

object GrafanaConnectionConfig {

	sealed trait Auth

	case class AuthBasic(user: String, password: String) extends Auth

	case class AuthToken(token: String) extends Auth

	object AuthNone extends Auth
}