val dottyVersion = "3.0.0-RC1"

lazy val root = project
	.in(file("."))
	.settings(
		name := "dotty-simple",
		version := "0.1.0",

		scalaVersion := dottyVersion,

		libraryDependencies ++= Seq(
			"dev.zio" %% "zio" % "1.0.5",
			"com.novocode" % "junit-interface" % "0.11" % "test")
	)
