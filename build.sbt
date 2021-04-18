val dottyVersion = "3.0.0-RC1"

lazy val root = project
	.in(file("."))
	.configs(IntegrationTest)
	.settings(
		Defaults.itSettings,
		name := "dotty-simple",
		version := "0.1.0",

		scalaVersion := dottyVersion,

		libraryDependencies ++= Seq(
			"dev.zio" %% "zio" % "1.0.5+",
			"com.softwaremill.sttp.client3" %% "core" % sttpVersion,
			"com.softwaremill.sttp.client3" %% "circe" % sttpVersion,

			"io.circe" %% "circe-core" % circeVersion,
			"io.circe" %% "circe-generic" % circeVersion,
			"io.circe" %% "circe-parser" % circeVersion,

			"org.scalatest" %% "scalatest" % "3.2.5" % "test,it",
		)
	)
val circeVersion = "0.14.0-M4+"
val sttpVersion = "3.2.3"
