val dottyVersion = "3.0.0-M2"

lazy val root = project
  .in(file("."))
  .settings(
    name := "dotty-simple",
    version := "0.1.0",

    scalaVersion := dottyVersion,

    libraryDependencies += "dev.zio" %% "zio" % "1.0.5"
    libraryDependencies += "com.novocode" % "junit-interface" % "0.11" % "test"
  )
