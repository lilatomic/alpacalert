# pylint: disable=redefined-outer-name,missing-module-docstring,missing-function-docstring,unused-argument

from alpacalert.generic import SensorConstant
from alpacalert.instrumentor import Instrumentor, InstrumentorComposite, InstrumentorRegistry, Kind, Registrations
from alpacalert.models import Scanner

kind0 = Kind("alpacalert.example.com", "0")
kind1 = Kind("alpacalert.example.com", "1")

s0 = SensorConstant.passing("s0", [])
s1 = SensorConstant.passing("s1", [])


class Instrumentor0(Instrumentor):

	def registrations(self) -> Registrations:
		return [(kind0, self)]

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs) -> list[Scanner]:
		return [s0]


class Instrumentor1(Instrumentor):
	def registrations(self) -> Registrations:
		return [(kind1, self)]

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs):
		return [s1]


class InstrumentorBoth(Instrumentor):
	def registrations(self) -> Registrations:
		return [(kind0, self), (kind1, self)]

	def instrument(self, registry: InstrumentorRegistry, kind: Kind, **kwargs):
		return [s0, s1]


class TestRegistry:
	def test_extend(self):
		r0 = InstrumentorRegistry()
		i0 = Instrumentor0()
		r0.register_many(i0.registrations())

		r1 = InstrumentorRegistry()
		i1 = Instrumentor1()
		r1.register_many(i1.registrations())

		r1.extend(r0)
		assert r1.instrumentors == {kind0: i0, kind1: i1}


class TestRegistryComposite:
	"""Test that registries use composite instrumentors"""
	def test_nonoverlapping(self):
		r = InstrumentorRegistry()
		i0 = Instrumentor0()
		r.register_many(i0.registrations())
		i1 = Instrumentor1()
		r.register_many(i1.registrations())

		assert r.instrumentors[kind0] == i0
		assert r.instrumentors[kind1] == i1

	def test_overlapping(self):
		r = InstrumentorRegistry()
		i0 = Instrumentor0()
		r.register_many(i0.registrations())
		ib = InstrumentorBoth()
		r.register_many(ib.registrations())

		assert r.instrumentors[kind1] == ib
		result = r.instrumentors[kind0]
		assert isinstance(result, InstrumentorComposite)
		assert result.instrumentors == [i0, ib]

	def test_nested_composite(self):
		r = InstrumentorRegistry()
		ia = Instrumentor0()
		r.register_many(ia.registrations())
		ib = Instrumentor0()
		r.register_many(ib.registrations())
		ic = Instrumentor0()
		r.register_many(ic.registrations())

		result = r.instrumentors[kind0]
		assert isinstance(result, InstrumentorComposite)
		assert result.instrumentors == [ia, ib, ic]
