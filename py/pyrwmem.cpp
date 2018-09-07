#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "mmaptarget.h"
#include "regs.h"
#include "mappedregs.h"

namespace py = pybind11;

using namespace std;

PYBIND11_MODULE(pyrwmem, m) {
	py::class_<RegisterFile>(m, "RegisterFile")
			.def(py::init<const string&>())
			.def_property_readonly("name", &RegisterFile::name)
			.def_property_readonly("num_blocks", &RegisterFile::num_blocks)
			.def_property_readonly("num_regs", &RegisterFile::num_regs)
			.def_property_readonly("num_fields", &RegisterFile::num_fields)
			.def("__getitem__", &RegisterFile::at)
			.def("__getitem__", &RegisterFile::find_register_block)
			.def("find_register", (unique_ptr<Register> (RegisterFile::*)(const string&) const)&RegisterFile::find_register)
			.def("find_register", (unique_ptr<Register> (RegisterFile::*)(uint64_t) const)&RegisterFile::find_register)
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
			.def("find_field", (unique_ptr<Field> (Register::*)(const string&) const)&Register::find_field)
			.def("find_field", (unique_ptr<Field> (Register::*)(uint8_t, uint8_t) const)&Register::find_field)
			;

	py::class_<Field>(m, "Field")
			.def_property_readonly("name", &Field::name)
			.def_property_readonly("low", &Field::low)
			.def_property_readonly("high", &Field::high)
			;



	py::class_<MMapTarget>(m, "MMapTargetMap")
			.def(py::init<const string&, Endianness, uint64_t, uint64_t>())
			.def("read32", &MMapTarget::read32)
			.def("write32", &MMapTarget::write32)
			;


	py::class_<MappedRegisterBlock>(m, "MappedRegisterBlock")
			.def(py::init<const string&, const string&, const string&>())
			.def(py::init<const string&, uint64_t, const string&, const string&>())
			.def(py::init<const string&, uint64_t, uint64_t>())
			.def("read", &MappedRegisterBlock::read)
			.def("read_value", &MappedRegisterBlock::read_value)
			.def("read32", &MappedRegisterBlock::read32)
			.def("find_register", &MappedRegisterBlock::find_register)
			.def("get_register", &MappedRegisterBlock::get_register)
			;

	py::class_<MappedRegister>(m, "MappedRegister")
			.def("read", &MappedRegister::read)
			.def("read_value", &MappedRegister::read_value)
			;

	py::class_<RegisterValue>(m, "RegisterValue")
			.def("value", &RegisterValue::value)
			.def("field_value", (uint64_t (RegisterValue::*)(const string&) const)&RegisterValue::field_value)
			.def("field_value", (uint64_t (RegisterValue::*)(uint8_t, uint8_t) const)&RegisterValue::field_value)
			.def("set_field_value", (void (RegisterValue::*)(const string&, uint64_t))&RegisterValue::set_field_value)
			.def("set_field_value", (void (RegisterValue::*)(uint8_t, uint8_t, uint64_t))&RegisterValue::set_field_value)
			.def("write", &RegisterValue::write)
			;
}
