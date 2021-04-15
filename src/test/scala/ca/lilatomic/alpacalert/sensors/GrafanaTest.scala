package ca.lilatomic.alpacalert.sensors

import ca.lilatomic.alpacalert._
import org.scalatest.funsuite.AnyFunSuite
import zio._
import zio.internal.Platform
import ca.lilatomic.alpacalert.sensors.{GrafanaConnection, GrafanaSensor}

class GrafanaTest extends AnyFunSuite {
	test("Demo Grafana Test Runs") {
		println(GrafanaTest.getDemo())
	}

	test("Pull ca.lilatomic.alpacalert.sensors from GrafanaConnection") {
		val grafana = GrafanaTest.getDemo()

		val system = SystemPar("TestSystem", Seq(grafana(1), grafana(2)))
		val service = new BasicService("Grafana Test", system)

		println(service.status())
	}

	test("Automatically generate system from existing Grafana dashboards") {
		val grafana = GrafanaTest.getDemo()

		val by_dashboard = grafana.values.groupBy(_.dashboardUid)
		val services = by_dashboard.map(e => new BasicService(e._1, new SystemSeq("TestSystem" + e._1, e._2.toSeq)))

		assert(services.size === 6)
	}
}

object GrafanaTest {
	val runtime = Runtime.default

	def getDemo(): Map[Integer, GrafanaSensor] = {
		val program = for {
			x <- GrafanaConnection.getAlerts()
		} yield x

		val exe = program.provideLayer(GrafanaConnection.demoGrafana)
		runtime.unsafeRun(exe)
	}
}
