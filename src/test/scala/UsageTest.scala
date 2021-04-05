
import org.junit.Test
import org.junit.Assert._

class UsageTest {
  @Test def t1(): Unit = {
    assertEquals("I was compiled by dotty :)", Main.msg)
  }
}