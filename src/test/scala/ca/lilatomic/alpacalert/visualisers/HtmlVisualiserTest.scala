package ca.lilatomic.alpacalert.visualisers

import ca.lilatomic.alpacalert._
import ca.lilatomic.alpacalert.sensors.GrafanaTest
import org.scalatest.funsuite.AnyFunSuite
import zio.{Runtime, ZIO}


class HtmlVisualiserTest extends AnyFunSuite {
	def execZio[A](z: zio.IO[Any, A]): A = Runtime.default.unsafeRun(z)

	test("Example html visualiser") {
		val grafana = GrafanaTest.getDemo()

		val by_dashboard = grafana.values.groupBy(_.dashboardUid)
		val services = by_dashboard.map(e => new BasicService(e._1, new SystemSeq("TestSystem" + e._1, e._2.toSeq))).toSeq

		assert(!(execZio(HtmlVisualiser.visualise(services)).toLowerCase.contains("zio")))
	}
}