val dottyVersion = "3.0.0-RC1"

lazy val root = project
	.in(file("."))
	.configs(IntegrationTest)
	.settings(
		Defaults.itSettings,
		name := "alpacalert",
		version := "0.1.0",

		scalaVersion := dottyVersion,

		IntegrationTest / fork := true,

		libraryDependencies ++= dependencies,
	)
lazy val examples = project
	.in(file("examples"))
	.dependsOn(root)
	.settings(
		name := "alpacalert-examples",
		version := "0.1.0",
		scalaVersion := dottyVersion,

		IntegrationTest / fork := false,

		libraryDependencies ++= dependencies,
	)
val circeVersion = "0.14.0-M4+"
val sttpVersion = "3.2.3"
val testcontainersScalaVersion = "0.39.3+"
val dependencies = Seq(
	"dev.zio" %% "zio" % "1.0.5+",
	"com.softwaremill.sttp.client3" %% "core" % sttpVersion,
	"com.softwaremill.sttp.client3" %% "circe" % sttpVersion,

	"io.circe" %% "circe-core" % circeVersion,
	"io.circe" %% "circe-generic" % circeVersion,
	"io.circe" %% "circe-parser" % circeVersion,

	"org.scalatest" %% "scalatest" % "3.2.5" % "test,it",
	"com.dimafeng" %% "testcontainers-scala-scalatest" % testcontainersScalaVersion % "it"
)

