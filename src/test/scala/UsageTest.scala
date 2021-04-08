
import ca.lilatomic.alpacalert._
import org.scalatest.funsuite.AnyFunSuite

def SensorDown = MockSensor(Status.Down)

def SensorUp = MockSensor(Status.Up)

def mkSensor(up: Boolean): Sensor = MockSensor(if (up) Status.Up else Status.Down)

class MockSensor(val data: Status) extends Sensor {
	def sense(): Status = data
}

class SensorUsage extends AnyFunSuite {

	test("Dynamic Sensor array") {
		val spec = Seq(
			(0, false),
			(1, false),
			(2, true),
		)
		val sensors = spec.map(e => (e._1, mkSensor(e._2))).toMap

		val statuses = sensors.map(_._2.sense())

		assert(statuses === Seq(Status.Down, Status.Down, Status.Up))
	}
}

class SystemUsageTest extends AnyFunSuite {
	test("SystemPar with All UP") {
		val system = new SystemPar(Seq(SensorUp, SensorUp))
		assert(Status.Up === system.status())
	}

	test("SystemPar wth some UP") {
		val system = new SystemPar(Seq(SensorUp, SensorDown))
		assert(Status.Up === system.status())
	}

	test("SystemPar with all DOWN") {
		val system = new SystemPar(Seq(SensorDown, SensorDown))
		assert(Status.Down === system.status())
	}
}

class DynamicSetup extends AnyFunSuite {

	/**
	 * Demonstrates how to dynamically construct Services from lists of sensors and a definition for a custom sensor
	 */
	test("Dynamic setup") {
		val sensorsA = Seq(false, false, true).map(mkSensor(_))
		val sensorsB = Seq(false, true, true).map(mkSensor(_))

		class TestSystem(val sensorA: Sensor, sensorB: Sensor) extends System {
			override def status() = Status.&(sensorA.sense(), sensorB.sense())
		}

		val systems = sensorsA.zip(sensorsB).map(e => new TestSystem(e._1, e._2))
		val services = systems.zipWithIndex.map(e => new BasicService(e._2.toString, e._1))

		val serviceStatuses = services.map(e => (e.name, e.status()))
		print(serviceStatuses)
		assert(Seq(("0", Status.Down), ("1", Status.Down), ("2", Status.Up)) === serviceStatuses)
	}
}