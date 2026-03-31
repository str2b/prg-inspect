"""
prg_doc_gen.py - EDIABAS PRG Documentation Generator
======================================================

Description
-----------
Generates a self-contained, interactive HTML documentation report for a PRG file.
Aggregates job descriptions, table links, and global table definitions.
All tables are stored once in a global section and cross-referenced via anchor links.

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
HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PRG Documentation: {filename}</title>
    <style>
        :root {{
            --bg:           #f4f5f7;
            --card-bg:      #ffffff;
            --text:         #212529;
            --text-muted:   #6c757d;
            --border:       #dee2e6;
            --border-hover: #adb5bd;
            --accent:       #007bff;
            --accent-dim:   rgba(0,123,255,0.08);
            --header-bg:    #212529;
            --hover-bg:     #f1f3f5;
            --tag-bg:       #f1f3f5;
        }}
        *, *::before, *::after {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
            color: var(--text);
            background: var(--bg);
            margin: 0;
            padding: 20px;
            max-width: 1200px;
            margin-inline: auto;
        }}
        /* Page header */
        .page-header {{
            background: var(--header-bg);
            color: #fff;
            padding: 20px 24px;
            border-radius: 8px;
            margin-bottom: 32px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}
        .page-header h1 {{ margin: 0 0 4px; font-size: 1.6rem; }}
        .page-header p  {{ margin: 0; opacity: 0.65; font-size: 0.85rem; }}
        .page-header .stats {{
            display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap;
        }}
        .page-header .stat {{
            background: rgba(255,255,255,0.12);
            padding: 3px 12px;
            border-radius: 20px;
            font-size: 0.84rem;
        }}
        .page-header .stat a {{ color: inherit; text-decoration: none; }}
        .page-header .stat:hover {{ background: rgba(255,255,255,0.2); }}
        /* Section headings */
        .section-heading {{
            font-size: 0.78rem;
            font-weight: 700;
            color: var(--text-muted);
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin: 32px 0 10px;
            padding-bottom: 6px;
            border-bottom: 2px solid var(--border);
        }}
        /* Shared card */
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            margin-bottom: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            overflow: hidden;
        }}
        /* Job cards (collapsible) */
        details.card > summary {{
            padding: 11px 16px;
            font-weight: 600;
            cursor: pointer;
            list-style: none;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            transition: background 0.15s;
        }}
        details.card > summary:hover {{ background: var(--hover-bg); }}
        details.card > summary::after {{
            content: "+";
            font-size: 1.3rem;
            line-height: 1;
            flex-shrink: 0;
            color: var(--text-muted);
        }}
        details.card[open] > summary::after {{ content: "−"; }}
        .job-title {{ display: flex; flex-direction: column; min-width: 0; }}
        .job-name  {{ font-family: monospace; font-size: 0.95rem; }}
        .job-desc  {{
            font-weight: normal;
            font-size: 0.78rem;
            color: var(--text-muted);
            margin-top: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        /* Table cards (static) — same card, accent left stripe instead of dark header */
        .table-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 9px 16px;
            border-left: 4px solid var(--accent);
            background: var(--accent-dim);
        }}
        .table-card-name {{
            font-family: monospace;
            font-weight: 700;
            font-size: 0.95rem;
        }}
        .table-card-meta {{
            font-size: 0.76rem;
            color: var(--text-muted);
        }}
        /* Card body shared by both jobs and tables */
        .card-body {{
            padding: 16px;
            border-top: 1px solid var(--border);
        }}
        /* Inner sections */
        .inner-section {{ margin-bottom: 18px; }}
        .inner-section:last-child {{ margin-bottom: 0; }}
        .inner-heading {{
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            color: var(--text-muted);
            margin: 0 0 7px;
        }}
        /* Data tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.86rem;
            margin: 0;
        }}
        th, td {{
            text-align: left;
            padding: 6px 10px;
            border: 1px solid var(--border);
        }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        tr:nth-child(even) {{ background: #fafbfc; }}
        /* Reference pill lists */
        .ref-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .ref-item {{
            background: var(--tag-bg);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 1px 9px;
            font-size: 0.81rem;
            transition: background 0.15s, border-color 0.15s;
        }}
        .ref-item:hover {{ background: #e9ecef; border-color: var(--border-hover); }}
        .ref-item a {{ color: var(--accent); text-decoration: none; font-weight: 500; }}
        .ref-item a:hover {{ text-decoration: underline; }}
        /* Inline table name hyperlinks */
        .ref-link {{ color: var(--accent); text-decoration: none; font-weight: 500; }}
        .ref-link:hover {{ text-decoration: underline; }}
        /* Description prose */
        .desc-text {{ font-size: 0.875rem; line-height: 1.6; margin: 0; }}
        /* Footer */
        footer {{
            text-align: center;
            margin-top: 48px;
            padding: 16px;
            font-size: 0.76rem;
            color: var(--text-muted);
        }}
        /* Back button */
        #back-btn {{
            position: fixed;
            bottom: 28px; right: 28px;
            padding: 10px 22px;
            background: var(--accent);
            color: #fff;
            border: none;
            border-radius: 50px;
            box-shadow: 0 4px 14px rgba(0,123,255,0.35);
            cursor: pointer;
            display: none;
            z-index: 1000;
            font-weight: 600;
            font-size: 0.88rem;
            transition: transform 0.15s, background 0.15s;
        }}
        #back-btn:hover  {{ transform: scale(1.05); background: #0056b3; }}
        #back-btn:active {{ transform: scale(0.95); }}
        @media print {{
            .card {{ box-shadow: none; break-inside: avoid; }}
            details.card > summary::after {{ display: none; }}
            .page-header {{ background: none; color: #000; border: 1px solid #000; box-shadow: none; }}
            #back-btn {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div class="page-header">
        <h1>PRG Documentation: {filename}</h1>
        <p>{filepath}</p>
        <div class="stats">
            <div class="stat"><a href="#jobs">Jobs: {job_count}</a></div>
            <div class="stat"><a href="#tables">Tables: {table_count}</a></div>
            <div class="stat">Generated: {timestamp}</div>
        </div>
    </div>

    <div class="section-heading" id="jobs">Jobs</div>
    {jobs_html}

    <div class="section-heading" id="tables">Tables</div>
    {tables_html_global}

    <button id="back-btn" onclick="window.history.back()">&#8592; Back</button>
    <footer>Generated by prg_doc_gen.py</footer>

    <script>
        function updateBackBtn() {{
            const btn = document.getElementById('back-btn');
            const h = window.location.hash;
            btn.style.display = (h && h !== '#jobs' && h !== '#tables') ? 'block' : 'none';
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

    # ------------------------------------------------------------------
    # Data acquisition
    # ------------------------------------------------------------------
    def _run_inspect(self, extra_args):
        cmd = self.inspector_cmd + extra_args + ["-f", self.prg_file, "-j"]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, encoding="utf-8"
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Error running prg_inspect.py: {e.stderr}", file=sys.stderr)
        except Exception as e:
            print(f"Failed to parse JSON: {e}", file=sys.stderr)
        return None

    def generate(self, output_file):
        print("Reading architectural overview...")
        overview = self._run_inspect(["--prg"])
        if not overview:
            return False

        jobs_list      = overview.get("jobs", [])
        tables_list    = overview.get("tables", [])
        total_jobs     = len(jobs_list)
        all_job_data   = []
        global_tables  = {}  # name -> row data

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
                for t_name, t_data in job_info.get("table_data", {}).items():
                    global_tables.setdefault(t_name, t_data)

        # Fetch tables not referenced by any job
        total_tables_count = len(tables_list)
        tables_from_jobs   = len(global_tables)
        remaining_tables   = [t["name"] for t in tables_list if t["name"] not in global_tables]

        if remaining_tables:
            print(
                f"\nCollected {tables_from_jobs} tables from jobs. "
                f"Fetching {len(remaining_tables)} remaining (Total: {total_tables_count})..."
            )
            for i in range(0, len(remaining_tables), 50):
                chunk = remaining_tables[i : i + 50]
                table_details = self._run_inspect(["--table"] + chunk)
                if table_details and table_details.get("tables"):
                    for t_info in table_details["tables"]:
                        global_tables.setdefault(t_info["name"], t_info.get("data", []))
        else:
            print(f"\nAll {total_tables_count} tables already collected from jobs.")

        print("Building HTML documentation...")
        self._write_html(overview, all_job_data, global_tables, output_file)
        return True

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_link_pattern(table_names):
        """Compile a single regex matching any table name as a whole word."""
        if not table_names:
            return None
        parts = [re.escape(n) for n in sorted(table_names, key=len, reverse=True)]
        return re.compile(r"\b(" + "|".join(parts) + r")\b")

    def _link_tables(self, text, pattern):
        """Hyperlink bare table names found in free-form text."""
        if not text or not pattern:
            return text
        return pattern.sub(
            lambda m: f'<a href="#table_{m.group(0)}" class="ref-link">{m.group(0)}</a>',
            text,
        )

    def _render_data_table(self, data, link_pattern=None):
        """Render a 2-D list as an HTML <table> (row 0 = header)."""
        if not data:
            return "<p style='color:#999; font-size:0.85rem;'>Empty table</p>"
        html = "<table><thead><tr>"
        for h in data[0]:
            html += f"<th>{h}</th>"
        html += "</tr></thead><tbody>"
        for row in data[1:]:
            html += "<tr>"
            for cell in row:
                text = str(cell)
                if link_pattern and any(c.isalpha() for c in text):
                    text = self._link_tables(text, link_pattern)
                html += f"<td>{text}</td>"
            html += "</tr>"
        html += "</tbody></table>"
        return html

    def _render_ref_section(self, title, items):
        """
        Render a labelled pill-list of cross-reference links.
        items: iterable of (href, label_html) tuples.
        """
        if not items:
            return ""
        pills = "".join(
            f"<li class='ref-item'><a href='{href}'>{label}</a></li>"
            for href, label in items
        )
        return (
            f"<div class='inner-section'>"
            f"<p class='inner-heading'>{title}</p>"
            f"<ul class='ref-list'>{pills}</ul>"
            f"</div>"
        )

    def _render_args_or_results(self, rows, title, link_pattern):
        """Render an args or results list as a labelled data table."""
        if not rows:
            return ""
        cells = "".join(
            f"<tr>"
            f"<td>{r.get('name','')}</td>"
            f"<td>{r.get('type','')}</td>"
            f"<td>{self._link_tables(r.get('comment',''), link_pattern)}</td>"
            f"</tr>"
            for r in rows
        )
        return (
            f"<div class='inner-section'>"
            f"<p class='inner-heading'>{title}</p>"
            f"<table><thead><tr><th>Name</th><th>Type</th><th>Comment</th></tr></thead>"
            f"<tbody>{cells}</tbody></table>"
            f"</div>"
        )

    def _render_job(self, job, link_pattern):
        """Render one job as a collapsible card."""
        name      = job["job"]
        desc_meta = job.get("description", {})
        comments  = " ".join(desc_meta.get("comments", []))

        desc_html = ""
        if comments:
            linked = self._link_tables(comments, link_pattern)
            desc_html = (
                f"<div class='inner-section'>"
                f"<p class='inner-heading'>Description</p>"
                f"<p class='desc-text'>{linked}</p>"
                f"</div>"
            )

        args_html = self._render_args_or_results(desc_meta.get("args", []),    "Arguments", link_pattern)
        res_html  = self._render_args_or_results(desc_meta.get("results", []), "Results",   link_pattern)

        # Build ref pill items, deduplicating and annotating reason
        ref_items = []
        seen = set()
        for ref_disp in job.get("referenced_tables", []):
            base = ref_disp.split(" (Linked")[0].strip().upper()
            if base in seen:
                continue
            seen.add(base)
            if "(Linked via" in ref_disp:
                reason = ref_disp.split("(Linked via ")[1].rstrip(")")
                label = f"{base} <small style='color:#999;font-weight:normal'>({reason})</small>"
            else:
                label = base
            ref_items.append((f"#table_{base}", label))

        refs_html = self._render_ref_section("Referenced Tables", ref_items)
        snippet   = (comments[:110] + "\u2026") if len(comments) > 110 else comments

        return (
            f'<details class="card" id="{name}">'
            f'<summary>'
            f'<div class="job-title">'
            f'<span class="job-name">{name}</span>'
            f'<span class="job-desc">{snippet}</span>'
            f'</div>'
            f'</summary>'
            f'<div class="card-body">{desc_html}{args_html}{res_html}{refs_html}</div>'
            f'</details>\n'
        )

    def _render_table(self, t_name, t_data, t_meta, ref_jobs, link_pattern):
        """Render one global table as a static card."""
        cols = t_meta.get("cols", "?")
        rows = t_meta.get("rows", "?")

        ref_items = [(f"#{rj}", rj) for rj in sorted(ref_jobs)]
        refs_html = self._render_ref_section("Referenced by Jobs", ref_items)

        return (
            f"<div class='card' id='table_{t_name}'>"
            f"<div class='table-card-header'>"
            f"<span class='table-card-name'>{t_name}</span>"
            f"<span class='table-card-meta'>{cols} cols &times; {rows} rows</span>"
            f"</div>"
            f"<div class='card-body'>"
            f"<div class='inner-section'>{self._render_data_table(t_data, link_pattern)}</div>"
            f"{refs_html}"
            f"</div>"
            f"</div>\n"
        )

    # ------------------------------------------------------------------
    # HTML assembly
    # ------------------------------------------------------------------
    def _write_html(self, overview, detailed_jobs, global_tables, output_file):
        filename  = os.path.basename(self.prg_file)
        filepath  = os.path.abspath(self.prg_file)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        job_count   = len(overview.get("jobs", []))
        table_count = len(overview.get("tables", []))

        # Pre-index table metadata to avoid O(n²) lookups in the render loop
        table_meta    = {t["name"]: t for t in overview.get("tables", [])}
        table_to_jobs = {t["name"]: t.get("referenced_by_jobs", []) for t in overview.get("tables", [])}

        link_pattern = self._build_link_pattern(global_tables.keys())

        jobs_html = "".join(
            self._render_job(job, link_pattern) for job in detailed_jobs
        )
        tables_html_global = "".join(
            self._render_table(
                t_name, t_data,
                table_meta.get(t_name, {}),
                table_to_jobs.get(t_name, []),
                link_pattern,
            )
            for t_name, t_data in sorted(global_tables.items())
        )

        html = HTML_TEMPLATE.format(
            filename=filename,
            filepath=filepath,
            job_count=job_count,
            table_count=table_count,
            timestamp=timestamp,
            jobs_html=jobs_html,
            tables_html_global=tables_html_global,
        )

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)


# ===========================================================================
# Command dispatcher
# ===========================================================================
def cmd_generate(args):
    """Main execution path for documentation generation."""
    if not args.output:
        args.output = os.path.splitext(args.file)[0] + ".html"

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
    parser.add_argument("-f", "--file",   required=True, help="Path to .prg file")
    parser.add_argument("-o", "--output", help="Output HTML file path (default: <input>.html)")
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
    args   = parser.parse_args()
    cmd_generate(args)


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()

