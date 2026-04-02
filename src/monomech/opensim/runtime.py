"""OpenSim runtime helpers."""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from ..exceptions import OpenSimError
from ..utils.optional import import_optional


def import_opensim():
    return import_optional("opensim", extra_name="OpenSim")


def run_opensim_tool(setup_xml_path: str | Path, tool_name: str, use_subprocess: bool = True) -> dict:
    setup_xml_path = Path(setup_xml_path)
    if use_subprocess:
        cmd_path = shutil.which("opensim-cmd")
        if cmd_path:
            cmd = [cmd_path, "-o", "info", "run-tool", str(setup_xml_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "method": "opensim-cmd",
                "ok": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": cmd,
            }
        script = textwrap.dedent(
            """
            import sys
            import opensim as osim
            from pathlib import Path

            setup_xml = Path(sys.argv[1])
            tool_name = sys.argv[2]
            if tool_name == 'InverseKinematicsTool':
                tool = osim.InverseKinematicsTool(str(setup_xml))
            elif tool_name == 'InverseDynamicsTool':
                tool = osim.InverseDynamicsTool(str(setup_xml))
            elif tool_name == 'ScaleTool':
                tool = osim.ScaleTool(str(setup_xml))
            else:
                raise ValueError(tool_name)
            ok = bool(tool.run())
            print(f"{tool_name}.run() -> {ok}")
            raise SystemExit(0 if ok else 2)
            """
        )
        cmd = [sys.executable, "-c", script, str(setup_xml_path), tool_name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return {
            "method": "python-subprocess",
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": cmd,
        }

    osim = import_opensim()
    if tool_name == "InverseKinematicsTool":
        tool = osim.InverseKinematicsTool(str(setup_xml_path))
    elif tool_name == "InverseDynamicsTool":
        tool = osim.InverseDynamicsTool(str(setup_xml_path))
    elif tool_name == "ScaleTool":
        tool = osim.ScaleTool(str(setup_xml_path))
    else:
        raise OpenSimError(f"Unsupported tool: {tool_name}")
    ok = bool(tool.run())
    return {"method": "python-api", "ok": ok, "returncode": 0 if ok else 2, "stdout": f"{tool_name}.run() -> {ok}", "stderr": ""}
