package ca.lilatomic.alpacalert.visualisers

import ca.lilatomic.alpacalert._
import ca.lilatomic.alpacalert.sensors.GrafanaTest
import org.scalatest.funsuite.AnyFunSuite


class ConsoleVisualiserTest extends AnyFunSuite {
	test("Example console visualiser") {
		val grafana = GrafanaTest.getDemo()

		val by_dashboard = grafana.values.groupBy(_.dashboardUid)
		val services = by_dashboard.map(e => new BasicService(e._1, new SystemSeq("TestSystem" + e._1, e._2.toSeq)))

		println(services.map(ConsoleVisualiser.visualise(_)).mkString(""))
	}
}