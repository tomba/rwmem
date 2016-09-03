#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "memmap.h"
#include "regs.h"

namespace py = pybind11;

using namespace std;

PYBIND11_PLUGIN(pyrwmem) {
	py::module m("pyrwmem", "rwmem bindings");

	py::class_<RegisterFile>(m, "RegisterFile")
			.def(py::init<const string&>())
			.def_property_readonly("name", &RegisterFile::name)
			.def_property_readonly("num_blocks", &RegisterFile::num_blocks)
			.def_property_readonly("num_regs", &RegisterFile::num_regs)
			.def_property_readonly("num_fields", &RegisterFile::num_fields)
			.def("block", &RegisterFile::register_block)
			;

	py::class_<RegisterBlock>(m, "RegisterBlock")
			.def_property_readonly("name", &RegisterBlock::name)
			.def_property_readonly("offset", &RegisterBlock::offset)
			.def_property_readonly("size", &RegisterBlock::size)
			.def_property_readonly("num_regs", &RegisterBlock::num_regs)
			.def("reg", &RegisterBlock::reg)
			;

	py::class_<Register>(m, "Register")
			.def_property_readonly("name", &Register::name)
			.def_property_readonly("offset", &Register::offset)
			.def_property_readonly("size", &Register::size)
			.def_property_readonly("num_fields", &Register::num_fields)
			.def("field", &Register::field)
			;

	py::class_<Field>(m, "Field")
			.def_property_readonly("name", &Field::name)
			.def_property_readonly("low", &Field::low)
			.def_property_readonly("high", &Field::high)
			;



	py::class_<MemMap>(m, "MemMap")
			.def(py::init<const string&, uint64_t, uint64_t, bool>())
			.def("read32", &MemMap::read32)
			.def("write32", &MemMap::write32)
			;

	return m.ptr();
}
