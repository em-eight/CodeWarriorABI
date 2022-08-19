"""
Lists the source code files that make up Mario Kart Wii.
"""


from dataclasses import dataclass
from itertools import chain


HOSTSYS_OPTS = '-ipa file -rostr -sdata 0 -sdata2 0'
RVL_OPTS = '-ipa file'
MSL_LIBC_OPTS = '-ipa file'
NW4R_OPTS = '-ipa file -inline auto -O4,p -pragma \"legacy_struct_alignment on\"'
SPY_OPTS = RVL_OPTS + " -w nounusedexpr -w nounusedarg"
RFL_OPTS = RVL_OPTS + " -O4,p"
EGG_OPTS = ' -use_lmw_stmw=on -ipa function -rostr'
REL_OPTS = HOSTSYS_OPTS + " -use_lmw_stmw=on -pragma \"legacy_struct_alignment on\" "


@dataclass
class Source:
    src: str
    cc: str
    opts: str


SOURCES = [
    Source(src="src/a.cpp", cc='4201_127', opts=REL_OPTS),
]
