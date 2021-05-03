import ca.lilatomic.alpacalert.{BasicService, SystemSeq}
import ca.lilatomic.alpacalert.sensors.GrafanaConnection
import ca.lilatomic.alpacalert.visualisers.{ConsoleVisualiser, HtmlVisualiser}
import zio._
import zhttp.http._
import zhttp.http
import zhttp.service.Server

/**
 * This example shows how to make a web endpoint for your sensors using the zio-http library. This library is small and provides a small-footprint way of exposing system health to the web.
 */
object ziohttp_autowired_grafana extends zio.App {
	val program: ZIO[GrafanaConnection, Throwable, String] = for {
		grafana <- GrafanaConnection.getAlerts()
		by_dashboard <- ZIO.succeed(grafana.values.groupBy(_.dashboardUid))
		services <- ZIO.succeed(by_dashboard.map(e => new BasicService(e._1, new SystemSeq("TestSystem " + e._1, e._2.toSeq))).take(2).toSeq)
		content <- ZIO.succeed(HtmlVisualiser.visualise(services))
	} yield (content)
	val app = Http.collectM {
		case Method.GET -> Root => program.map(html => htmlResponse(html))
	}

	def htmlResponse(html: String): UResponse =
		Response.http(
			content = HttpContent.Complete(html),
			headers = List(Header.custom("Content-Type", "text/html")),
		)

	override def run(args: List[String]): URIO[zio.ZEnv, ExitCode] = Server.start(8080, app).provideCustomLayer(GrafanaConnection.demoGrafana).exitCode
}
