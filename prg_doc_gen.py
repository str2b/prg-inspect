"""
prg_doc_gen.py - EDIABAS PRG Documentation Generator
======================================================

Description
-----------
Generates a self-contained, interactive HTML documentation report for a PRG file.
Aggregates job descriptions, table links, and global table definitions.
To optimize performance and eliminate data redundancy, all tables are stored in
a global section and cross-referenced via anchor links.

Usage
-----
  python prg_doc_gen.py -f <file.prg> [-o <output.html>] [--heuristic]

Dependencies
------------
Requires prg_inspect.py in the same directory as a subprocess engine.
"""

import os
import sys
import json
import subprocess
import argparse
import re
from datetime import datetime

# ===========================================================================
# HTML Template
# ===========================================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PRG Documentation: {filename}</title>
    <style>
        :root {{
            --bg-color: #f8f9fa;
            --text-color: #212529;
            --header-bg: #343a40;
            --header-text: #ffffff;
            --job-bg: #ffffff;
            --border-color: #dee2e6;
            --accent-color: #007bff;
            --summary-hover: #e9ecef;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
            color: var(--text-color);
            background-color: var(--bg-color);
            margin: 0;
            padding: 20px;
        }}
        .header {{
            background: var(--header-bg);
            color: var(--header-text);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header h1 {{ margin: 0; font-size: 1.8rem; }}
        .header p {{ margin: 5px 0 0 0; opacity: 0.8; font-size: 0.9rem; }}

        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 15px;
            font-size: 0.9rem;
        }}
        .stat-item {{
            background: rgba(255,255,255,0.1);
            padding: 5px 12px;
            border-radius: 4px;
        }}
        .stat-item a {{
            color: inherit;
            text-decoration: none;
        }}
        .stat-item:hover {{
            background: rgba(255,255,255,0.2);
        }}

        details {{
            background: var(--job-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            margin-bottom: 15px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        summary {{
            padding: 12px 20px;
            font-weight: 600;
            cursor: pointer;
            list-style: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: background 0.2s;
        }}
        summary:hover {{
            background: var(--summary-hover);
        }}
        summary::after {{
            content: "+";
            font-size: 1.5rem;
            line-height: 0;
            margin-left: 10px;
        }}
        details[open] summary::after {{
            content: "-";
        }}
        summary .job-title {{
            display: flex;
            flex-direction: column;
        }}
        summary .job-desc {{
            font-weight: normal;
            font-size: 0.85rem;
            color: #6c757d;
            margin-top: 2px;
        }}

        .job-content {{
            padding: 20px;
            border-top: 1px solid var(--border-color);
        }}

        section {{
            margin-bottom: 25px;
        }}
        section:last-child {{ margin-bottom: 0; }}
        h3 {{
            margin-top: 0;
            font-size: 1.1rem;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 5px;
            margin-bottom: 12px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            margin-bottom: 15px;
        }}
        th, td {{
            text-align: left;
            padding: 8px 12px;
            border: 1px solid var(--border-color);
        }}
        th {{
            background-color: #f1f3f5;
            font-weight: 600;
        }}
        tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}

        .ref-link {{
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 500;
        }}
        .ref-link:hover {{ text-decoration: underline; }}

        .table-data-container {{
            margin-top: 15px;
            padding: 15px;
            background: #fff;
            border: 1px dashed #adb5bd;
            border-radius: 4px;
        }}
        .table-name {{
            font-family: monospace;
            font-weight: bold;
            display: block;
            margin-bottom: 5px;
        }}

        footer {{
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            font-size: 0.8rem;
            color: #6c757d;
        }}

        #back-btn {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            padding: 12px 24px;
            background: var(--accent-color);
            color: white;
            border: none;
            border-radius: 50px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            cursor: pointer;
            display: none;
            z-index: 1000;
            font-weight: bold;
            transition: transform 0.2s, background 0.2s;
        }}
        #back-btn:hover {{
            transform: scale(1.05);
            background: #0056b3;
        }}
        #back-btn:active {{
            transform: scale(0.95);
        }}

        @media print {{
            details {{ box-shadow: none; border: 1px solid #000; break-inside: avoid; }}
            summary::after {{ display: none; }}
            .header {{ background: none; color: #000; border: 1px solid #000; box-shadow: none; }}
            #back-btn {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>PRG Documentation: {filename}</h1>
        <p>Location: {filepath}</p>
        <div class="stats">
            <div class="stat-item"><a href="#jobs">Jobs: {job_count}</a></div>
            <div class="stat-item"><a href="#tables">Tables: {table_count}</a></div>
            <div class="stat-item">Generated: {timestamp}</div>
        </div>
    </div>

    <div class="jobs">
        <h2 id="jobs">Jobs</h2>
        {jobs_html}
    </div>

    <div class="tables-global">
        <h2 id="tables">Tables</h2>
        {tables_html_global}
    </div>

    <button id="back-btn" onclick="window.history.back()">← Back</button>

    <footer>
        Generated by prg_doc_gen.py
    </footer>

    <script>
        // Show/hide back button based on hash presence
        function updateBackBtn() {{
            const btn = document.getElementById('back-btn');
            if (window.location.hash && window.location.hash !== '#jobs' && window.location.hash !== '#tables') {{
                btn.style.display = 'block';
            }} else {{
                btn.style.display = 'none';
            }}
        }}
        window.addEventListener('hashchange', updateBackBtn);
        window.addEventListener('load', updateBackBtn);
    </script>
</body>
</html>
"""


# ===========================================================================
# Generator Logic
# ===========================================================================
class DocGenerator:
    def __init__(self, prg_file, heuristic=False):
        self.prg_file = prg_file
        self.heuristic = heuristic
        self.inspector_cmd = ["python", "prg_inspect.py"]

    def _run_inspect(self, extra_args):
        cmd = self.inspector_cmd + extra_args + ["-f", self.prg_file, "-j"]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, encoding="utf-8"
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Error running prg_inspect.py: {e.stderr}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Failed to parse JSON: {e}", file=sys.stderr)
            return None

    def generate(self, output_file):
        print(f"Reading architectural overview...")
        overview = self._run_inspect(["--prg"])
        if not overview:
            return False

        jobs_list = overview.get("jobs", [])
        tables_list = overview.get("tables", [])
        total_jobs = len(jobs_list)
        all_job_data = []
        global_tables = {}  # name -> data

        print(f"Collecting deep details for {total_jobs} jobs...")
        for i, job_meta in enumerate(jobs_list):
            job_name = job_meta["name"]
            print(f" [{i+1}/{total_jobs}] {job_name}...", end="\x1b[K\r")

            job_args = ["--job", job_name]
            if self.heuristic:
                job_args.append("--heuristic")

            job_details = self._run_inspect(job_args)
            if job_details and job_details.get("jobs"):
                job_info = job_details["jobs"][0]
                all_job_data.append(job_info)
                # Sink tables into global map
                for t_name, t_data in job_info.get("table_data", {}).items():
                    if t_name not in global_tables:
                        global_tables[t_name] = t_data

        # Fetch remaining tables that weren't referenced by any job
        total_tables_count = len(tables_list)
        tables_from_jobs = len(global_tables)
        remaining_tables = [
            t["name"] for t in tables_list if t["name"] not in global_tables
        ]

        if remaining_tables:
            print(
                f"\nCollected {tables_from_jobs} tables from jobs. "
                f"Fetching {len(remaining_tables)} remaining (Total: {total_tables_count})..."
            )
            # Batch fetch in chunks to avoid command line length limits
            chunk_size = 50
            for i in range(0, len(remaining_tables), chunk_size):
                chunk = remaining_tables[i : i + chunk_size]
                table_details = self._run_inspect(["--table"] + chunk)
                if table_details and table_details.get("tables"):
                    for t_info in table_details["tables"]:
                        global_tables[t_info["name"]] = t_info.get("data", [])
        else:
            print(f"\nAll {total_tables_count} tables already collected from jobs.")

        print(f"Building HTML documentation...")
        self._write_html(overview, all_job_data, global_tables, output_file)
        return True

    def _link_tables(self, text, pattern):
        if not text or not pattern:
            return text
        return pattern.sub(
            lambda m: f'<a href="#table_{m.group(0)}" class="ref-link">{m.group(0)}</a>',
            text,
        )

    def _format_table(self, data, caption=None, link_pattern=None):
        if not data:
            return "<p>Empty table</p>"

        html = "<table>"
        if caption:
            html += f"<caption style='text-align:left; font-weight:bold; margin-bottom:5px;'>{caption}</caption>"

        # Header (row 0)
        html += "<thead><tr>"
        for h in data[0]:
            html += f"<th>{h}</th>"
        html += "</tr></thead>"

        # Rows
        html += "<tbody>"
        for row in data[1:]:
            html += "<tr>"
            for cell in row:
                cell_text = str(cell)
                if link_pattern and any(c.isalpha() for c in cell_text):
                    cell_text = self._link_tables(cell_text, link_pattern)
                html += f"<td>{cell_text}</td>"
            html += "</tr>"
        html += "</tbody>"
        html += "</table>"
        return html

    def _write_html(self, overview, detailed_jobs, global_tables, output_file):
        filename = os.path.basename(self.prg_file)
        filepath = os.path.abspath(self.prg_file)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        job_count = len(overview.get("jobs", []))
        table_count = len(overview.get("tables", []))

        # Build a single regex pattern for all table names to optimize linking
        # Sort by length descending to avoid partial matches
        sorted_names = sorted(global_tables.keys(), key=len, reverse=True)
        link_pattern = None
        if sorted_names:
            regex_parts = [re.escape(name) for name in sorted_names]
            link_pattern = re.compile(r"\b(" + "|".join(regex_parts) + r")\b")

        jobs_html = ""
        for job in detailed_jobs:
            name = job["job"]
            desc_meta = job.get("description", {})
            comments = " ".join(desc_meta.get("comments", []))

            # Link comments
            linked_comments = self._link_tables(comments, link_pattern)

            args_html = ""
            if desc_meta.get("args"):
                args_html = "<section><h3>Arguments</h3>"
                args_html += "<table><thead><tr><th>Name</th><th>Type</th><th>Comment</th></tr></thead><tbody>"
                for arg in desc_meta["args"]:
                    linked_arg_comment = self._link_tables(arg["comment"], link_pattern)
                    args_html += f"<tr><td>{arg['name']}</td><td>{arg['type']}</td><td>{linked_arg_comment}</td></tr>"
                args_html += "</tbody></table></section>"

            res_html = ""
            if desc_meta.get("results"):
                res_html = "<section><h3>Results</h3>"
                res_html += "<table><thead><tr><th>Name</th><th>Type</th><th>Comment</th></tr></thead><tbody>"
                for res in desc_meta["results"]:
                    linked_res_comment = self._link_tables(res["comment"], link_pattern)
                    res_html += f"<tr><td>{res['name']}</td><td>{res['type']}</td><td>{linked_res_comment}</td></tr>"
                res_html += "</tbody></table></section>"

            tables_refs_html = ""
            job_refs = set()
            for ref_disp in job.get("referenced_tables", []):
                base_name = ref_disp.split(" (Linked")[0].strip().upper()
                job_refs.add(base_name)

            if job_refs:
                tables_refs_html = "<section><h3>Referenced Tables</h3><ul>"
                for t_name in sorted(job_refs):
                    display_name = t_name
                    for ref_disp in job.get("referenced_tables", []):
                        if ref_disp.startswith(t_name) and "(Linked via" in ref_disp:
                            reason = ref_disp.split("(Linked via ")[1].rstrip(")")
                            display_name += f" <small style='color:#666; font-weight:normal;'>({reason})</small>"
                            break

                    tables_refs_html += f"<li><a href='#table_{t_name}' class='ref-link'>{display_name}</a></li>"
                tables_refs_html += "</ul></section>"

            jobs_html += f"""
            <details id="{name}">
                <summary>
                    <div class="job-title">
                        <span>{name}</span>
                        <span class="job-desc">{comments[:100]}{'...' if len(comments) > 100 else ''}</span>
                    </div>
                </summary>
                <div class="job-content">
                    {('<section><h3>Description</h3><p>' + linked_comments + '</p></section>') if comments else ''}
                    {args_html}
                    {res_html}
                    {tables_refs_html}
                </div>
            </details>
            """

        tables_html_global = ""
        for t_name, t_data in sorted(global_tables.items()):
            tables_html_global += (
                f"<div class='table-data-container' id='table_{t_name}'>"
            )
            tables_html_global += f"<span class='table-name'>{t_name}</span>"
            tables_html_global += self._format_table(t_data, link_pattern=link_pattern)
            tables_html_global += "</div>"

        final_html = HTML_TEMPLATE.format(
            filename=filename,
            filepath=filepath,
            job_count=job_count,
            table_count=table_count,
            timestamp=timestamp,
            jobs_html=jobs_html,
            tables_html_global=tables_html_global,
        )

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_html)


# ===========================================================================
# Command dispatcher
# ===========================================================================
def cmd_generate(args):
    """Main execution path for documentation generation."""
    if not args.output:
        base = os.path.splitext(args.file)[0]
        args.output = base + ".html"

    gen = DocGenerator(args.file, args.heuristic)
    if gen.generate(args.output):
        print(f"Documentation successfully generated at: {args.output}")
    else:
        print("Documentation generation failed.")
        sys.exit(1)


# ===========================================================================
# Argument parser
# ===========================================================================
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prg_doc_gen",
        description="EDIABAS PRG Documentation Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  prg_doc_gen.py -f ecufile.prg
  prg_doc_gen.py -f ecufile.prg -o my_doc.html --heuristic
""",
    )

    parser.add_argument("-f", "--file", required=True, help="Path to .prg file")
    parser.add_argument(
        "-o", "--output", help="Output HTML file path (default: <input>.html)"
    )
    parser.add_argument(
        "--heuristic",
        action="store_true",
        help="Enable heuristic table matching (passed to prg_inspect.py)",
    )

    return parser


# ===========================================================================
# Entry point
# ===========================================================================
def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()

    cmd_generate(args)


if __name__ == "__main__":
    main()
