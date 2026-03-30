# prg_inspect

Inspection tool for EDIABAS `.prg` and `.grp` binary files.

> **Note**: This tool originally started as a vibe coding project.

## Usage

```
python prg_inspect.py <mode> <file.prg> [options]
```

### Modes

| Mode | Description |
|------|-------------|
| `prg` | Architectural overview: all jobs and tables |
| `job` | Deep dump of a single job with description and referenced tables |
| `table` | Dump one or more named tables |
| `dtc` | Dump fault-code tables (`FORTTEXTE`) |
| `dis` | Disassemble a job's bytecode |

---

## Common options

| Flag | Description |
|------|-------------|
| `-w N` / `--width N` | Truncate cell strings to N characters. Bare `-w` or `-w 0` disables truncation. Default: 50. |
| `-j` / `--json` | Emit machine-readable JSON instead of pretty text. Not available for `dis`. |

---

## Mode reference

### `prg`: Architectural overview

```
python prg_inspect.py prg <file.prg> [-w N] [-j]
```

Lists all jobs (with optional description from the embedded comment block) and
all tables (name, address, declared column and row counts).

**Example**
```
python prg_inspect.py prg demo.prg
python prg_inspect.py prg demo.prg -j
```

---

### `job`: Job dump

```
python prg_inspect.py job <file.prg> <JOB> [-w N] [-j] [--heuristic]
```

Displays:
- The job's embedded description (comments, arguments, results)
- All tables referenced by the job, found via two methods:
  1. **Bytecode scan**: string literals passed to `tabset` and similar opcodes
  2. **Comment scan**: `table <Name>` patterns in RESULTCOMMENT/ARGCOMMENT lines, or directly in Argument/Result names

Referenced tables are dumped recursively: if a table cell contains the name of
another table, that table is fetched and displayed too.

**Options**

`--heuristic`: additionally expand `_XXX` suffix patterns found in comment
text into prefix-matched table names.  This is a non-standard heuristic; the
real EDIABAS format does not use wildcard table references.

**Example**
```
python prg_inspect.py job demo.prg JOB_DEMO
python prg_inspect.py job demo.prg JOB_DEMO -w 80 -j
python prg_inspect.py job demo.prg JOB_DEMO --heuristic
```

---

### `table`: Named table dump

```
python prg_inspect.py table <file.prg> <TABLE> [<TABLE> ...] [-w N] [-j]
```

Dumps one or more tables by name (case-insensitive).  Multiple names can be
provided; each is printed in sequence.

**Example**
```
python prg_inspect.py table demo.prg FORTTEXTE
python prg_inspect.py table demo.prg SIMPLE_ENUM FORTTEXTE -w
python prg_inspect.py table demo.prg RECURSIVE_DEMO -j
```

---

### `dtc`: Fault-code table dump

```
python prg_inspect.py dtc <file.prg> [-w N] [-j]
```

Dumps tables whose names contain `FORTTEXTE` (fault location text).  This is
the standard DTC table family found in BMW ECU files.

**Example**
```
python prg_inspect.py dtc demo.prg
python prg_inspect.py dtc demo.prg -w 80
python prg_inspect.py dtc demo.prg -j
```

---

### `dis`: Bytecode disassembly

```
python prg_inspect.py dis <file.prg> <JOB>
```

Disassembles the EDIABAS bytecode of the named job.  Each instruction is shown
with its absolute file address, mnemonic, and decoded operands.  Table names
referenced in the bytecode are listed at the top.  JSON output is not supported
for this mode.

**Example**
```
python prg_inspect.py dis demo.prg JOB_DEMO
python prg_inspect.py dis demo.prg READ_FAULT_MEMORY
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
