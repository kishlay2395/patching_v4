#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import sys
import html
from pathlib import Path
from datetime import datetime
from collections import Counter

# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------

def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")

def safe(v, default="Not Found") -> str:
    v = "" if v is None else str(v).strip()
    return v if v else default

def http_code_only(v: str) -> str:
    m = re.search(r"\b(\d{3})\b", str(v or ""))
    return m.group(1) if m else ""

def cmp_status(a: str, b: str) -> str:
    return "Validated" if str(a) == str(b) else "Need Attention"

def cmp_cups_http(a: str, b: str) -> str:
    a = safe(a, "Not Found/Not Running")
    b = safe(b, "Not Found/Not Running")

    ca = http_code_only(a)
    cb = http_code_only(b)

    return "Validated" if str(ca) == str(cb) else "Need Attention"

def cmp_jboss_http(a: str, b: str) -> str:
    ca = http_code_only(a)
    cb = http_code_only(b)

    return "Validated" if str(ca) == str(cb) else "Need Attention"

def sort_url(url: str):
    """
    Sort URLs like:
      http://1.2.3.4:8080
      1.2.3.4:8080
    """
    u = str(url or "").strip()
    u2 = re.sub(r"^https?://", "", u, flags=re.IGNORECASE)

    if ":" in u2:
        host, port = u2.rsplit(":", 1)
        try:
            return (host, int(port))
        except Exception:
            return (host, port)
    return (u2, 0)

# -----------------------------------------------------------------------------
# Parsing
# -----------------------------------------------------------------------------

def parse_kv(text: str) -> dict:
    kv = {}
    for raw in text.splitlines():
        line = raw.strip()
        if "|" not in line:
            continue
        k, v = [x.strip() for x in line.split("|", 1)]
        if k:
            kv[k] = v
    return kv

def extract_data_mounts(text: str) -> str:
    mounts = []
    in_table = False

    for raw in text.splitlines():
        line = raw.strip()

        if line == "Filesystem | Size | Used | Avail | Use% | Mounted on":
            in_table = True
            continue

        if in_table:
            if line.startswith("====") or line.startswith("SYMLINK CHECK") or line.startswith("NFS CHECK"):
                break
            if "|" not in line:
                continue

            cols = [c.strip() for c in line.split("|")]
            if cols:
                mnt = cols[-1]
                if mnt.startswith("/data"):
                    mounts.append(mnt)

    mounts = sorted(set(mounts))
    return ", ".join(mounts) if mounts else "Not Found"

def extract_shared_mount_points(text: str) -> str:
    targets = []
    in_table = False

    for raw in text.splitlines():
        line = raw.strip()

        if line == "Symlink | ResolvedTarget":
            in_table = True
            continue

        if in_table:
            if line.startswith("====") or line.startswith("NFS CHECK") or line.startswith("CUPS CHECK"):
                break
            if "|" not in line:
                continue

            cols = [c.strip() for c in line.split("|", 1)]
            if len(cols) == 2 and cols[1].startswith("/data"):
                targets.append(cols[1])

    targets = sorted(set(targets))
    return ", ".join(targets) if targets else "Not Found"

def yes_no_status(v: str) -> str:
    v = (v or "").strip().lower()
    if v == "yes":
        return "running"
    if v == "no":
        return "not running"
    return "Not Found/Not Running"

def parse_name_list(v: str):
    raw = safe(v, "").strip()
    if not raw:
        return []

    low = raw.lower()
    if low in {"not found", "not found/not running", "not running", "none"}:
        return []

    if re.fullmatch(r"\d+", raw):
        return []

    parts = [x.strip() for x in raw.split(",")]
    out = []

    for p in parts:
        if not p:
            continue
        pl = p.lower()
        if pl in {"not found", "not found/not running", "not running", "none"}:
            continue
        out.append(p)

    return out

def pick_cups_ip_code(text: str) -> str:
    m = re.search(r"^CUPS IP URL \(http://[^)]+:631\)\s*\|\s*(.+)$", text, re.MULTILINE)
    if not m:
        return "Not Found/Not Running"

    val = m.group(1).strip()
    if not val or val.lower() == "not found":
        return "Not Found/Not Running"

    code = http_code_only(val)
    return f"HTTP {code}" if code else safe(val, "Not Found/Not Running")

def parse_app_table(text: str):
    rows = []
    lines = text.splitlines()
    header = "PID | AppName | JbossVersion | Java-Name | Port | URL | Status | Code | SSL-Status | App-Path"
    start = None

    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i + 1
            break

    if start is None:
        return rows

    for line in lines[start:]:
        line = line.strip()
        if not line or line.startswith("===="):
            break
        if "|" not in line:
            continue

        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 10:
            continue

        rows.append({
            "PID": cols[0],
            "AppName": cols[1],
            "JbossVersion": cols[2],
            "Java-Name": cols[3],
            "Port": cols[4],
            "URL": cols[5],
            "Status": cols[6],
            "Code": cols[7],
            "SSL-Status": cols[8],
            "App-Path": cols[9],
        })

    return rows

def parse_batch_table(text: str, section_title: str = "BATCH/DAEMON JAVA DETAILS"):
    rows = []
    lines = text.splitlines()
    header = "Java-Name | Java-Path"
    start = None
    in_section = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == section_title:
            in_section = True
            continue
        if in_section and stripped == header:
            start = i + 1
            break

    if start is None:
        return rows

    for line in lines[start:]:
        line = line.strip()
        if not line or line.startswith("===="):
            break
        if "|" not in line:
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 2:
            continue
        rows.append({"Java-Name": cols[0], "Java-Path": cols[1]})

    return rows


def derive_jboss_summary(app_rows):
    codes = []
    for r in app_rows:
        c = http_code_only(r.get("Code", "")) or safe(r.get("Code", ""), "")
        if c and c.lower() != "not found":
            codes.append(c)

    if not codes:
        return "Not Found/Not Running"

    preferred = next((c for c in codes if c in {"200", "301", "302", "401", "403"}), codes[0])
    return f"HTTP {preferred}"

def parse_log(path: str):
    text = read_text(path)
    kv = parse_kv(text)
    app_rows = parse_app_table(text)
    batch_detail_rows = parse_batch_table(text)

    batch_detail_rows = parse_batch_table(text, "BATCH/DAEMON JAVA DETAILS")
    cron_detail_rows = parse_batch_table(text, "CRON TRIGGERED JAVA DETAILS")

    pkg = (kv.get("NFS Package Installed") or "").strip().lower()
    if pkg == "yes":
        nfs_srv_pkg = "Service Available"
        nfs_cli_pkg = "Service Available"
    elif pkg == "no":
        nfs_srv_pkg = "Service is Unavailable"
        nfs_cli_pkg = "Service is Unavailable"
    else:
        nfs_srv_pkg = "Not Found/Not Running"
        nfs_cli_pkg = "Not Found/Not Running"

    daemon_batch_count = kv.get("Batch/Daemon Java Processes") or ""
    daemon_batch_names_raw = kv.get("Non-Standalone Java Processes") or ""

    daemon_batch_val = daemon_batch_count or daemon_batch_names_raw or ""
    batch_names = parse_name_list(daemon_batch_names_raw)

    

    summary = {
        "Server IP": safe(kv.get("Server IP")),
        "Time Zone Information": safe(kv.get("Time Zone")),
        "Mounted on (data*)": extract_data_mounts(text),
        "Shared Mount point": extract_shared_mount_points(text),
        "NFS Server Package Availability": nfs_srv_pkg,
        "NFS Server Status": yes_no_status(kv.get("nfs-server.service Active")),
        "NFS Client Target Package Availability": nfs_cli_pkg,
        "NFS Client Target Status": yes_no_status(kv.get("nfs-client.target Active")),
        "Cups Service Status": yes_no_status(kv.get("CUPS Running")),
        "CUPS Service Version": safe(kv.get("CUPS Version"), "Not Found"),
        "CUPS IP URL Validation": pick_cups_ip_code(text),
        "JBOSS Application URL Validation": derive_jboss_summary(app_rows),
        "FTP Service Status": yes_no_status(kv.get("FTP Running (Port 21 localhost)")),
        "Number of Printers": safe(kv.get("Printers Configured"), "Not Found/Not Running"),
        "Total Number of Java Processes Running": safe(kv.get("Total Java Processes"), "Not Found/Not Running"),
        "Daemon / Batch App Processes": safe(daemon_batch_val, "Not Found/Not Running"),
        "App Processes Running": safe(kv.get("JBoss App Processes"), "Not Found/Not Running"),
        "Cups server Http Status": safe(kv.get("Cups server Http Status"), "Not Found"),
        "Cups printers Http Status": safe(kv.get("Cups printers Http Status"), "Not Found"),
        "Health Monitor Crontab": safe(kv.get("Health Monitor Crontab"), "Not Found"),
    }

    up_count = sum(1 for r in app_rows if str(r.get("Status", "")).strip().upper() == "UP")

    return {
        "summary": summary,
        "app_rows": app_rows,
        "up_url_count": up_count,
        "batch_names": batch_names,
        "batch_detail_rows": batch_detail_rows,
        "cron_detail_rows": cron_detail_rows,
    }


def build_lb_rows(lb_data):
    if not lb_data:
        return []
    try:
        before = lb_data.get("before", {})
        after = lb_data.get("after", {})
        rows = []
        all_tg_arns = set(list(before.keys()) + list(after.keys()))
        for tg_arn in all_tg_arns:
            b = before.get(tg_arn, {})
            a = after.get(tg_arn, {})
            lb_name = b.get("lb_name") or a.get("lb_name", "N/A")
            before_state = b.get("state", "N/A")
            after_state = a.get("state", "N/A")
            status = cmp_status(before_state, after_state)
            rows.append((lb_name, before_state, after_state, status))
        return rows
    except Exception:
        return []
# -----------------------------------------------------------------------------
# Comparison build
# -----------------------------------------------------------------------------

def build_summary(before, after):
    keys = [
        "Server IP",
        "Time Zone Information",
        "Mounted on (data*)",
        "Shared Mount point",
        "NFS Server Package Availability",
        "NFS Server Status",
        "NFS Client Target Package Availability",
        "NFS Client Target Status",
        "Cups Service Status",
        "CUPS Service Version",
        "CUPS IP URL Validation",
        "JBOSS Application URL Validation",
        "FTP Service Status",
        "Number of Printers",
        "Total Number of Java Processes Running",
        "Daemon / Batch App Processes",
        "App Processes Running",
    ]

    rows = []
    for k in keys:
        b = safe(before["summary"].get(k), "Not Found")
        a = safe(after["summary"].get(k), "Not Found")

        if k == "CUPS IP URL Validation":
            st = cmp_cups_http(b, a)
        elif k == "JBOSS Application URL Validation":
            st = cmp_jboss_http(b, a)
        elif k == "CUPS Service Version":
            b_found = (b != "Not Found")
            a_found = (a != "Not Found")
            if b_found == a_found:
                st = "Validated"
            else:
                st = "Need Attention"
        else:
            st = cmp_status(b, a)

        rows.append((k, b, a, st))

    rows.append((
        "Total App URL Running ",
        str(before.get("up_url_count", 0)),
        str(after.get("up_url_count", 0)),
        cmp_status(str(before.get("up_url_count", 0)), str(after.get("up_url_count", 0))),
    ))
    return rows

def build_batch_rows(before, after):
    before_rows = before.get("batch_detail_rows", [])
    after_rows = after.get("batch_detail_rows", [])

    # backward compatibility for old logs where new batch table is absent
    if not before_rows and before.get("batch_names"):
        before_rows = [{"Java-Name": n, "Java-Path": "Unknown"} for n in before.get("batch_names", [])]
    if not after_rows and after.get("batch_names"):
        after_rows = [{"Java-Name": n, "Java-Path": "Unknown"} for n in after.get("batch_names", [])]

    after_map = {}
    for r in after_rows:
        path = safe(r.get("Java-Path"), "Unknown")
        after_map.setdefault(path, []).append(safe(r.get("Java-Name"), "Unknown"))

    rows = []
    for r in before_rows:
        path = safe(r.get("Java-Path"), "Unknown")
        bname = safe(r.get("Java-Name"), "Unknown")

        after_names = after_map.get(path, [])
        if bname in after_names:
            aname = bname
            after_names.remove(bname)
            status = "Validated"
        elif after_names:
            aname = after_names.pop(0)
            status = "Need Attention"
        else:
            aname = "Missing After Patch"
            status = "Need Attention"

        rows.append(("Batch Process Detail", path, bname, aname, status))


    before_path_names = set()
    for r in before_rows:
        before_path_names.add((
            safe(r.get("Java-Path"), "Unknown"),
            safe(r.get("Java-Name"), "Unknown")
        ))

    for r in after_rows:
        path  = safe(r.get("Java-Path"), "Unknown")
        aname = safe(r.get("Java-Name"), "Unknown")
        if (path, aname) not in before_path_names:
            rows.append(("Batch Process Detail", path, "Not Present Before Patch", aname, "Need Attention"))

    return rows



def build_app_rows(before, after):
    def java_name(row):
        jname = (row.get("Java-Name") or "").strip()
        return jname if jname and jname.lower() not in {"notfound", "not found"} else "Unknown"

    def app_path(row):
        apath = (row.get("App-Path") or "").strip()
        return apath if apath and apath.lower() not in {"notfound", "not found"} else "Unknown"

    bmap = {}
    for r in before["app_rows"]:
        url = safe(r.get("URL"), "")
        if url:
            bmap[url] = {
                "path": app_path(r),
                "java": java_name(r),
            }

    amap = {}
    for r in after["app_rows"]:
        url = safe(r.get("URL"), "")
        if url:
            amap[url] = {
                "path": app_path(r),
                "java": java_name(r),
            }

    rows = []
    for url in sorted(set(bmap) | set(amap), key=sort_url):
        bpath = bmap.get(url, {}).get("path", "Not Found")
        bjava = bmap.get(url, {}).get("java", "Not Found")
        ajava = amap.get(url, {}).get("java", "Not Found")

        if bpath == "Not Found":
            bpath = amap.get(url, {}).get("path", "Not Found")
        rows.append((url, bpath, bjava, ajava, cmp_status(bjava, ajava)))

    rows.append((
        "Total App Processes Running",
        "-",
        safe(before["summary"].get("App Processes Running"), "Not Found"),
        safe(after["summary"].get("App Processes Running"), "Not Found"),
        cmp_status(
            safe(before["summary"].get("App Processes Running"), "Not Found"),
            safe(after["summary"].get("App Processes Running"), "Not Found"),
        )
    ))
    return rows

def build_app_status_rows(before, after):
    bmap = {
        r["URL"]: {"status": safe(r.get("Status"), "Not Found"), "code": safe(r.get("Code"), "Not Found")}
        for r in before["app_rows"] if r.get("URL")
    }
    amap = {
        r["URL"]: {"status": safe(r.get("Status"), "Not Found"), "code": safe(r.get("Code"), "Not Found")}
        for r in after["app_rows"] if r.get("URL")
    }

    urls = sorted(set(bmap) | set(amap), key=sort_url)
    rows = []

    for url in urls:
        bs = safe(bmap.get(url, {}).get("status"), "Not Found")
        ps = safe(amap.get(url, {}).get("status"), "Not Found")
        bc = safe(bmap.get(url, {}).get("code"), "Not Found")
        pc = safe(amap.get(url, {}).get("code"), "Not Found")
        rows.append({
            "URL Address": url,
            "Pre-Status": bs,
            "Post-Status": ps,
            "StatusCmp": cmp_status(bs, ps),
            "Pre_HttpCode": bc,
            "Post_HttpCode": pc,
            "HttpCmp": cmp_jboss_http(bc, pc),
        })

    extra_cups_rows = [
        "Cups server Http Status",
        "Cups printers Http Status",
    ]

    for label in extra_cups_rows:
        bc_raw = safe(before["summary"].get(label), "Not Found")
        pc_raw = safe(after["summary"].get(label), "Not Found")

        bc = http_code_only(bc_raw) or bc_raw
        pc = http_code_only(pc_raw) or pc_raw
        status_cmp = "Validated" if bc == pc else "Need Attention"

        rows.append({
            "URL Address": label,
            "Pre-Status": bc,
            "Post-Status": pc,
            "StatusCmp": status_cmp,
            "Pre_HttpCode": "-",
            "Post_HttpCode": "-",
            "HttpCmp": "-",
        })

    return rows

# -----------------------------------------------------------------------------
# Html Reports
# -----------------------------------------------------------------------------

def overall_metrics(summary_rows, batch_rows, app_rows, app_status_rows, lb_rows=None):
    statuses = [r[3] for r in summary_rows]
    statuses += [r[4] for r in batch_rows] if batch_rows else ["Validated"]
    statuses += [r[4] for r in app_rows] if app_rows else ["Validated"]

    for r in app_status_rows:
        if r["HttpCmp"] == "-":
            statuses.append(r["StatusCmp"])
        else:
            statuses.append(
                "Validated"
                if (r["StatusCmp"] == "Validated" and r["HttpCmp"] == "Validated")
                else "Need Attention"
            )
    
    if lb_rows:
        statuses += [r[3] for r in lb_rows]

    total = len(statuses)
    validated = sum(1 for s in statuses if s == "Validated")
    need = total - validated
    rate = int((validated / total) * 100) if total else 0
    return total, validated, need, rate

def build_need_attention_items(summary_rows, batch_rows, app_rows, app_status_rows, lb_rows=None):
    items = []

    # Summary Comparison
    for section, before_val, after_val, status in summary_rows:
        if str(status).strip() == "Need Attention":
            items.append((
                "Summary Comparison",
                section,
                f"Before: {before_val} | After: {after_val}"
            ))

    # Batch Processes Missing After Patching
    for section, path, before_java, after_java, status in batch_rows:
        if str(status).strip() == "Need Attention":
            items.append((
                "Batch Processes Missing After Patching",
                before_java,
                f"Path: {path} | Before Java: {before_java} | After Java: {after_java}"
            ))

    # Application Process Details
    for section, path, before_java, after_java, status in app_rows:
        if str(status).strip() == "Need Attention":
            items.append((
                "Application Process Details",
                section,
                f"Path: {path} | Before Java: {before_java} | After Java: {after_java}"
            ))

    # Application URL Status Comparison
    for r in app_status_rows:
        status_cmp = str(r.get("StatusCmp", "")).strip()
        http_cmp = str(r.get("HttpCmp", "")).strip()

        if status_cmp == "Need Attention" or (http_cmp != "-" and http_cmp == "Need Attention"):
            items.append((
                "Application URL Status Comparison",
                r.get("URL Address", "Unknown"),
                f"Pre-Status: {r.get('Pre-Status', 'Not Found')} | "
                f"Post-Status: {r.get('Post-Status', 'Not Found')} | "
                f"Pre_HttpCode: {r.get('Pre_HttpCode', 'Not Found')} | "
                f"Post_HttpCode: {r.get('Post_HttpCode', 'Not Found')}"
            ))

    if lb_rows:
        for lb_name, before_state, after_state, status in lb_rows:
            if status == "Need Attention":
                items.append((
                    "LB Health Status",
                    lb_name,
                    f"Before: {before_state} | After: {after_state}"
                ))

    return items

def write_html(summary_rows, cron_rows, batch_rows, app_rows, app_status_rows, lb_rows, output_html_file, before_log, after_log, before, after):
    html_file = output_html_file
    total, validated, need, rate = overall_metrics(summary_rows, batch_rows, app_rows, app_status_rows, lb_rows)
    need_attention_items = build_need_attention_items(summary_rows, batch_rows, app_rows, app_status_rows, lb_rows)

    def cls(status):
        status = str(status).strip()
        if status == "-":
            return ""
        return "ok" if status == "Validated" else "warn"

    def table4(title, rows, h1, h2, h3, h4):
        body = []
        for a, b, c, d in rows:
            body.append(
                "<tr>"
                f"<td>{html.escape(str(a))}</td>"
                f"<td>{html.escape(str(b))}</td>"
                f"<td>{html.escape(str(c))}</td>"
                f"<td class='{cls(str(d))}'>{html.escape(str(d))}</td>"
                "</tr>"
            )
        if not body:
            body = ["<tr><td colspan='4'>No data found</td></tr>"]

        return f"""
        <h2>{html.escape(title)}</h2>
        <table>
          <thead>
            <tr><th>{html.escape(h1)}</th><th>{html.escape(h2)}</th><th>{html.escape(h3)}</th><th>{html.escape(h4)}</th></tr>
          </thead>
          <tbody>{''.join(body)}</tbody>
        </table>
        """

    def table5(title, rows, h1, h2, h3, h4, h5):
        body = []
        for a, b, c, d, e in rows:
            body.append(
                "<tr>"
                f"<td>{html.escape(str(a))}</td>"
                f"<td>{html.escape(str(b))}</td>"
                f"<td>{html.escape(str(c))}</td>"
                f"<td>{html.escape(str(d))}</td>"
                f"<td class='{cls(str(e))}'>{html.escape(str(e))}</td>"
                "</tr>"
            )
        if not body:
            body = ["<tr><td colspan='5'>No data found</td></tr>"]

        return f"""
        <h2>{html.escape(title)}</h2>
        <table>
          <thead>
            <tr>
              <th>{html.escape(h1)}</th>
              <th>{html.escape(h2)}</th>
              <th>{html.escape(h3)}</th>
              <th>{html.escape(h4)}</th>
              <th>{html.escape(h5)}</th>
            </tr>
          </thead>
          <tbody>{''.join(body)}</tbody>
        </table>
        """

    attention_body = []
    for section, item_name, details in need_attention_items:
        attention_body.append(
            "<tr>"
            f"<td>{html.escape(str(section))}</td>"
            f"<td>{html.escape(str(item_name))}</td>"
            f"<td class='attention-details'>{html.escape(str(details))}</td>"
            "</tr>"
        )

    attention_section = f"""
    <h2 class="attention-title">Vigilance Summary</h2>
    <table>
        <thead>
            <tr>
            <th>Section</th>
            <th>Name</th>
            <th>Details</th>
            </tr>
        </thead>
        <tbody>
           {''.join(attention_body) if attention_body else '<tr><td colspan="3">No items </td></tr>'}
        </tbody>
    </table>
    """

    if not cron_rows:
        cron_rows = [("Cron Process Detail", "-", "No cron java process found", "-", "-")]

    if not batch_rows:
        batch_rows = [("Batch Process Detail", "-", "No batch process found", "-", "Validated")]

    app_status_body = []
    for r in app_status_rows:
        app_status_body.append(
            "<tr>"
            f"<td>{html.escape(r['URL Address'])}</td>"
            f"<td>{html.escape(r['Pre-Status'])}</td>"
            f"<td>{html.escape(r['Post-Status'])}</td>"
            f"<td class='{cls(r['StatusCmp'])}'>{html.escape(r['StatusCmp'])}</td>"
            f"<td>{html.escape(r['Pre_HttpCode'])}</td>"
            f"<td>{html.escape(r['Post_HttpCode'])}</td>"
            f"<td class='{cls(r['HttpCmp'])}'>{html.escape(r['HttpCmp'])}</td>"
            "</tr>"
        )

    overall_msg = "All Validation Checks Passed" if need == 0 else f"{need} Check(s) Need Attention"

    hm_before = safe(before["summary"].get("Health Monitor Crontab"), "Not Found")
    hm_after = safe(after["summary"].get("Health Monitor Crontab"), "Not Found")

    hm_section = f"""
    <h2>Health Monitor Crontab Status</h2>
    <table>
      <thead>
        <tr>
          <th>Section</th>
          <th>Before Patching</th>
          <th>After Patching</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Health Monitor Crontab</td>
          <td>{html.escape(hm_before)}</td>
          <td>{html.escape(hm_after)}</td>
        </tr>
      </tbody>
    </table>
    """

    doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Validation Comparison Report</title>
<style>
body {{
  font-family: Arial, sans-serif; margin: 0; padding: 20px;
  background: #f5f7fb; color: #222;
}}
.container {{
  max-width: 1250px; margin: 0 auto; background: #fff;
  border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden;
}}
.header {{ background: #1976D2; color: #fff; padding: 20px 24px; }}
.header h1 {{ margin: 0; font-size: 24px; }}
.submeta {{ margin-top: 8px; font-size: 13px; opacity: 0.95; }}
.content {{ padding: 24px; }}
.status-box {{
  margin: 0 0 18px 0; padding: 12px 14px; border-radius: 8px;
  border-left: 5px solid {"#4CAF50" if need == 0 else "#FF9800"};
  background: {"#E8F5E9" if need == 0 else "#FFF3E0"};
}}
.summary {{
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px;
}}
.card {{
  border: 1px solid #e6eaf0; border-left: 4px solid #1976D2;
  border-radius: 8px; padding: 12px; background: #fafcff;
}}
.card .label {{ font-size: 12px; color: #666; margin-bottom: 4px; }}
.card .value {{ font-size: 24px; font-weight: 700; }}
h2 {{ margin-top: 28px; border-bottom: 2px solid #1976D2; padding-bottom: 6px; font-size: 18px; }}
table {{
  width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 20px;
  table-layout: fixed; word-wrap: break-word;
}}
th, td {{
  border: 1px solid #e0e0e0; padding: 10px; text-align: left; vertical-align: top; font-size: 13px;
}}
th {{ background: #1976D2; color: #fff; }}
tr:nth-child(even) td {{ background: #fafafa; }}
.ok {{ color: #2E7D32; font-weight: 700; }}
.warn {{ color: #D84315; font-weight: 700; }}
.attention-title {{ color: #C62828; }}
.attention-details {{ color: #C62828; font-weight: 600; }}
.footer {{
  border-top: 1px solid #e0e0e0; background: #fafafa; padding: 14px 24px; font-size: 12px; color: #666;
}}
@media (max-width: 900px) {{ .summary {{ grid-template-columns: 1fr 1fr; }} }}
@media (max-width: 600px) {{
  .summary {{ grid-template-columns: 1fr; }}
  th, td {{ font-size: 12px; padding: 8px; }}
}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Validation Comparison Report</h1>
    <div class="submeta">
      Before log: <b>{html.escape(before_log)}</b> &nbsp; | &nbsp;
      After log: <b>{html.escape(after_log)}</b>
    </div>
  </div>
  <div class="content">
    <div class="status-box"><strong>{html.escape(overall_msg)}</strong></div>

    <div class="summary">
      <div class="card"><div class="label">Total Checks</div><div class="value">{total}</div></div>
      <div class="card"><div class="label">Validated</div><div class="value">{validated}</div></div>
      <div class="card"><div class="label">Un-Validated</div><div class="value">{need}</div></div>
      <div class="card"><div class="label">Success Rate</div><div class="value">{rate}%</div></div>
    </div>

    {attention_section}

    {table4("Summary Comparison", summary_rows, "Section", "Before Patching", "Post Patching", "Status")}

    {table5("Cron Triggered Java Processes", cron_rows,
            "Section", "Agent Path", "Before Patching Java Name", "After Patching Java Name", "Status")}

    {table5("Batch Processes Missing After Patching", batch_rows,
            "Section", "Agent Path", "Before Patching Java Name", "After Patching Java Name", "Status")}

    {table5("Application Process Details", app_rows,
            "Section / URL", "Application Path", "Before Patching Java Name", "After Patching Java Name", "Status")}


    <h2>Application URL Status Comparison</h2>
    <table>
      <thead>
        <tr>
          <th>URL Address</th>
          <th>Pre-Status</th>
          <th>Post-Status</th>
          <th>Status</th>
          <th>Pre_HttpCode</th>
          <th>Post_HttpCode</th>
          <th>HTTP Compare</th>
        </tr>
      </thead>
      <tbody>
        {''.join(app_status_body) if app_status_body else '<tr><td colspan="7">No app URL entries found</td></tr>'}
      </tbody>
    </table>
    {table4("LB Health Status", lb_rows, "LB Name", "Before Patching", "After Patching", "Status") if lb_rows else ""}
    {hm_section}
  </div>
  <div class="footer">
    Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
  </div>
</div>
</body>
</html>
"""
    Path(html_file).write_text(doc, encoding="utf-8")
    return html_file

# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------

def run_report(before_file, after_file, output_html, lb_data=None):
    if not Path(before_file).exists():
        print(f"Before log not found: {before_file}")
        sys.exit(1)
    if not Path(after_file).exists():
        print(f"After log not found: {after_file}")
        sys.exit(1)

    before = parse_log(before_file)
    after = parse_log(after_file)

    summary_rows = build_summary(before, after)
    lb_rows = build_lb_rows(lb_data)
    batch_rows = build_batch_rows(before, after)

    before_cron = dict(before)
    after_cron = dict(after)
    before_cron["batch_detail_rows"] = before.get("cron_detail_rows", [])
    before_cron["batch_names"] = []
    after_cron["batch_detail_rows"] = after.get("cron_detail_rows", [])
    after_cron["batch_names"] = []

    cron_rows_raw = build_batch_rows(before_cron, after_cron)

    cron_rows = [
        ("Cron Process Detail", path, bname, aname, "-")
        for (_label, path, bname, aname, _status) in cron_rows_raw
    ]
    # ---- CRON ROWS END ----

    app_rows = build_app_rows(before, after)
    app_status_rows = build_app_status_rows(before, after)

    html_file = write_html(summary_rows, cron_rows, batch_rows, app_rows, app_status_rows, lb_rows, output_html, before_file, after_file, before, after)

    print("Comparison completed successfully!")
    print(f"HTML report: {html_file}")

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 validation_report_runner.py <before.log> <after.log> <output_report.html>")
        sys.exit(1)

    before_file = sys.argv[1]
    after_file = sys.argv[2]
    output_html = sys.argv[3]
    
    lb_data = None
    if not sys.stdin.isatty():
        try:
            lb_data = json.loads(sys.stdin.read())
        except Exception:
            lb_data = None

    run_report(before_file, after_file, output_html, lb_data)

if __name__ == "__main__":
    main()