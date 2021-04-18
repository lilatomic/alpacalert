package ca.lilatomic.alpacalert.sensors

import com.dimafeng.testcontainers.{ForAllTestContainer, GenericContainer}
import io.circe._
import io.circe.generic._
import io.circe.generic.auto._
import io.circe.parser._
import io.circe.syntax._
import org.scalatest.funsuite.AnyFunSuite
import org.testcontainers.containers.wait.strategy.Wait
import sttp.client3._
import sttp.client3.circe._
import sttp.model.Uri

import java.net.{HttpURLConnection, URL}
import scala.io.Source

class GrafanaIT extends AnyFunSuite with ForAllTestContainer {
	override val container: GenericContainer = GenericContainer(
		"grafana/grafana:7.5.4",
		exposedPorts = Seq(grafanaPort),
		waitStrategy = Wait.forHttp("/"),
		env = Map("GF_SECURITY_ADMIN_PASSWORD" -> testAdminPassword),
	)
	val grafanaPort = 3000
	val testAdminPassword = "pEyWpy3Ogt3fpRmF"

	def getToken(): GrafanaTokenResponse = {
		import scala.concurrent.duration._

		val request = basicRequest
			.auth.basic("admin", testAdminPassword)
			.header("Content-Type", "application/json")
			.body(GrafanaTokenRequest("testApiKey", "Admin").asJson)
			.post(uri"http://${container.containerIpAddress}:${container.mappedPort(grafanaPort)}/api/auth/keys")
			.response(asJson[GrafanaTokenResponse].getRight)
			.readTimeout(5.seconds)

		val backend = HttpURLConnectionBackend()
		val response = request.send(backend)
		response.body
	}

	case class GrafanaTokenRequest(name: String, role: String)

	case class GrafanaTokenResponse(name: String, key: String)

	test("Integration : Auth") {
		val tok = getToken()


	}
}
