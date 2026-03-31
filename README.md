# prg_inspect

Inspection tool for EDIABAS `.prg` and `.grp` binary files.

> **Note**: This tool originally started as a vibe coding project.

## Usage

```
python prg_inspect.py --prg              -f <file.prg> [-w N] [-j]
python prg_inspect.py --job   <JOB>...   -f <file.prg> [-w N] [-j] [--heuristic]
python prg_inspect.py --table <TABLE>... -f <file.prg> [-w N] [-j]
python prg_inspect.py --dtc              -f <file.prg> [-w N] [-j]
python prg_inspect.py --dis   <JOB>...   -f <file.prg>
```

### Mode Selection

Exactly one mode flag must be provided:

| Mode | Description |
|------|-------------|
| `--prg` | Architectural overview: all jobs and tables |
| `--job <JOB>...` | Deep dump of one or more jobs with descriptions and referenced tables |
| `--table <TABLE>...` | Dump one or more named tables |
| `--dtc` | Dump fault-code tables (`FORTTEXTE`) |
| `--dis <JOB>...` | Disassemble one or more jobs' bytecode |

---

## Common options

| Flag | Description |
|------|-------------|
| `-f` / `--file` | Path to the `.prg` file (required for all modes). |
| `-w N` / `--width N` | Truncate cell strings to N characters. Bare `-w` or `-w 0` disables truncation. Default: 50. |
| `-j` / `--json` | Emit machine-readable JSON instead of pretty text. Not available for `--dis`. |

---

## Mode reference

### `--prg`: Architectural overview

```
python prg_inspect.py --prg -f <file.prg> [-w N] [-j]
```

Lists all jobs (with optional description from the embedded comment block) and
all tables (name, address, declared column and row counts).

**Example**
```
python prg_inspect.py --prg -f demo.prg
python prg_inspect.py --prg -f demo.prg -j
```

---

### `--job`: Job dump

```
python prg_inspect.py --job <JOB> [<JOB> ...] -f <file.prg> [-w N] [-j] [--heuristic]
```

Displays for one or more jobs:
- The job's embedded description (comments, arguments, results)
- All tables referenced by the job, found via three methods (always active):
  1. **Bytecode scan**: string literals passed to `tabset` and similar opcodes
  2. **Comment scan**: `table <Name>` patterns in RESULTCOMMENT/ARGCOMMENT lines, or directly in Argument/Result names
  3. **Recursive cell scan**: if a cell value in a discovered table matches a known table name, that table is fetched and followed transitively (BFS)

**Options**

`--heuristic`: enables a fourth, optional discovery method - `_XXX` suffix
patterns found in comment text are expanded into all table names sharing that
prefix (e.g. `table DID_XXX` => all tables starting with `DID_`).
This is a non-standard heuristic; the real EDIABAS format does not use wildcard
table references.

**Example**
```
python prg_inspect.py --job JOB_DEMO -f demo.prg
python prg_inspect.py --job JOB_DEMO -f demo.prg -w 80 -j
python prg_inspect.py --job JOB_DEMO -f demo.prg --heuristic
```

---

### `--table`: Named table dump

```
python prg_inspect.py --table <TABLE> [<TABLE> ...] -f <file.prg> [-w N] [-j]
```

Dumps one or more tables by name (case-insensitive).  Multiple names can be
provided; each is printed in sequence.

**Example**
```
python prg_inspect.py --table FORTTEXTE -f demo.prg
python prg_inspect.py --table SIMPLE_ENUM FORTTEXTE -f demo.prg -w
python prg_inspect.py --table RECURSIVE_DEMO -f demo.prg -j
```

---

### `--dtc`: Fault-code table dump

```
python prg_inspect.py --dtc -f <file.prg> [-w N] [-j]
```

Dumps tables whose names contain `FORTTEXTE` (fault location text).  This is
the standard DTC table family found in BMW ECU files.

**Example**
```
python prg_inspect.py --dtc -f demo.prg
python prg_inspect.py --dtc -f demo.prg -w 80
python prg_inspect.py --dtc -f demo.prg -j
```

---

### `--dis`: Bytecode disassembly

```
python prg_inspect.py --dis <JOB> [<JOB> ...] -f <file.prg>
```

Disassembles the EDIABAS bytecode of one or more jobs.  Each instruction is shown
with its absolute file address, mnemonic, and decoded operands.  Table names
referenced in the bytecode are listed at the top.  JSON output is not supported
for this mode.

**Example**
```
python prg_inspect.py --dis JOB_DEMO -f demo.prg
python prg_inspect.py --dis READ_FAULT_MEMORY -f demo.prg
```

---

## Knowledge sources

Binary file format, opcode definitions, addressing modes, and the XOR-0xF7
obfuscation scheme are derived from the reference C# implementation:

**`EdiabasLib/EdiabasLib/EdiabasNet.cs`**  
<https://github.com/uholeschak/ediabaslib>

Specific items referenced (not necessarily exhaustive):
- `ReadAllTables()`: table list offset (0x84) and table entry layout (0x50 bytes)
- `GetJobList()`: job list offset (0x88) and job entry layout (0x44 bytes)
- `ReadDescriptions()`: description block offset (0x90)
- `ReadAndDecryptBytes()`: XOR-0xF7 obfuscation applied to all encrypted regions
- `OpAddrMode` enum: addressing mode constants
- `OcList`: opcode mnemonic table

---

## Demo file

An arbitrary demo file (`examples/demo.prg`) is included for testing all modes. It contains three jobs and five tables covering every inspection mode.
