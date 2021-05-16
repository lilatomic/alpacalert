package ca.lilatomic.alpacalert


import ca.lilatomic.alpacalert._
import org.scalatest.funsuite.AnyFunSuite
import zio.{UIO, ZIO, IO, Runtime}

def SensorDown = MockSensor(Status.Down)

def SensorUp = MockSensor(Status.Up)

def mkSensor(up: Boolean): Sensor = MockSensor(if (up) Status.Up else Status.Down)

class MockSensor(val data: Status) extends Sensor {
	val name: String = "TestSystem"

	def status(): UIO[Status] = ZIO.succeed(data)
}

class SensorUsage extends AnyFunSuite {
	def execZio[A](z: zio.IO[Any, A]): A = Runtime.default.unsafeRun(z)

	/**
	 * This test shows that you can turn some data from whatever service you have into an array of sensors
	 */
	test("Dynamic Sensor array") {
		val spec = Seq(
			(0, false),
			(1, false),
			(2, true),
		)
		val sensors = spec.map(e => (e._1, mkSensor(e._2))).toMap

		val statuses = sensors.map(_._2.status())

		assert(Seq(Status.Down, Status.Down, Status.Up) === statuses.map(execZio))
	}
}

/**
 * This suite shows off a basic Parallel system, which is up when any of the subsystems are up.
 * This could be a Highly Available webserver, which is serving webs so long as any of its members are.
 */
class SystemUsageTest extends AnyFunSuite {
	def execZio[A](z: zio.IO[Any, A]): A = Runtime.default.unsafeRun(z)

	test("SystemPar with All UP") {
		val system = new SystemPar("TestSystem", Seq(SensorUp, SensorUp))
		assert(Status.Up === execZio(system.status()))
	}

	test("SystemPar wth some UP") {
		val system = new SystemPar("TestSystem", Seq(SensorUp, SensorDown))
		assert(Status.Up === execZio(system.status()))
	}

	test("SystemPar with all DOWN") {
		val system = new SystemPar("TestSystem", Seq(SensorDown, SensorDown))
		assert(Status.Down === execZio(system.status()))
	}
}

class DynamicSetup extends AnyFunSuite {
	def execZio[A](z: zio.IO[Any, A]): A = Runtime.default.unsafeRun(z)

	/**
	 * Demonstrates how to dynamically construct Services from lists of ca.lilatomic.alpacalert.sensors and a definition for a custom sensor
	 */
	test("Dynamic setup") {
		val sensorsA = Seq(false, false, true).map(mkSensor(_))
		val sensorsB = Seq(false, true, true).map(mkSensor(_))

		class TestSystem(val sensorA: Sensor, sensorB: Sensor) extends System {
			val name: String = "TestSystem"

			override def status() = for {
				a <- sensorA.status()
				b <- sensorB.status()
			} yield (Status.&(a, b))

			override def children(): Seq[Sensor] = Seq(sensorA, sensorB)
		}

		val systems = sensorsA.zip(sensorsB).map(e => new TestSystem(e._1, e._2))
		val services = systems.zipWithIndex.map(e => new BasicService(e._2.toString, e._1))

		val serviceStatuses = services.map(e => (e.name, e.status()))
		print(serviceStatuses)
		assert(Seq(("0", Status.Down), ("1", Status.Down), ("2", Status.Up)) === serviceStatuses.map(e => (e._1, execZio(e._2))))
	}
}