package sensors

import ca.lilatomic.alpacalert.Sensor
import org.scalatest.funsuite.AnyFunSuite
import zio._
import zio.internal.Platform
import ca.lilatomic.alpacalert.sensors.GrafanaConnection

class GrafanaTest extends AnyFunSuite {

	test("Grafana Test") {
		val program: ZIO[GrafanaConnection, Throwable, List[Sensor]] = for {
			x <- GrafanaConnection.getAlerts()
		} yield x

		val exe: Task[List[Sensor]] = program.provideLayer(GrafanaConnection.demoGrafana)

		val runtime = Runtime.default

		val out = runtime.unsafeRun(exe)
		println(out)

		//		val runtime = Runtime(GrafanaConnection.demoGrafana, PlatformLive.Default)
		//		runtime.unsafeRun[Throwable, List[Sensor]](program)
	}
}
