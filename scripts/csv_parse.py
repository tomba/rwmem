#!/usr/bin/python3

import csv

def csv_parse(file):
    regs = []
    with open(file, newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=',')
        reg = None
        for row in spamreader:
            if row == []:
                regs.append(reg)
                reg = None
            elif reg == None:
                reg = {"name": row[0], "offset": int(row[1], 0), "fields": [] }
            else:
                reg["fields"].append({ "name": row[0], "high": int(row[1], 0), "low": int(row[2], 0) })

    return regs
