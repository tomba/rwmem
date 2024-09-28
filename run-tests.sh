#!/bin/sh

python3 -m unittest $*
PYTHONPATH=py python3 -m unittest discover py/tests
