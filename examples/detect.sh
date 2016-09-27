#!/bin/sh

c=/proc/device-tree/compatible

if grep -sqi dra7 $c ; then
	echo dra7
fi

