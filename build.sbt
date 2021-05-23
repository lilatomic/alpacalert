lazy val examples = (project
	in (file("examples")))
	.dependsOn(root)
	.settings(
		resolvers +=
			"Sonatype OSS Snapshots" at "https://s01.oss.sonatype.org/content/repositories/snapshots",
		name := "alpacalert-examples",
		version := "0.1.0",
		scalaVersion := dottyVersion,

		libraryDependencies ++= dependencies ++ Seq(
			"io.d11" %% "zhttp" % "1.0.0.0-RC15+31-46c879fd-SNAPSHOT"
			//			"io.d11" %% "zhttp" % "1.0.0.0-RC15"
		),
	)

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
val dottyVersion = "3.0.0-RC3"
val circeVersion = "0.14.0-M6+"
val sttpVersion = "3.3.0"
val testcontainersScalaVersion = "0.39.4"
val dependencies = Seq(
	"dev.zio" %% "zio" % "1.0.7+",
	"com.softwaremill.sttp.client3" %% "core" % sttpVersion,
	"com.softwaremill.sttp.client3" %% "circe" % sttpVersion,

	"io.circe" %% "circe-core" % circeVersion,
	"io.circe" %% "circe-generic" % circeVersion,
	"io.circe" %% "circe-parser" % circeVersion,

	"org.scalatest" %% "scalatest" % "3.2.8" % "test,it",
	"com.dimafeng" % "testcontainers-scala-scalatest_2.13" % testcontainersScalaVersion % "it"
)

