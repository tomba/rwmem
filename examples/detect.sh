#!/bin/sh

c=/proc/device-tree/compatible

if grep -sqi dra7 $c ; then
	echo dra7
fi

if grep -sqi omap5 $c ; then
	echo omap5
fi

if grep -sqi omap3 $c ; then
	echo omap3
fi

if grep -sqi am437x $c ; then
	echo am4
fi

if grep -sqi k2g $c ; then
        echo k2g
fi

if grep -sqi ti,am6 $c ; then
        echo am6
fi
