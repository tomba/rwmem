#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "mmaptarget.h"
#include "i2ctarget.h"
#include "regs.h"

namespace py = pybind11;

using namespace std;

PYBIND11_MODULE(pyrwmem, m) {
	m.def("get_field_value", [](uint64_t r_val, uint8_t h, uint8_t l) {
		uint64_t mask = GENMASK(h, l);
		return (r_val & mask) >> l;
	});

	m.def("set_field_value", [](uint64_t r_val, uint8_t h, uint8_t l, uint64_t f_val) {
		uint64_t mask = GENMASK(h, l);
		return (r_val & ~mask) | ((f_val << l) & mask);
	});

	py::class_<RegisterFile>(m, "RegisterFile")
			.def(py::init<const string&>())
			.def_property_readonly("name", &RegisterFile::name)
			.def_property_readonly("num_blocks", &RegisterFile::num_blocks)
			.def_property_readonly("num_regs", &RegisterFile::num_regs)
			.def_property_readonly("num_fields", &RegisterFile::num_fields)

			.def("__getitem__", &RegisterFile::find_register_block)
			.def("__getitem__",  &RegisterFile::at)

			.def("find_register", (unique_ptr<Register> (RegisterFile::*)(const string&) const)&RegisterFile::find_register)
			.def("find_register", (unique_ptr<Register> (RegisterFile::*)(uint64_t) const)&RegisterFile::find_register)
			;

	py::class_<RegisterBlock>(m, "RegisterBlock")
			.def_property_readonly("name", &RegisterBlock::name)
			.def_property_readonly("offset", &RegisterBlock::offset)
			.def_property_readonly("size", &RegisterBlock::size)
			.def_property_readonly("num_regs", &RegisterBlock::num_regs)
			.def_property_readonly("data_endianness", &RegisterBlock::data_endianness)
			.def_property_readonly("data_size", &RegisterBlock::data_size)

			.def("__getitem__", &RegisterBlock::get_register)
			.def("__getitem__",  &RegisterBlock::at)

			.def("__eq__", [](RegisterBlock* self, string s) { return s == self->name(); })
			;

	py::class_<Register>(m, "Register")
			.def_property_readonly("name", &Register::name)
			.def_property_readonly("offset", &Register::offset)
			.def_property_readonly("num_fields", &Register::num_fields)
			.def_property_readonly("register_block", &Register::register_block)

			.def("__getitem__", (unique_ptr<Field> (Register::*)(const string&) const)&Register::find_field)
			.def("__getitem__",  &Register::at)

			.def("__getitem__",  [](Register* self, py::slice slice) {
				size_t start, stop, step, slicelength;

				if (!slice.compute(self->register_block().data_size() * 8 - 1, &start, &stop, &step, &slicelength))
					throw py::error_already_set();

				if (step != 1)
					throw py::value_error();

				return self->find_field(stop, start);
			})

			.def("__eq__", [](Register* self, string s) { return s == self->name(); })
			;

	py::class_<Field>(m, "Field")
			.def_property_readonly("name", &Field::name)
			.def_property_readonly("low", &Field::low)
			.def_property_readonly("high", &Field::high)
			.def("__eq__", [](Field* self, string s) { return s == self->name(); })
			;


        py::enum_<Endianness>(m, "Endianness")
                        .value("Default", Endianness::Default)
                        .value("Big", Endianness::Big)
                        .value("Little", Endianness::Little)
                        .value("BigSwapped", Endianness::BigSwapped)
                        .value("LittleSwapped", Endianness::LittleSwapped)
                        ;

	py::class_<ITarget>(m, "ITarget")
			.def("map", &ITarget::map)
			.def("unmap", &ITarget::unmap)
			.def("read", (uint64_t (ITarget::*)(uint64_t) const)&ITarget::read)
			.def("write", (void (ITarget::*)(uint64_t, uint64_t))&ITarget::write)
			.def("read", (uint64_t (ITarget::*)(uint64_t, uint8_t) const)&ITarget::read)
			.def("write", (void (ITarget::*)(uint64_t, uint8_t, uint64_t))&ITarget::write)
			;

	py::class_<MMapTarget, ITarget>(m, "MMapTarget")
			.def(py::init<const string&>())
			.def(py::init<const string&, Endianness, uint64_t, uint64_t>())
			;

	py::class_<I2CTarget, ITarget>(m, "I2CTarget")
			.def(py::init<unsigned, uint16_t>())
			;
}
