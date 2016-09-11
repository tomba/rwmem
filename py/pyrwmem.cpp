#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "memmap.h"
#include "regs.h"
#include "mappedregs.h"

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
			.def("__getitem__", &RegisterFile::at)
			.def("__getitem__", &RegisterFile::get_register_block)
			.def("get_reg", (Register (RegisterFile::*)(const string&) const)&RegisterFile::get_reg)
			.def("get_reg", (Register (RegisterFile::*)(uint64_t) const)&RegisterFile::get_reg)
			;

	py::class_<RegisterBlock>(m, "RegisterBlock")
			.def_property_readonly("name", &RegisterBlock::name)
			.def_property_readonly("offset", &RegisterBlock::offset)
			.def_property_readonly("size", &RegisterBlock::size)
			.def_property_readonly("num_regs", &RegisterBlock::num_regs)
			.def("at", &RegisterBlock::at)
			.def("get_reg", &RegisterBlock::get_register)
			;

	py::class_<Register>(m, "Register")
			.def_property_readonly("name", &Register::name)
			.def_property_readonly("offset", &Register::offset)
			.def_property_readonly("size", &Register::size)
			.def_property_readonly("num_fields", &Register::num_fields)
			.def("at", &Register::at)
			.def("get_field", (Field (Register::*)(const string&) const)&Register::get_field)
			.def("get_field", (Field (Register::*)(uint8_t, uint8_t) const)&Register::get_field)
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


	py::class_<MappedRegisterBlock>(m, "MappedRegisterBlock")
			.def(py::init<const string&, const string&, const string&>())
			.def(py::init<const string&, uint64_t, const string&, const string&>())
			.def(py::init<const string&, uint64_t, uint64_t>())
			.def("read32", (uint32_t (MappedRegisterBlock::*)(const string&) const)&MappedRegisterBlock::read32)
			.def("read32", (uint32_t (MappedRegisterBlock::*)(uint64_t) const)&MappedRegisterBlock::read32)
			.def("find_register", &MappedRegisterBlock::find_register)
			.def("get_register", &MappedRegisterBlock::get_register)
			;

	py::class_<MappedRegister>(m, "MappedRegister")
			.def("read32", &MappedRegister::read32)
			.def("read32value", &MappedRegister::read32value)
			;

	py::class_<RegisterValue>(m, "RegisterValue")
			.def("field_value", (uint64_t (RegisterValue::*)(const string&) const)&RegisterValue::field_value)
			.def("field_value", (uint64_t (RegisterValue::*)(uint8_t, uint8_t) const)&RegisterValue::field_value)
			;

	return m.ptr();
}
