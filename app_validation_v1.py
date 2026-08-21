#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple Server Availability / Validation Check
"""

import os
import re
import pwd
import shlex
import socket
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# ------------------------------------
# helpers
# ------------------------------------
def cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None

def run_cmd(cmd, timeout=10) -> str:
    """Return stdout (stripped). Empty string on failure."""
    try:
        p = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout
        )
        return (p.stdout or "").strip()
    except Exception:
        return ""

def print_section(title: str):
    print("")
    print("=" * 78)
    print(title)
    print("=" * 78)

def print_kv(key: str, val: str):
    print(f"{key} | {val}")

def tcp_reachable(host: str, port: int, timeout: int = 3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def http_code(url: str, insecure: bool = False) -> str:
    """
    Return HTTP status code using curl.
    """
    if not cmd_exists("curl"):
        return ""

    cmd = ["curl", "--max-time", "5", "-s", "-o", "/dev/null", "-w", "%{http_code}"]
    if insecure:
        cmd.append("-k")
    cmd.append(url)

    out = run_cmd(cmd, timeout=8)
    return out.strip() if out else ""

def get_host_ip() -> str:
    out = run_cmd(["hostname", "-I"], timeout=5) if cmd_exists("hostname") else ""
    if out:
        parts = [p for p in out.split() if p and not p.startswith("127.")]
        if parts:
            return parts[0]
    return "Not Found"

def timezone_info() -> str:
    out = run_cmd(["date", "+%Z"], timeout=4) if cmd_exists("date") else ""
    return out if out else "Not Found"

def human_size(num_bytes):
    units = ["B", "K", "M", "G", "T", "P"]
    n = float(num_bytes)

    for u in units:
        if n < 1024:
            if u == "B":
                return f"{int(n)}{u}"
            return f"{round(n, 1)}{u}"
        n = n / 1024
    return "0B"

def parse_mounts():
    mounts = []
    try:
        for ln in Path("/proc/mounts").read_text(errors="ignore").splitlines():
            parts = ln.split()
            if len(parts) >= 3:
                mounts.append((parts[0], parts[1], parts[2]))
    except Exception:
        pass
    return mounts

def df_for_data_mounts():
    print("Filesystem | Size | Used | Avail | Use% | Mounted on")
    mounts = parse_mounts()
    data_mounts = []

    for dev, mnt, fstype in mounts:
        if mnt.startswith("/data"):
            data_mounts.append((dev, mnt, fstype))

    seen = set()
    for dev, mnt, _fstype in data_mounts:
        if mnt in seen:
            continue
        seen.add(mnt)
        try:
            du = shutil.disk_usage(mnt)
            size = human_size(du.total)
            used = human_size(du.used)
            avail = human_size(du.free)
            usep = int((du.used / du.total) * 100) if du.total else 0
            print(f"{dev} | {size} | {used} | {avail} | {usep}% | {mnt}")
        except Exception:
            print(f"{dev} | NA | NA | NA | 0% | {mnt}")

def list_root_symlinks():
    all_rows = []
    valid_rows = []
    invalid_rows = []

    try:
        for e in os.scandir("/"):
            if e.is_symlink():
                link_path = "/" + e.name
                resolved = str(Path(link_path).resolve(strict=False))
                row = f"{link_path} | {resolved}"

                all_rows.append(row)

                if Path(link_path).exists():
                    valid_rows.append(row)
                else:
                    invalid_rows.append(row)
    except Exception:
        pass

    return sorted(all_rows), sorted(valid_rows), sorted(invalid_rows)

def iter_procs():
    """Yield (pid, user, cmdline)"""
    proc = Path("/proc")
    try:
        proc_entries = list(proc.iterdir())
    except Exception:
        return

    for p in proc_entries:
        if not p.name.isdigit():
            continue

        pid = p.name
        try:
            cmdline = (p / "cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="ignore").strip()
            if not cmdline:
                continue

            status = (p / "status").read_text(errors="ignore")
            m = re.search(r"^Uid:\s+(\d+)", status, re.MULTILINE)
            uid = int(m.group(1)) if m else -1

            try:
                user = pwd.getpwuid(uid).pw_name if uid >= 0 else "Unknown"
            except Exception:
                user = "Unknown"

            yield pid, user, cmdline
        except Exception:
            continue

def get_ppid(pid: str) -> str:
    """Read parent PID from /proc/<pid>/stat"""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(errors="ignore")
        # cmd name is in parentheses and can contain spaces/parens,
        # so split from the last ')' 
        after = stat.rsplit(")", 1)[-1].split()
        # after[0] = state, after[1] = ppid
        return after[1].strip()
    except Exception:
        return ""

def get_proc_name(pid: str) -> str:
    """Read process name (comm) from /proc/<pid>/comm"""
    try:
        return Path(f"/proc/{pid}/comm").read_text(errors="ignore").strip()
    except Exception:
        return ""

def is_cron_triggered(pid: str, max_depth: int = 50) -> bool:
    """
    Walk up the parent chain from pid to PID 1.
    Return True if any ancestor process is crond/cron.
    """
    current = str(pid)
    depth = 0

    while current and current != "1" and depth < max_depth:
        pname = get_proc_name(current)

        if pname in ("crond", "cron"):
            return True

        parent = get_ppid(current)
        if not parent or parent == current:
            break

        current = parent
        depth += 1

    return False



def systemctl_active(unit: str) -> bool:
    if not cmd_exists("systemctl"):
        return False
    try:
        p = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=6
        )
        return p.returncode == 0
    except Exception:
        return False

def any_systemctl_active(units) -> bool:
    for unit in units:
        if systemctl_active(unit):
            return True
    return False

def rpm_has(pkg: str) -> bool:
    if not cmd_exists("rpm"):
        return False
    try:
        p = subprocess.run(
            ["rpm", "-q", pkg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8
        )
        return p.returncode == 0
    except Exception:
        return False

def dpkg_version(pkg: str) -> str:
    if not cmd_exists("dpkg"):
        return ""
    out = run_cmd(["dpkg", "-s", pkg], timeout=8)
    m = re.search(r"^Version:\s*(.+)$", out, re.MULTILINE)
    return m.group(1).strip() if m else ""

# ------------------------------------
# JBoss / WildFly helpers
# ------------------------------------
def strip_quotes_commas(value: str) -> str:
    return value.strip('"\',')

def split_cmdline_safe(cmdline: str):
    try:
        return shlex.split(cmdline)
    except Exception:
        return cmdline.split()

def jboss_base_dir(cmdline: str) -> str:
    """
    Extract JBoss standalone base dir.
    """
    m = re.search(r"-Djboss\.server\.base\.dir=([^\s]+)", cmdline)
    if m:
        return strip_quotes_commas(m.group(1))

    for tok in cmdline.split():
        if "/standalone" in tok:
            tok2 = strip_quotes_commas(tok)
            if "=" in tok2:
                tok2 = tok2.split("=", 1)[1]
            i = tok2.find("/standalone")
            if i != -1:
                cand = tok2[: i + len("/standalone")]
                if os.path.isdir(cand):
                    return cand

    return "NotFound"

def jboss_app_name(base_dir: str) -> str:
    p = Path(base_dir)
    if p.name == "standalone":
        return p.parent.name or "NotFound"
    return "NotFound"

def jboss_version_name(base_dir: str) -> str:
    p = Path(base_dir)
    try:
        return p.parents[2].name or "NotFound"
    except Exception:
        return "NotFound"

def _resolve_port_value(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("${") and ":" in raw:
        try:
            after = raw.split(":", 1)[1]
            after = after.split("}", 1)[0]
            return after.strip()
        except Exception:
            return raw
    return raw

def parse_jboss_ports(xml_path: str):
    """
    Return (http_port, https_port)
    Reads standalone.xml
    """
    try:
        txt = Path(xml_path).read_text(errors="ignore")
    except Exception:
        return "", ""

    def find_socket_binding(name: str) -> str:
        patterns = [
            rf'<socket-binding\b[^>]*\bname="{re.escape(name)}"[^>]*\bport="([^"]+)"',
            rf'<socket-binding\b[^>]*\bport="([^"]+)"[^>]*\bname="{re.escape(name)}"',
        ]
        for pat in patterns:
            m = re.search(pat, txt)
            if m:
                return _resolve_port_value(m.group(1))
        return ""

    http_port = find_socket_binding("http")
    https_port = find_socket_binding("https")
    return http_port, https_port

def get_jboss_config_xml_path(cmdline: str, base_dir: str) -> str:
    """
    Return actual JBoss config XML path being used by the process.
    """
    config_name = "standalone.xml"

    m = re.search(r'(?:^|\s)-c\s+([^\s]+)', cmdline)
    if m:
        config_name = strip_quotes_commas(m.group(1))

    return str(Path(base_dir) / "configuration" / config_name)

def parse_jboss_port_offset(xml_path: str) -> str:
    """
    Return socket-binding-group port-offset from actual config xml
    """
    try:
        txt = Path(xml_path).read_text(errors="ignore")
    except Exception:
        return ""

    m = re.search(r'<socket-binding-group\b[^>]*\bport-offset="([^"]+)"', txt)
    if not m:
        return ""

    return _resolve_port_value(m.group(1))

def get_cmdline_prop(cmdline: str, prop: str) -> str:
    m = re.search(rf"-D{re.escape(prop)}=([^\s]+)", cmdline)
    if not m:
        return ""
    return strip_quotes_commas(m.group(1))

def resolve_effective_jboss_ports(cmdline: str, xml_http: str, xml_https: str, xml_offset: str = ""):
    """
    Resolve actual app ports using active XML + cmdline overrides/offset.
    """
    http_port = (xml_http or "").strip()
    https_port = (xml_https or "").strip()

    http_override = get_cmdline_prop(cmdline, "jboss.http.port")
    https_override = get_cmdline_prop(cmdline, "jboss.https.port")
    cmd_offset = get_cmdline_prop(cmdline, "jboss.socket.binding.port-offset")

    if http_override.isdigit():
        http_port = http_override
    if https_override.isdigit():
        https_port = https_override

    port_offset = cmd_offset if cmd_offset.isdigit() else (xml_offset if str(xml_offset).isdigit() else "")

    if port_offset.isdigit():
        off = int(port_offset)

        if http_port.isdigit() and not http_override.isdigit():
            http_port = str(int(http_port) + off)

        if https_port.isdigit() and not https_override.isdigit():
            https_port = str(int(https_port) + off)

    return http_port, https_port

def pid_listens_on_port(pid: str, port: str) -> bool:
    if not port or not port.isdigit():
        return False
    if not cmd_exists("ss"):
        return False

    out = run_cmd(["ss", "-lntp"], timeout=10)
    if not out:
        return False

    pid_pat = f"pid={pid},"
    port_pat = f":{port}"

    for line in out.splitlines():
        if pid_pat in line and port_pat in line:
            return True
    return False

# ------------------------------------
# Batch / daemon helpers
# ------------------------------------
def read_proc_pwd(pid: str) -> str:
    try:
        env_raw = Path(f"/proc/{pid}/environ").read_bytes().decode(errors="ignore")
        for item in env_raw.split("\x00"):
            if item.startswith("PWD="):
                return item.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""

def read_proc_cwd(pid: str) -> str:
    try:
        return os.readlink(f"/proc/{pid}/cwd").strip()
    except Exception:
        return ""

def java_proc_display_name(cmdline: str) -> str:
    parts = cmdline.split("/")

    for i, part in enumerate(parts):
        if part.strip() == "bin" and i + 1 < len(parts):
            next_part = parts[i + 1].strip()
            name = next_part.split()[0].strip()
            return name if name else "Unknown"

    return "Unknown"

def jboss_java_display_name(cmdline: str) -> str:
    """
    Preserve old JBoss Java-Name behaviour.
    Example:
      allendemo_jb720
      domsora261_jb80
    """
    parts = cmdline.split("/")

    for i, part in enumerate(parts):
        if part.strip() == "bin" and i + 1 < len(parts):
            next_part = parts[i + 1].strip()
            name = next_part.split()[0].strip()
            return name if name else "Unknown"

    return "Unknown"

def java_proc_path(pid: str, cmdline: str, java_name: str) -> str:
    """
    Return daemon-related path.
    """
    if not java_name or java_name == "Unknown":
        java_name = ""

    tokens = [strip_quotes_commas(t) for t in split_cmdline_safe(cmdline)]

    # 1) direct full launcher path from cmdline
    if java_name:
        for tok in tokens:
            tok2 = strip_quotes_commas(tok)
            if "/" not in tok2:
                continue

            base = Path(tok2).name
            low = tok2.lower()

            if base == java_name and not low.endswith("/java") and "amazon-corretto" not in low:
                return tok2

    def best_from_dir(dir_path: str) -> str:
        if not dir_path:
            return ""

        dir_path = dir_path.strip()
        if not dir_path:
            return ""
        
        if len(dir_path)>4096:
            return ""

        if java_name:
            cand1 = Path(dir_path) / java_name
            if cand1.exists():
                return str(cand1)

            cand2 = Path(dir_path) / "bin" / java_name
            if cand2.exists():
                return str(cand2)

        return dir_path

    # 2) PWD from environment
    pwd_path = read_proc_pwd(pid)
    best = best_from_dir(pwd_path)
    if best:
        return best

    # 3) process cwd
    cwd_path = read_proc_cwd(pid)
    best = best_from_dir(cwd_path)
    if best:
        return best

    # 4) derive common/lib -> common/bin/<daemon> only if actual file exists
    if java_name:
        for tok in tokens:
            tok2 = strip_quotes_commas(tok)
            if "/common/lib" in tok2:
                if len(tok2) > 4096:
                    continue
                m = re.search(r'(/[^\s"\']+/common)/lib\b', tok2)
                if m:
                    common_base = m.group(1)
                    cand = Path(common_base) / "bin" / java_name
                    if cand.exists():
                        return str(cand)

    # 5) generic -jar fallback
    for i, tok in enumerate(tokens[:-1]):
        if tok == "-jar":
            jar_path = strip_quotes_commas(tokens[i + 1])
            if "/" in jar_path:
                return jar_path

    return "Unknown"

def collect_real_jboss_apps(probe_host: str):
    """
    Return only real JBoss/WildFly apps.
    Skip random java listeners / unknown ports.
    """
    rows = []
    seen = set()

    for pid, user, cmdline in iter_procs():
        lower = cmdline.lower()

        if "java" not in lower:
            continue
        if "standalone" not in lower:
            continue

        base_dir = jboss_base_dir(cmdline)
        if base_dir == "NotFound":
            continue

        app_name = jboss_app_name(base_dir)
        if app_name in {"", "NotFound"}:
            continue

        xml = get_jboss_config_xml_path(cmdline, base_dir)
        if not Path(xml).is_file():
            continue

        xml_http_port, xml_https_port = parse_jboss_ports(xml)
        if not xml_http_port and not xml_https_port:
            continue

        xml_offset = parse_jboss_port_offset(xml)
        http_port, https_port = resolve_effective_jboss_ports(cmdline, xml_http_port, xml_https_port, xml_offset)
        display_port = ""
        status = "Down"
        code = "000"
        ssl_text = "Disabled"

        if http_port and pid_listens_on_port(str(pid), http_port):
            display_port = http_port
            ssl_text = "Disabled"
            code = http_code(f"http://{probe_host}:{display_port}") or "000"
            status = "UP" if code == "200" else "Down"

        elif https_port and pid_listens_on_port(str(pid), https_port):
            display_port = https_port
            ssl_text = "Enabled"
            code = http_code(f"https://{probe_host}:{display_port}", insecure=True) or "000"
            status = "UP" if code == "200" else "Down"

        else:
            if http_port:
                display_port = http_port
                ssl_text = "Disabled"
                code = http_code(f"http://{probe_host}:{display_port}") or "000"
                status = "UP" if code == "200" else "Down"
            elif https_port:
                display_port = https_port
                ssl_text = "Enabled"
                code = http_code(f"https://{probe_host}:{display_port}", insecure=True) or "000"
                status = "UP" if code == "200" else "Down"

        if not display_port:
            continue

        key = (app_name, display_port, base_dir)
        if key in seen:
            continue
        seen.add(key)

        jboss_version = jboss_version_name(base_dir)
        java_name = jboss_java_display_name(cmdline)

        rows.append({
            "PID": pid,
            "User": user,
            "AppName": app_name,
            "JbossVersion": jboss_version,
            "Java-Name": java_name,
            "Port": display_port,
            "URL": f"{probe_host}:{display_port}",
            "Status": status,
            "Code": code,
            "SSL-Status": ssl_text,
            "App-Path": base_dir,
        })

    rows.sort(key=lambda r: (r["AppName"], int(r["Port"]) if str(r["Port"]).isdigit() else r["Port"]))
    return rows

def is_excluded_batch_java(cmdline: str) -> bool:
    low = cmdline.lower()

    if "standalone" in low:
        return True
    if "i-net" in low:
        return True
    if "health" in low:
        return True
    if "/ant/" in low:
        return True

    return False

# ------------------------------------
# Main
# ------------------------------------
def main():
    print_section(f"Server Availability Check Started | {datetime.now()}")
    host_ip = get_host_ip()
    probe_host = host_ip if host_ip != "Not Found" else "127.0.0.1"

    # SYSTEM
    print_section("SYSTEM INFORMATION")
    print_kv("Server IP", host_ip)
    print_kv("Hostname", socket.gethostname() or "Not Found")

    try:
        cur_user = pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        cur_user = "Not Found"

    print_kv("Current User", cur_user)
    print_kv("Working Directory", os.getcwd())
    print_kv("Time Zone", timezone_info())

    # STORAGE /data
    print_section("STORAGE CHECK | /data mounts")
    df_for_data_mounts()

    # SYMLINKS
    print_section("SYMLINK CHECK | root (/)")
    all_links, valid_links, invalid_links = list_root_symlinks()
    print_kv("Symlinks Total", str(len(all_links)))
    print_kv("Symlinks Valid", str(len(valid_links)))
    print_kv("Symlinks Invalid", str(len(invalid_links)))

    if all_links:
        print("Symlink | ResolvedTarget")
        for ln in all_links:
            print(ln)

    # NFS
    print_section("NFS CHECK")
    nfs_pkg = (
        rpm_has("nfs-utils") or
        bool(dpkg_version("nfs-kernel-server")) or
        bool(dpkg_version("nfs-common"))
    )
    print_kv("NFS Package Installed", "Yes" if nfs_pkg else "No")
    print_kv("nfs-server.service Active", "Yes" if systemctl_active("nfs-server.service") else "No")
    print_kv("nfs-client.target Active", "Yes" if systemctl_active("nfs-client.target") else "No")

    if Path("/etc/exports").is_file():
        print_kv("/etc/exports Present", "Yes")
        try:
            exports_txt = Path("/etc/exports").read_text(errors="ignore").strip()
            if exports_txt:
                print("EXPORTS_LINE | " + exports_txt.replace("\n", " | "))
            else:
                print("EXPORTS_LINE | (empty)")
        except Exception:
            print("EXPORTS_LINE | Not Found")
    else:
        print_kv("/etc/exports Present", "No")

    mounts = parse_mounts()
    nfs_mounts = [(d, m, t) for (d, m, t) in mounts if t.startswith("nfs")]
    if nfs_mounts:
        print("NFS_MOUNT | Device | MountPoint | FSType")
        for d, m, t in nfs_mounts:
            print(f"NFS_MOUNT | {d} | {m} | {t}")
    else:
        print_kv("NFS Mounted Shares", "None")

    # CUPS
    print_section("CUPS CHECK")
    cups_installed = (
        Path("/etc/cups").exists() or
        Path("/usr/sbin/cupsd").exists() or
        cmd_exists("cupsd")
    )
    cups_running = any_systemctl_active(["cups", "cups.service"]) or tcp_reachable("127.0.0.1", 631, 2)

    print_kv("CUPS Installed", "Yes" if cups_installed else "No")
    print_kv("CUPS Running", "Yes" if cups_running else "No")

    ver = ""

    if rpm_has("cups"):
        ver = run_cmd(["rpm", "-q", "cups"], timeout=6)
    elif cmd_exists("cups-config"):
        ver = run_cmd(["cups-config", "--version"], timeout=6)
    else:
        ver = dpkg_version("cups")

    print_kv("CUPS Version", ver if ver else "Not Found")

    shown_host = host_ip if host_ip != "Not Found" else "127.0.0.1"

    if tcp_reachable(probe_host, 631, 3):
        c3 = http_code(f"http://{probe_host}:631") or "Not Found"
        print_kv(f"CUPS IP URL (http://{shown_host}:631)", c3)

        cups_server_code = http_code(f"http://{probe_host}:631/") or "Not Found"
        print_kv("Cups server Http Status", cups_server_code)

        cups_printers_code = http_code(f"http://{probe_host}:631/printers") or "Not Found"
        print_kv("Cups printers Http Status", cups_printers_code)
    else:
        print_kv("CUPS IP Port 631 Reachable", "No")
        print_kv("Cups server Http Status", "Not Found")
        print_kv("Cups printers Http Status", "Not Found")

    if cmd_exists("lpstat"):
       out = run_cmd(["bash", "-c", "lpstat -v 2>/dev/null | wc -l"], timeout=8)
       count = out.strip()
       print_kv("Printers Configured", count if count else "0")
    else:
       print_kv("Printers Configured", "Not Found")

    # FTP
    print_section("FTP CHECK")
    ftp_service_units = ["vsftpd", "vsftpd.service", "proftpd", "proftpd.service"]
    ftp_installed = (
        Path("/usr/sbin/vsftpd").exists() or
        Path("/usr/sbin/proftpd").exists() or
        Path("/usr/sbin/in.ftpd").exists() or
        any_systemctl_active(ftp_service_units)
    )
    ftp_running = any_systemctl_active(ftp_service_units) or tcp_reachable("127.0.0.1", 21, 2)

    print_kv("FTP Installed", "Yes" if ftp_installed else "No")
    print_kv("FTP Running (Port 21 localhost)", "Yes" if ftp_running else "No")
    print_kv(
        f"FTP Port 21 Reachable on {host_ip}",
        "Yes" if (host_ip != "Not Found" and tcp_reachable(host_ip, 21, 3)) else "No"
    )

    ftp_hits = []
    pat = re.compile(r"\b(vsftpd|proftpd|pure-ftpd|in\.ftpd|ftpd)\b", re.IGNORECASE)
    for pid, user, cmdline in iter_procs():
        if pat.search(cmdline):
            proc_name = cmdline.split()[0] if cmdline.split() else cmdline
            ftp_hits.append((pid, user, proc_name))

    if ftp_hits:
        print("FTP_PROCESS | PID | User | Proc")
        for pid, user, proc in ftp_hits:
            print(f"FTP_PROCESS | {pid} | {user} | {proc}")
    else:
        print_kv("FTP Processes", "None")

    # JAVA
    print_section("JAVA CHECK")

    # Java processes check
    out = run_cmd([
    "bash",
    "-c",
    """
    ps -eo pid,tgid,ppid,cmd | grep java | grep -v grep | awk '$1==$2 {print $1}' |
    while read pid; do
      current=$pid
      is_cron=0
      while [ -n "$current" ] && [ "$current" != "1" ]; do
        pname=$(ps -o comm= -p "$current" 2>/dev/null)
        if [ "$pname" = "crond" ] || [ "$pname" = "cron" ]; then
          is_cron=1
          break
        fi
        current=$(ps -o ppid= -p "$current" 2>/dev/null | tr -d ' ')
      done
      [ "$is_cron" -eq 0 ] && echo "$pid"
    done | wc -l
    """
    ], timeout=15)

    count = out.strip()
    
    total_java = 0
    all_java_procs = []

    for pid, user, cmdline in iter_procs():
        if "java" in cmdline.lower():
            total_java += 1
            all_java_procs.append((pid, user, cmdline))

    app_rows = collect_real_jboss_apps(probe_host)
    app_pid_set = {str(r["PID"]) for r in app_rows}

    batch_detail_rows = []
    cron_detail_rows = []

    for pid, user, cmdline in all_java_procs:
        if str(pid) in app_pid_set:
            continue

        if is_excluded_batch_java(cmdline):
            continue

        pname = java_proc_display_name(cmdline)
        ppath = java_proc_path(str(pid), cmdline, pname)


        if is_cron_triggered(pid):
            cron_detail_rows.append({         
                "Java-Name": pname,
                "Java-Path": ppath,
            })
            continue

        batch_detail_rows.append({
            "Java-Name": pname,
            "Java-Path": ppath,
        })

    # unique keep order
    seen_batch = set()
    unique_batch_rows = []
    batch_names = []

    for r in batch_detail_rows:
        key = (r["Java-Name"], r["Java-Path"])
        if key in seen_batch:
            continue
        seen_batch.add(key)
        unique_batch_rows.append(r)
        batch_names.append(r["Java-Name"])

    batch_detail_rows = unique_batch_rows
    batch_daemon_java = len(batch_detail_rows)

    seen_cron = set()
    unique_cron_rows = []
    cron_names = []

    for r in cron_detail_rows:
        key = (r["Java-Name"], r["Java-Path"])
        if key in seen_cron:
            continue
        seen_cron.add(key)
        unique_cron_rows.append(r)
        cron_names.append(r["Java-Name"])

    cron_detail_rows = unique_cron_rows
    cron_java_count = len(cron_detail_rows)

    print_kv("Total Java Processes", count if count else "0")
    print_kv("Batch/Daemon Java Processes", str(batch_daemon_java))
    print_kv(
        "Non-Standalone Java Processes",
        ", ".join(batch_names) if batch_names else "Not Found"
    )

    # NEW SECTION: BATCH/DAEMON PATH DETAILS
    print_section("BATCH/DAEMON JAVA DETAILS")
    print_kv("Batch/Daemon Java Processes", str(batch_daemon_java))

    if batch_detail_rows:
        print("Java-Name | Java-Path")
        for r in batch_detail_rows:
            print(f"{r['Java-Name']} | {r['Java-Path']}")
    else:
        print_kv("Batch/Daemon Java Details", "None")


    print_section("CRON TRIGGERED JAVA DETAILS")
    print_kv("Cron Triggered Java Processes", str(cron_java_count))

    if cron_detail_rows:
        print("Java-Name | Java-Path")
        for r in cron_detail_rows:
            print(f"{r['Java-Name']} | {r['Java-Path']}")
    else:
        print_kv("Cron Triggered Java Details", "None")

    # JBOSS / WILDFLY
    print_section("JBOSS/WILDFLY APPS (simple table)")
    print_kv("JBoss App Processes", str(len(app_rows)))

    if app_rows:
        print("PID | AppName | JbossVersion | Java-Name | Port | URL | Status | Code | SSL-Status | App-Path")
        shown_host = host_ip if host_ip != "Not Found" else "127.0.0.1"
        for r in app_rows:
            url = f"{shown_host}:{r['Port']}"
            print(
                f"{r['PID']} | {r['AppName']} | {r['JbossVersion']} | {r['Java-Name']} | "
                f"{r['Port']} | {url} | {r['Status']} | {r['Code']} | "
                f"{r['SSL-Status']} | {r['App-Path']}"
            )
    else:
        print_kv("JBoss Apps", "None")


    # Health Monitor Crontab Status
    print_section("HEALTH MONITOR CRONTAB STATUS")
    crontab_out = run_cmd(["crontab", "-l", "-u", "appadmin"], timeout=10)
    if crontab_out:
        found = False
        for line in crontab_out.splitlines():
            if "start_healthmonitor" in line:
                found = True
                if line.strip().startswith("#"):
                    print_kv("Health Monitor Crontab", "Disabled")
                else:
                    print_kv("Health Monitor Crontab", "Active")
                break
        if not found:
            print_kv("Health Monitor Crontab", "Not Found")  
    else:
        print_kv("Health Monitor Crontab", "Not Found") 

    print_section(f"Server Availability Check Completed | {datetime.now()}")


if __name__ == "__main__":
    main()