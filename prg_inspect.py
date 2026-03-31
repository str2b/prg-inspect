"""
prg_inspect.py - Unified EDIABAS PRG Inspection Tool
======================================================

Modes
-----
  --prg              -f <file.prg> [-w N] [-j]
  --job   <JOB>...   -f <file.prg> [-w N] [-j] [--heuristic]
  --table <TABLE>... -f <file.prg> [-w N] [-j]
  --dtc              -f <file.prg> [-w N] [-j]
  --dis   <JOB>...   -f <file.prg>

Common flags
  -w / --width N   Max chars per cell (bare flag or 0 = unlimited; default 50)
  -j / --json      Emit JSON instead of pretty text (not available for dis)

Job-mode flags
  --heuristic      Also match tables named via _xxx wildcard patterns in comments

Knowledge sources
-----------------
Binary format, opcodes, addressing modes and obfuscation scheme are derived from
EdiabasLib/EdiabasLib/EdiabasNet.cs (https://github.com/uholeschak/ediabaslib).
"""

import struct
import os
import re
import sys
import json
import argparse

# Opcode table + addressing modes
# Source: EdiabasNet.cs - OpAddrMode enum, OcList
MODE_NONE = 0
MODE_REG_S = 1
MODE_REG_AB = 2
MODE_REG_I = 3
MODE_REG_L = 4
MODE_IMM8 = 5
MODE_IMM16 = 6
MODE_IMM32 = 7
MODE_IMM_STR = 8
MODE_IDX_IMM = 9
MODE_IDX_REG = 10
MODE_IDX_REG_IMM = 11
MODE_IDX_IMM_LEN_IMM = 12
MODE_IDX_IMM_LEN_REG = 13
MODE_IDX_REG_LEN_IMM = 14
MODE_IDX_REG_LEN_REG = 15

# Opcodes that use a near-address operand instead of the standard mode byte.
# Source: EdiabasNet.cs - OcList
_NO_MODE_OPCODES = {
    0x0B,
    0x0C,
    0x0D,
    0x0E,
    0x0F,
    0x10,
    0x11,
    0x12,
    0x13,
    0x14,
    0x15,
    0x41,
    0x47,
    0x48,
    0x5A,
    0x5B,
    0x5C,
    0x5D,
    0x5E,
    0x5F,
}

# Source: EdiabasNet.cs - OcList
OPCODES = {
    0x00: "move",
    0x01: "clear",
    0x02: "comp",
    0x03: "subb",
    0x04: "adds",
    0x05: "mult",
    0x06: "divs",
    0x07: "and",
    0x08: "or",
    0x09: "xor",
    0x0A: "not",
    0x0B: "jump",
    0x0C: "jtsr",
    0x0D: "ret",
    0x0E: "jc",
    0x0F: "jae",
    0x10: "jz",
    0x11: "jnz",
    0x12: "jv",
    0x13: "jnv",
    0x14: "jmi",
    0x15: "jpl",
    0x16: "clrc",
    0x17: "setc",
    0x18: "asr",
    0x19: "lsl",
    0x1A: "lsr",
    0x1B: "asl",
    0x1C: "nop",
    0x1D: "eoj",
    0x1E: "push",
    0x1F: "pop",
    0x20: "scmp",
    0x21: "scat",
    0x22: "scut",
    0x23: "slen",
    0x24: "spaste",
    0x25: "serase",
    0x26: "xconnect",
    0x27: "xhangup",
    0x28: "xsetpar",
    0x29: "xawlen",
    0x2A: "xsend",
    0x2B: "xsendf",
    0x2C: "xrequf",
    0x2D: "xstopf",
    0x2E: "xkeyb",
    0x2F: "xstate",
    0x30: "xboot",
    0x31: "xreset",
    0x32: "xtype",
    0x33: "xvers",
    0x34: "ergb",
    0x35: "ergw",
    0x36: "ergd",
    0x37: "ergi",
    0x38: "ergr",
    0x39: "ergs",
    0x3A: "a2flt",
    0x3B: "fadd",
    0x3C: "fsub",
    0x3D: "fmul",
    0x3E: "fdiv",
    0x3F: "ergy",
    0x40: "enewset",
    0x41: "etag",
    0x42: "xreps",
    0x43: "gettmr",
    0x44: "settmr",
    0x45: "sett",
    0x46: "clrt",
    0x47: "jt",
    0x48: "jnt",
    0x49: "addc",
    0x4A: "subc",
    0x4B: "break",
    0x4C: "clrv",
    0x4D: "eerr",
    0x4E: "popf",
    0x4F: "pushf",
    0x50: "atsp",
    0x51: "swap",
    0x52: "setspc",
    0x53: "srevrs",
    0x54: "stoken",
    0x55: "parb",
    0x56: "parw",
    0x57: "parl",
    0x58: "pars",
    0x59: "fclose",
    0x5A: "jg",
    0x5B: "jge",
    0x5C: "jl",
    0x5D: "jle",
    0x5E: "ja",
    0x5F: "jbe",
    0x60: "fopen",
    0x61: "fread",
    0x62: "freadln",
    0x63: "fseek",
    0x64: "fseekln",
    0x65: "ftell",
    0x66: "ftellln",
    0x67: "a2fix",
    0x68: "fix2flt",
    0x69: "parr",
    0x6A: "test",
    0x6B: "wait",
    0x6C: "date",
    0x6D: "time",
    0x6E: "xbatt",
    0x6F: "tosp",
    0x70: "xdownl",
    0x71: "xgetport",
    0x72: "xignit",
    0x73: "xloopt",
    0x74: "xprog",
    0x75: "xraw",
    0x76: "xsetport",
    0x77: "xsireset",
    0x78: "xstoptr",
    0x79: "fix2hex",
    0x7A: "fix2dez",
    0x7B: "tabset",
    0x7C: "tabseek",
    0x7D: "tabget",
    0x7E: "strcat",
    0x7F: "pary",
    0x80: "parn",
    0x81: "ergc",
    0x82: "ergl",
    0x83: "tabline",
    0x84: "xsendr",
    0x85: "xrecv",
    0x86: "xinfo",
    0x87: "flt2a",
    0x88: "setflt",
    0x89: "cfgig",
    0x8A: "cfgsg",
    0x8B: "cfgis",
    0x8C: "a2y",
    0x8D: "xparraw",
    0x8E: "hex2y",
    0x8F: "strcmp",
    0x90: "strlen",
    0x91: "y2bcd",
    0x92: "y2hex",
    0x93: "shmset",
    0x94: "shmget",
    0x95: "ergsysi",
    0x96: "flt2fix",
    0x97: "iupdate",
    0x98: "irange",
    0x99: "iincpos",
    0x9A: "tabseeku",
    0x9B: "flt2y4",
    0x9C: "flt2y8",
    0x9D: "y42flt",
    0x9E: "y82flt",
    0x9F: "plink",
    0xA0: "pcall",
    0xA1: "fcomp",
    0xA2: "plinkv",
    0xA3: "ppush",
    0xA4: "ppop",
    0xA5: "ppushflt",
    0xA6: "ppopflt",
    0xA7: "ppushy",
    0xA8: "ppopy",
    0xA9: "pjtsr",
    0xAA: "tabsetex",
    0xAB: "ufix2dez",
    0xAC: "generr",
    0xAD: "ticks",
    0xAE: "waitex",
    0xAF: "xopen",
    0xB0: "xclose",
    0xB1: "xcloseex",
    0xB2: "xswitch",
    0xB3: "xsendex",
    0xB4: "xrecvex",
    0xB5: "ssize",
    0xB6: "tabcols",
    0xB7: "tabrows",
}


# ===========================================================================
# Low-level deobfuscation helper
# Source: EdiabasNet.cs - ReadAndDecryptBytes()
# ===========================================================================
def xor_deobfuscate(data: bytes) -> bytes:
    """Undo the XOR-0xF7 byte obfuscation."""
    return bytes(b ^ 0xF7 for b in data)


# ===========================================================================
# PRGReader - single binary access layer
# Binary file format derived from EdiabasNet.cs:
#   table list offset (0x84) - ReadAllTables()
#   job list offset   (0x88) - GetJobList()
#   description offset(0x90) - ReadDescriptions()
#   job entry layout  (0x44 bytes) - GetJobList()
#   table entry layout(0x50 bytes) - ReadTable()
#   instruction encoding (opcode + mode byte) - opcode dispatch loop
# ===========================================================================
class PRGReader:
    """
    Reads a binary .prg file and exposes high-level accessors.
    All binary obfuscation is handled internally via xor_deobfuscate().
    """

    # ------------------------------------------------------------------
    def __init__(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"PRG file not found: {path}")
        self.path = path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _read_u32(self, f, obfuscated: bool = False) -> int:
        raw = f.read(4)
        if len(raw) < 4:
            return 0
        if obfuscated:
            raw = xor_deobfuscate(raw)
        return struct.unpack("<I", raw)[0]

    # ------------------------------------------------------------------
    # Directory readers
    # ------------------------------------------------------------------
    def read_table_dir(self) -> dict:
        """
        Returns {name: {"ptr": int, "col_ptr": int, "cols": int, "rows": int}}
        """
        tables = {}
        with open(self.path, "rb") as f:
            f.seek(0x84)
            offset = self._read_u32(f)
            if offset == 0:
                return tables
            f.seek(offset)
            count = struct.unpack("<I", xor_deobfuscate(f.read(4)))[0]
            for _ in range(count):
                entry = xor_deobfuscate(f.read(0x50))
                name = entry[:0x40].split(b"\x00")[0].decode("latin-1").strip()
                ptr, col_ptr, cols, rows = struct.unpack("<IIII", entry[0x40:0x50])
                if name:
                    tables[name] = {
                        "ptr": ptr,
                        "col_ptr": col_ptr,
                        "cols": cols,
                        "rows": rows,
                    }
        return tables

    def read_job_dir(self) -> list:
        """
        Returns [(name, addr), ...] sorted by address.
        """
        jobs = []
        with open(self.path, "rb") as f:
            f.seek(0x88)
            offset = self._read_u32(f)
            if offset == 0:
                return jobs
            f.seek(offset)
            count = self._read_u32(f)
            for _ in range(count):
                entry = xor_deobfuscate(f.read(0x44))
                name = entry[:0x40].split(b"\x00")[0].decode("latin-1").strip()
                addr = struct.unpack("<I", entry[0x40:0x44])[0]
                if name:
                    jobs.append((name, addr))
        jobs.sort(key=lambda x: x[1])
        return jobs

    def read_job_descriptions(self) -> dict:
        """
        Reads the description block and returns a dictionary mapping
        job names to their comments, inputs (args), and outputs (results).
        Returns: {job_name: {"comments": [], "args": [], "results": []}}
        """
        descriptions = {}
        with open(self.path, "rb") as f:
            f.seek(0x90)
            desc_offset = self._read_u32(f)
            if desc_offset == 0:
                return descriptions

            f.seek(desc_offset)
            size = self._read_u32(f)
            if size == 0:
                return descriptions

            raw_data = xor_deobfuscate(f.read(size))

        lines = raw_data.decode("latin-1", errors="ignore").split("\n")
        current_job = None
        for line in lines:
            line = line.strip()
            if line.startswith("JOBNAME:"):
                current_job = line[8:].strip()
                descriptions[current_job] = {"comments": [], "results": [], "args": []}
            elif current_job and line:
                if line.startswith("JOBCOMMENT:"):
                    descriptions[current_job]["comments"].append(line[11:].strip())
                elif line.startswith("RESULT:"):
                    descriptions[current_job]["results"].append(
                        {"name": line[7:].strip()}
                    )
                elif line.startswith("RESULTTYPE:"):
                    if descriptions[current_job]["results"]:
                        descriptions[current_job]["results"][-1]["type"] = line[
                            11:
                        ].strip()
                elif line.startswith("RESULTCOMMENT:"):
                    if descriptions[current_job]["results"]:
                        descriptions[current_job]["results"][-1]["comment"] = line[
                            14:
                        ].strip()
                elif line.startswith("ARG:"):
                    descriptions[current_job]["args"].append({"name": line[4:].strip()})
                elif line.startswith("ARGCOMMENT:"):
                    if descriptions[current_job]["args"]:
                        descriptions[current_job]["args"][-1]["comment"] = line[
                            11:
                        ].strip()

        return descriptions

    # ------------------------------------------------------------------
    # Table data extraction
    # ------------------------------------------------------------------
    def extract_table_data(
        self, table_info: dict, all_tables: dict, max_rows: int = 100
    ) -> list:
        """
        Decode a table's cell data.
        Returns list[list[str]] where row 0 is treated as the header.
        """
        ptrs = sorted(t["ptr"] for t in all_tables.values())
        ptr = table_info["ptr"]
        try:
            idx = ptrs.index(ptr)
            size = ptrs[idx + 1] - ptr if idx + 1 < len(ptrs) else 500_000
        except ValueError:
            size = 500_000

        with open(self.path, "rb") as f:
            f.seek(ptr)
            raw = xor_deobfuscate(f.read(size))

        raw_parts = raw.split(b"\x00")
        parts = []
        for p in raw_parts:
            cell = p.decode("latin-1", errors="replace")
            cell = re.sub(r"[\x00-\x1f\x7f]", " ", cell).strip()
            parts.append(cell)

        cols = max(1, table_info["cols"])
        total_rows = len(parts) // cols
        m_rows = table_info["rows"]
        if m_rows > total_rows:
            m_rows = total_rows
        actual_rows = min(total_rows, max_rows)

        extracted = []
        for r in range(actual_rows):
            row = parts[r * cols : (r + 1) * cols]
            if any(row):
                extracted.append(row)
            elif r > 0:
                break
        return extracted

    # ------------------------------------------------------------------
    # Cross-reference: which tables does a job reference in its bytecode?
    # ------------------------------------------------------------------
    def find_job_code_refs(self, job_name: str, all_tables: dict) -> list:
        """
        Scan the raw bytecode of `job_name` for embedded table-name strings.
        Returns sorted list of table names found.
        """
        jobs = self.read_job_dir()
        jobs_upper = [(n.upper(), a) for n, a in jobs]
        target_addr = None
        target_size = 0x2000

        for i, (name_u, addr) in enumerate(jobs_upper):
            if name_u == job_name.upper():
                target_addr = addr
                if i + 1 < len(jobs_upper):
                    target_size = jobs_upper[i + 1][1] - addr
                break

        if target_addr is None:
            return []

        with open(self.path, "rb") as f:
            f.seek(target_addr)
            j_data = xor_deobfuscate(f.read(target_size))

        refs = []
        for t_name in all_tables:
            if t_name.encode("latin-1") + b"\x00" in j_data:
                refs.append(t_name)
        return sorted(refs)

    # ------------------------------------------------------------------
    # Disassembler
    # ------------------------------------------------------------------
    @staticmethod
    def _dis_get_arg(data: bytes, pc: int, mode: int, base_addr: int, start_pc: int):
        """
        Decode one argument from `data[pc:]` according to `mode`.
        Returns (arg_str, new_pc).
        """
        if mode == MODE_NONE:
            return "", pc
        elif mode in (MODE_REG_S, MODE_REG_AB, MODE_REG_I, MODE_REG_L):
            return f"R{data[pc]}", pc + 1
        elif mode == MODE_IMM8:
            return f"0x{data[pc]:02X}", pc + 1
        elif mode == MODE_IMM16:
            v = struct.unpack("<H", data[pc : pc + 2])[0]
            return f"0x{v:04X}", pc + 2
        elif mode == MODE_IMM32:
            v = struct.unpack("<I", data[pc : pc + 4])[0]
            return f"0x{v:08X}", pc + 4
        elif mode == MODE_IMM_STR:
            slen = struct.unpack("<H", data[pc : pc + 2])[0]
            sdata = data[pc + 2 : pc + 2 + slen]
            try:
                text = sdata.decode("latin-1").replace("\n", "\\n").replace("\r", "\\r")
                if len(text) > 80:
                    text = text[:77] + "..."
                return f'"{text}"', pc + 2 + slen
            except Exception:
                return f"h'{sdata.hex().upper()}'", pc + 2 + slen
        elif mode == MODE_IDX_IMM:
            idx = struct.unpack("<I", data[pc : pc + 4])[0]
            return f"IDX(0x{idx:X})", pc + 4
        elif mode == MODE_IDX_REG:
            return f"IDX(R{data[pc]})", pc + 1
        else:
            return f"MODE_{mode}?", pc + 1

    def disassemble_job(self, job_name: str):
        """
        Full bytecode disassembly of a job.
        Returns (target_addr, referenced_tables: set, instructions: list[str]).
        """
        jobs = self.read_job_dir()
        tables_dir = self.read_table_dir()
        table_names = set(tables_dir.keys())

        target_addr = None
        target_size = 0x2000
        jobs_upper = [(n.upper(), a) for n, a in jobs]
        for i, (name_u, addr) in enumerate(jobs_upper):
            if name_u == job_name.upper():
                target_addr = addr
                if i + 1 < len(jobs_upper):
                    target_size = jobs_upper[i + 1][1] - addr
                break

        if target_addr is None:
            return None, set(), []

        with open(self.path, "rb") as f:
            f.seek(target_addr)
            data = xor_deobfuscate(f.read(target_size))

        pc = 0
        instructions = []
        referenced_tables: set = set()

        for _ in range(5000):
            if pc >= len(data):
                break
            start_pc = pc
            opcode = data[pc]
            pc += 1

            has_mode = opcode not in _NO_MODE_OPCODES
            mode0 = mode1 = 0
            arg0 = arg1 = ""

            if has_mode:
                if pc >= len(data):
                    break
                mode = data[pc]
                pc += 1
                mode0 = (mode & 0xF0) >> 4
                mode1 = mode & 0x0F
                arg0, pc = self._dis_get_arg(data, pc, mode0, target_addr, start_pc)
                arg1, pc = self._dis_get_arg(data, pc, mode1, target_addr, start_pc)
            else:
                # Relative jump opcodes
                if opcode in (
                    0x0B,
                    0x0C,
                    0x0E,
                    0x0F,
                    0x10,
                    0x11,
                    0x12,
                    0x13,
                    0x14,
                    0x15,
                    0x47,
                    0x48,
                    0x5A,
                    0x5B,
                    0x5C,
                    0x5D,
                    0x5E,
                    0x5F,
                ):
                    offset = struct.unpack("<h", data[pc : pc + 2])[0]
                    arg0 = f"0x{target_addr + start_pc + 2 + offset:08X}"
                    pc += 2
                elif opcode == 0x41:  # etag - has jump + inline string
                    offset = struct.unpack("<h", data[pc : pc + 2])[0]
                    arg0 = f"0x{target_addr + start_pc + 2 + offset:08X}"
                    pc += 2
                    slen = 0
                    while pc + slen < len(data) and data[pc + slen] != 0:
                        slen += 1
                    s = (
                        data[pc : pc + slen]
                        .decode("latin-1", errors="replace")
                        .replace("\r", "")
                        .replace("\n", "\\n")
                    )
                    arg1 = f'"{s}"'
                    pc += slen + 1
                # 0x0D = ret: no args

            op_name = OPCODES.get(opcode, f"UNK_{opcode:02X}")
            args_str = ", ".join(a for a in (arg0, arg1) if a)

            # Track table references from string literals
            for arg, m in ((arg0, mode0), (arg1, mode1)):
                is_str_lit = (m == MODE_IMM_STR) or (
                    not has_mode and opcode == 0x41 and arg == arg1
                )
                if is_str_lit:
                    stripped = arg.strip("\"'")
                    if stripped in table_names:
                        referenced_tables.add(stripped)

            line = f"  0x{target_addr + start_pc:X}: {op_name:<8}"
            if args_str:
                line += f" {args_str}"
            instructions.append(line)

            if opcode == 0x1D:  # EOJ
                break

        return target_addr, referenced_tables, instructions


# ===========================================================================
# Shared output helpers
# ===========================================================================
def _sanitize_cell(val, width: int) -> str:
    """Convert a cell value to a display string, stripping control chars.
    width=0 -> no truncation; width>0 -> hard limit with trailing '...'.
    """
    s = re.sub(r"[\r\n\t]", " ", str(val)).strip()
    if width == 0 or len(s) <= width:
        return s
    return s[: width - 3] + "..."


def pretty_print_table(data: list, title: str, width: int = 50):
    """
    Print a table as a formatted ASCII box.
    Row 0 is treated as the header; a separator is drawn after it.
    """
    if not data:
        sep = "-" * (13 + len(title))
        print(f"--- TABLE: {title} ---\n  (None or Empty)\n{sep}\n")
        return

    cols = len(data[0])
    widths = [0] * cols
    for row in data:
        for i, val in enumerate(row[:cols]):
            widths[i] = max(widths[i], len(_sanitize_cell(val, width)))

    row_width = sum(widths) + max(0, (cols - 1) * 3)  # " | " separators
    print(f"--- TABLE: {title} ---")
    for row_idx, row in enumerate(data):
        cells = [
            _sanitize_cell(val, width).ljust(widths[i])
            for i, val in enumerate(row[:cols])
        ]
        print("  " + " | ".join(cells))
        if row_idx == 0:
            print("  " + "-+-".join("-" * w for w in widths))
    print("-" * (row_width + 4) + "\n")


def pretty_print_section(data: list, title: str, width: int = 50):
    """
    Like pretty_print_table but for non-table overview sections
    (jobs list, tables-of-tables, etc.) with mixed column types.
    """
    if not data:
        return

    cols = len(data[0])
    widths = [0] * cols
    for row in data:
        for i, val in enumerate(row[:cols]):
            widths[i] = max(widths[i], len(_sanitize_cell(val, width)))

    row_width = sum(widths) + max(0, (cols - 1) * 3)
    print(f"--- {title} ---")
    for row_idx, row in enumerate(data):
        cells = [
            _sanitize_cell(val, width).ljust(widths[i])
            for i, val in enumerate(row[:cols])
        ]
        print("  " + " | ".join(cells))
        if row_idx == 0:
            print("  " + "-+-".join("-" * w for w in widths))
    print("-" * (row_width + 4) + "\n")


# ===========================================================================
# Sub-command: prg
# ===========================================================================
def cmd_prg(args):
    """Architectural overview: jobs list + tables list."""
    reader = PRGReader(args.file)
    descriptions = reader.read_job_descriptions()

    job_dir = reader.read_job_dir()
    table_dir = reader.read_table_dir()

    # --- Build rows ---
    job_rows = [["NAME", "ADDRESS", "DESCRIPTION"]]
    for name, addr in sorted(job_dir, key=lambda x: x[0]):
        desc = descriptions.get(name, {})
        comments = " ".join(desc.get("comments", []))
        job_rows.append([name, f"0x{addr:06X}", comments])

    table_rows = [["NAME", "ADDRESS", "COLS", "ROWS"]]
    for name, info in sorted(table_dir.items()):
        table_rows.append([name, f"0x{info['ptr']:06X}", info["cols"], info["rows"]])

    # --- Output ---
    if args.json:
        out = {
            "file": args.file,
            "jobs": [
                {"name": r[0], "address": r[1], "description": r[2]}
                for r in job_rows[1:]
            ],
            "tables": [
                {"name": r[0], "address": r[1], "cols": r[2], "rows": r[3]}
                for r in table_rows[1:]
            ],
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"=== PRG Architectural Overview: {os.path.basename(args.file)} ===")
        print(f"Location: {args.file}\n")
        pretty_print_section(
            job_rows, f"JOBS ({len(job_rows)-1} Total)", width=args.width
        )
        pretty_print_section(
            table_rows, f"TABLES ({len(table_rows)-1} Total)", width=args.width
        )


# ===========================================================================
# Sub-command: job
# ===========================================================================
def _find_table_refs_in_text(
    text: str,
    all_tables: dict,
    refs: list,
    implicit: list,
    heuristic: bool = False,
):
    """Scan free-form comment text for 'table <Name>' references.

    The real PRG convention is: 'table <TableName> <Column>' in RESULTCOMMENT
    or ARGCOMMENT lines.  Only exact table names are matched by default.

    With heuristic=True, names ending in '_XXX' are treated as prefix wildcards
    and matched against all tables sharing that prefix.  This pattern does not
    appear in the real EDIABAS format; it is a best-effort aid for hand-written
    or partially documented files.
    """
    for match in re.finditer(r"tables?\s+([a-zA-Z0-9_]+)", text, re.IGNORECASE):
        t_name = match.group(1).upper()
        if heuristic and t_name.endswith("_XXX"):
            prefix = t_name[:-4]
            for real_t in all_tables:
                if real_t.startswith(prefix) and real_t not in refs:
                    implicit.append(f"{real_t} (Linked via Wildcard '{t_name}')")
        elif t_name in all_tables and t_name not in refs:
            implicit.append(f"{t_name} (Linked via Comment)")


def cmd_job(args):
    """Deep job dump: description, referenced tables, recursive table data."""
    reader = PRGReader(args.file)
    heuristic = getattr(args, "heuristic", False)
    descriptions = reader.read_job_descriptions()
    all_tables = reader.read_table_dir()
    json_output = {"file": args.file, "jobs": []}

    for job_name_raw in args.job:
        job_name = job_name_raw.upper()
        desc = descriptions.get(job_name, {})

        # Primary refs: table names found as string literals in the job's bytecode.
        code_refs = reader.find_job_code_refs(job_name, all_tables)

        # Secondary refs: 'table <Name>' patterns in description comments/args/results.
        implicit_refs = []
        if all_tables:
            for c in desc.get("comments", []):
                _find_table_refs_in_text(c, all_tables, code_refs, implicit_refs, heuristic)
            for a in desc.get("args", []):
                arg_name = a.get("name", "").upper()
                if arg_name in all_tables and arg_name not in code_refs:
                    implicit_refs.append(f"{arg_name} (Linked via Argument Match)")
                _find_table_refs_in_text(
                    a.get("comment", ""), all_tables, code_refs, implicit_refs, heuristic
                )
            for r in desc.get("results", []):
                res_name = r.get("name", "").upper()
                if res_name in all_tables and res_name not in code_refs:
                    implicit_refs.append(f"{res_name} (Linked via Result Match)")
                _find_table_refs_in_text(
                    r.get("comment", ""), all_tables, code_refs, implicit_refs, heuristic
                )

        all_refs = sorted(
            set(code_refs + [i.split(" (Linked")[0].strip().upper() for i in implicit_refs])
        )
        all_refs_display = sorted(code_refs + implicit_refs)

        # Collect table data (BFS: seed from direct refs, follow cell-name links)
        table_data_map = {}
        direct_ref_set = set(all_refs)
        queue = list(all_refs)
        seen = set()
        while queue:
            t_name = queue.pop(0)
            if t_name in seen or t_name not in all_tables:
                continue
            seen.add(t_name)
            try:
                rows = reader.extract_table_data(all_tables[t_name], all_tables)
                table_data_map[t_name] = rows
                for row in rows:
                    for cell in row:
                        potential = str(cell).strip().upper()
                        if potential in all_tables and potential not in seen:
                            queue.append(potential)
            except Exception:
                table_data_map[t_name] = []

        # Promote recursively-discovered tables into the display lists
        for t_name in sorted(table_data_map):
            if t_name not in direct_ref_set:
                all_refs.append(t_name)
                all_refs_display.append(f"{t_name} (Linked via Table Cell)")
        all_refs = sorted(set(all_refs))
        all_refs_display = sorted(set(all_refs_display))

        if args.json:
            comments_raw = desc.get("comments", []) if desc else []
            out = {
                "job": job_name,
                "description": {
                    "comments": [c.replace("\r", "") for c in comments_raw],
                    "args": [
                        {
                            "name": a.get("name", ""),
                            "type": a.get("type", ""),
                            "comment": a.get("comment", "").replace("\r", ""),
                        }
                        for a in desc.get("args", [])
                    ],
                    "results": [
                        {
                            "name": r.get("name", ""),
                            "type": r.get("type", ""),
                            "comment": r.get("comment", "").replace("\r", ""),
                        }
                        for r in desc.get("results", [])
                    ],
                },
                "referenced_tables": all_refs_display,
                "table_data": {name: rows for name, rows in table_data_map.items()},
            }
            json_output["jobs"].append(out)
            continue

        print(f"=== Job Dump: {job_name} ===")
        print(f"File: {args.file}\n")

        # Description block
        comments_raw = desc.get("comments", [])
        comments = "\n".join(c.replace("\r", "") for c in comments_raw)
        args_list = [
            f"  {a.get('name','')}{(' (' + a.get('type','') + ')') if a.get('type') else ''}: "
            f"{a.get('comment','').replace(chr(13),'')}"
            for a in desc.get("args", [])
        ]
        results_list = [
            f"  {r.get('name','')}{(' (' + r.get('type','') + ')') if r.get('type') else ''}: "
            f"{r.get('comment','').replace(chr(13),'')}"
            for r in desc.get("results", [])
        ]

        if comments or args_list or results_list:
            print("--- DESCRIPTION ---")
            if comments:
                print(comments)
            if args_list:
                print(f"\n[Arguments]\n" + "\n".join(args_list))
            if results_list:
                print(f"\n[Results]\n" + "\n".join(results_list))
            print("-" * 19 + "\n")
        else:
            print("--- DESCRIPTION ---\n(None or Empty)\n-------------------\n")

        if not all_refs_display:
            print("--- REFERENCED TABLES ---\n  (None)\n-------------------------\n")
        else:
            print("--- REFERENCED TABLES ---")
            for ref in all_refs_display:
                print(f"  {ref}")
            print("-------------------------\n")
            for t_name in all_refs:
                rows = table_data_map.get(t_name)
                if rows is not None:
                    pretty_print_table(rows, t_name, width=args.width)
            print()

    if args.json:
        print(json.dumps(json_output, indent=2, ensure_ascii=False))


# ===========================================================================
# Sub-command: table
# ===========================================================================
def cmd_table(args):
    """Dump one or more named tables in the pretty format."""
    reader = PRGReader(args.file)
    all_tables = reader.read_table_dir()
    json_output = {"file": args.file, "tables": []}
    
    for table_name_raw in args.table:
        table_name = table_name_raw.upper()
        # Case-insensitive lookup
        match = next((k for k in all_tables if k.upper() == table_name), None)
        if match is None:
            available = sorted(all_tables.keys())
            print(f"Table '{table_name_raw}' not found in {args.file}.")
            print(
                f"Available tables ({len(available)}): "
                + ", ".join(available[:20])
                + (" ..." if len(available) > 20 else "")
            )
            if not args.json:
                print()
            continue

        rows = reader.extract_table_data(all_tables[match], all_tables)

        if args.json:
            json_output["tables"].append(
                {
                    "name": match,
                    "cols": all_tables[match]["cols"],
                    "rows_count": all_tables[match]["rows"],
                    "data": rows,
                }
            )
        else:
            print(f"=== Table Dump: {match} ===")
            print(f"File: {args.file}")
            print(
                f"Dimensions (declared): {all_tables[match]['cols']} cols - "
                f"{all_tables[match]['rows']} rows\n"
            )
            pretty_print_table(rows, match, width=args.width)

    if args.json:
        print(json.dumps(json_output, indent=2, ensure_ascii=False))


# ===========================================================================
# Sub-command: dtc
# ===========================================================================
def cmd_dtc(args):
    """Dump DTC tables (FORTTEXTE)."""
    reader = PRGReader(args.file)
    target_names = ["FORTTEXTE"]
    all_tables = reader.read_table_dir()

    matched = {
        k: v for k, v in all_tables.items() if any(t in k.upper() for t in target_names)
    }

    if not matched:
        print(f"No tables matching {target_names} found in {args.file}.")
        sys.exit(1)

    if args.json:
        out = {"file": args.file, "tables": {}}
        for name, info in sorted(matched.items()):
            rows = reader.extract_table_data(info, all_tables, max_rows=100_000)
            out["tables"][name] = rows
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"=== DTC Table Dump: {os.path.basename(args.file)} ===")
        print(f"Matched tables: {', '.join(sorted(matched.keys()))}\n")
        for name, info in sorted(matched.items()):
            rows = reader.extract_table_data(info, all_tables, max_rows=100_000)
            pretty_print_table(rows, name, width=args.width)


# ===========================================================================
# Sub-command: dis
# ===========================================================================
def cmd_dis(args):
    """Disassemble a job's bytecode (text only)."""
    reader = PRGReader(args.file)

    for job_name_raw in args.dis:
        job_name = job_name_raw.upper()
        target_addr, ref_tables, instructions = reader.disassemble_job(job_name)

        if target_addr is None:
            # List available jobs as a hint
            jobs = reader.read_job_dir()
            print(f"Job '{job_name_raw}' not found in {args.file}.")
            print(
                "Available jobs: "
                + ", ".join(n for n, _ in sorted(jobs, key=lambda x: x[0]))
            )
            print()
            continue

        print(f"=== Disassembly: {job_name} @ 0x{target_addr:X} ===")
        print(f"File: {args.file}")
        if ref_tables:
            print(f"Referenced tables: {', '.join(sorted(ref_tables))}")
        print()
        for inst in instructions:
            print(inst)
        print()


# ===========================================================================
# Argument parser
# ===========================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prg_inspect",
        description="Unified EDIABAS PRG inspection tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  prg_inspect.py --prg              -f ecufile.prg
  prg_inspect.py --prg              -f ecufile.prg -j
  prg_inspect.py --job READ_EEPROM  -f ecufile.prg
  prg_inspect.py --table FORTTEXTE  -f ecufile.prg
  prg_inspect.py --dtc              -f ecufile.prg
  prg_inspect.py --dis STATUS_LESEN -f ecufile.prg
""",
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--prg",   action="store_true",  help="Architectural overview: jobs + tables")
    mode_group.add_argument("--job",   metavar="JOB", nargs="+", help="Deep job dump (job name)")
    mode_group.add_argument("--table", metavar="TABLE", nargs="+", help="Dump named table(s)")
    mode_group.add_argument("--dtc",   action="store_true",  help="Dump DTC tables (FORTTEXTE)")
    mode_group.add_argument("--dis",   metavar="JOB", nargs="+", help="Disassemble job bytecode")

    parser.add_argument("-f", "--file", required=True, help="Path to .prg file")
    parser.add_argument(
        "-w",
        "--width",
        nargs="?",
        type=int,
        const=0,
        default=50,
        metavar="N",
        help="Max chars per cell (0 or bare flag = unlimited; default 50)",
    )
    parser.add_argument("-j", "--json", action="store_true", help="Emit JSON output")
    parser.add_argument(
        "--heuristic",
        action="store_true",
        help="Match tables via _xxx wildcard patterns in comments (non-standard, job mode only)",
    )

    return parser


# ===========================================================================
# Entry point
# ===========================================================================
def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    
    if args.job:
        cmd_job(args)
    elif args.dis:
        cmd_dis(args)
    elif args.table:
        cmd_table(args)
    elif args.dtc:
        cmd_dtc(args)
    elif args.prg:
        cmd_prg(args)



if __name__ == "__main__":
    main()
