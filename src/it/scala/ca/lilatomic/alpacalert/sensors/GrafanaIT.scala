package ca.lilatomic.alpacalert.sensors

import com.dimafeng.testcontainers.{ForAllTestContainer, GenericContainer}
import io.circe._
import io.circe.generic._
import io.circe.generic.auto._
import io.circe.parser._
import io.circe.syntax._
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest._
import org.testcontainers.containers.wait.strategy.Wait
import sttp.client3._
import sttp.client3.circe._
import sttp.model.Uri
import zio.ZIO
import zio.ZLayer
import zio.Runtime

import java.net.{HttpURLConnection, URL}
import scala.io.Source
import scala.util.Random

class GrafanaIT extends AnyFunSuite with GivenWhenThen with ForAllTestContainer {
	val grafanaPort = 3000
	val testAdminPassword = "pEyWpy3Ogt3fpRmF"
	override val container: GenericContainer = GenericContainer(
		"grafana/grafana:7.5.4",
		exposedPorts = Seq(grafanaPort),
		waitStrategy = Wait.forHttp("/"),
		env = Map("GF_SECURITY_ADMIN_PASSWORD" -> testAdminPassword),
	)

	val runtime = Runtime.default

	def getToken(): GrafanaTokenResponse = {
		import scala.concurrent.duration._

		val key_id = Random.alphanumeric.take(16).mkString

		val request = basicRequest
			.auth.basic("admin", testAdminPassword)
			.header("Content-Type", "application/json")
			.body(GrafanaTokenRequest(key_id, "Admin").asJson)
			.post(uri"http://${container.containerIpAddress}:${container.mappedPort(grafanaPort)}/api/auth/keys")
			.response(asJson[GrafanaTokenResponse].getRight)
			.readTimeout(5.seconds)

		val backend = HttpURLConnectionBackend()
		val response = request.send(backend)
		response.body
	}

	case class GrafanaTokenRequest(name: String, role: String)

	case class GrafanaTokenResponse(name: String, key: String)

	test("Integration : Auth can get a token") {
		val tok = getToken()
	}

	test("Integration : Token works") {
		Given("a working token")
		val tok = getToken()
		When("creating a grafana connection")
		val cfg = ZLayer.succeed(GrafanaConnectionConfig(uri"http://${container.containerIpAddress}:${container.mappedPort(grafanaPort)}/api/alerts", auth = GrafanaConnectionConfig.AuthToken(tok.key)))
		val grafana = cfg >>> GrafanaConnection.fromConfig
		Then("the connection can pull alerts")
		val program: ZIO[GrafanaConnection, Throwable, Map[Integer, GrafanaSensor]] = for {alerts <- GrafanaConnection.getAlerts()} yield (alerts)
		val sensors = runtime.unsafeRun(program.provideLayer(grafana))
		print(sensors.size)
	}
}
