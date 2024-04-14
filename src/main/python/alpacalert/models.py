from __future__ import annotations

from abc import abstractmethod, ABC
from enum import Enum

from pydantic import BaseModel


class Severity(Enum):
	"""Severity of a Message, per OpenTelemetry log SeverityText and SeverityNumber."""
	TRACE = 1
	DEBUG = 5
	INFO = 9
	WARN = 13
	ERROR = 17
	FATAL = 21


class Log(BaseModel):
	"""A message to be passed as part of a Status"""
	message: str
	severity: Severity


class State(Enum):
	"""The state of a Scanner"""
	PASSING = "passing"
	FAILING = "failing"
	UNKNOWN = "unknown"


class Status(BaseModel):
	state: State
	messages: list[Log]


class Scanner(ABC):
	@abstractmethod
	def status(self) -> Status:
		"""The status of this scanner"""


class Sensor(Scanner, ABC):
	"""
	These reach out to the world and measure something.

	That could be the status of a running process, available disk space, or availability of a healthcheck endpoint; for example.
	"""


class System(Scanner, ABC):
	"""
	These compose Sensors and other Systems into logical units of infrastructure.
	Systems also make determinations about their health by using data from their Sensors.
	"""


class Service(Scanner, ABC):
	"""
	These are capabilities that your infrastructure provides.

	These might be customer-facing, like the actual application; or internal-facing, like a message queue; or parts of your development infrastructure, like the status of build servers.
	"""