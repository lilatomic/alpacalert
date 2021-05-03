package ca.lilatomic.alpacalert.visualisers

import ca.lilatomic.alpacalert._
import ca.lilatomic.alpacalert.sensors.GrafanaTest
import org.scalatest.funsuite.AnyFunSuite


class HtmlVisualiserTest extends AnyFunSuite {
	test("Example html visualiser") {
		val grafana = GrafanaTest.getDemo()

		val by_dashboard = grafana.values.groupBy(_.dashboardUid)
		val services = by_dashboard.map(e => new BasicService(e._1, new SystemSeq("TestSystem" + e._1, e._2.toSeq))).toSeq

		println((HtmlVisualiser.visualise(services)))
	}
}