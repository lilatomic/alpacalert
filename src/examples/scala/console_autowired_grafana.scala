import ca.lilatomic.alpacalert.{BasicService, SystemSeq}

import java.io.IOException
import zio.{ZIO, URIO, Has}
import zio.console._
import ca.lilatomic.alpacalert.sensors.GrafanaConnection
import ca.lilatomic.alpacalert.visualisers.ConsoleVisualiser

/**
 * This example shows how to quickly query which grafana dashboards are alerting.
 *
 */
object console_autowired_grafana extends zio.App {
	val program: ZIO[Console with GrafanaConnection, Throwable, Unit] = for {
		grafana <- GrafanaConnection.getAlerts()
		by_dashboard <- ZIO.succeed(grafana.values.groupBy(_.dashboardUid))
		services <- ZIO.succeed(by_dashboard.map(e => new BasicService(e._1, new SystemSeq("TestSystem " + e._1, e._2.toSeq))))
		_ <- putStrLn(services.map(ConsoleVisualiser.visualise(_)).mkString(""))
	} yield ()

	def run(args: List[String]) =
		program
			.provideLayer(GrafanaConnection.demoGrafana ++ Console.live)
			.exitCode
}
