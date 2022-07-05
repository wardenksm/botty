import re
import json
from logger import Logger

ALL_PROPERTIES_PATH='assets/item_properties/all_properties.json'

default_prop = dict()
fp = open(ALL_PROPERTIES_PATH, 'r')
all_prop = json.load(fp)
fp.close()
for i in all_prop:
    for prop in all_prop[i].items():
        p=re.compile(prop[1][0].upper())
        prop[1][0] = p
        default_prop[prop[0]] = 0

def parse_line(str, item_prop):
    if "ETHEREAL" in str: # FIXME: "ethereal" and "socketed" may show in one line together
        item_prop["eth"] = 1
    for key in all_prop:
        if key in str:
            for name, expr in all_prop[key].items():
                if expr[0].search(str):
                    if expr[1] < 0:
                        item_prop[name] = 1
                    else:
                        values=re.findall('[0-9]+',str)
                        if expr[1] < 10:
                            item_prop[name] = int(values[expr[1]])
                        else: # Get average for attributes like "1-10 lightning damage"
                            item_prop[name] = sum(int(i) for i in values) / len(values)
                    return name, item_prop[name]
    return None, 0

def parse_lines(prop_strings: list[str], print_prop: bool = False):
    item_prop = default_prop.copy()
    for s in prop_strings:
        key,value = parse_line(s, item_prop)
        if print_prop:
            Logger.debug(" "+s if key is None else f" {s} ({key}={value})")
    return item_prop

if __name__ == "__main__":
    test_strings=[
        'WRAITH HOLD',
        'DEMONHIDE GLOVES',
        'DEFENSE: 32',
        'DURABILITY: 9 OF 12',
        'REQUIRED STRENGTH: 20',
        'REQUIRED LEVEL: 60',
        '+6 TO DEXTERITY',
        'POISON RESIST +21%',
        '11% BETTER CHANCE OF GETTING MAGIC ITEMS',
        'LEVEL 2 CHARGED STRIKE (21/25 CHARGES)',
        '+3 TO CURSES (NECROMANCER ONLY)'
    ]

    item_prop = parse_lines(test_strings)
    print(eval('all_res>15 and fcr>0', item_prop))