import ca.lilatomic.alpacalert.{BasicService, SystemSeq}

import java.io.IOException
import zio.{ZIO, URIO, Has}
import zio.console._
import zio.clock._
import zio.Schedule
import zio._
import zio.duration.durationInt
import ca.lilatomic.alpacalert.sensors.GrafanaConnection
import ca.lilatomic.alpacalert.visualisers.ConsoleVisualiser

/**
 * This example shows how to quickly query which grafana dashboards are alerting.
 * It assumes that each dashboard represents its own Service where all items are required
 * and creates the hierarchy to represent this
 */
object console_autowired_grafana extends zio.App {
	val program: ZIO[Console with GrafanaConnection, Throwable, Unit] = for {
		grafana <- GrafanaConnection.getAlerts()
		by_dashboard <- ZIO.succeed(grafana.values.groupBy(_.dashboardUid))
		services <- ZIO.succeed(by_dashboard.map(e => new BasicService(e._1, new SystemSeq("TestSystem " + e._1, e._2.toSeq))))
		_ <- putStrLn(services.map(ConsoleVisualiser.visualise(_)).mkString(""))
	} yield ()

	/**
	 * This schedule will query every 10 seconds, forever.
	 */
	val schedule = Schedule.fixed(10.seconds) && Schedule.forever

	def run(args: List[String]): ZIO[zio.ZEnv, Nothing, ExitCode] = {
		program
			.provideCustomLayer(GrafanaConnection.demoGrafana)
			.repeat(schedule)
			.exitCode
	}
}
