#!/usr/bin/env python3
"""生成 Conan Linux 依赖快照, 或为 bot2_calib 恢复离线依赖."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
PROFILES = ("aarch22", "aarch24")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(path):
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def conan_bin():
    executable = shutil.which("conan")
    if executable is None and Path("/opt/conan-venv/bin/conan").is_file():
        executable = "/opt/conan-venv/bin/conan"
    if executable is None:
        raise RuntimeError("未找到 Conan. 请先安装 conan==2.30.0.")
    version = subprocess.check_output([executable, "--version"], text=True).strip()
    if version != "Conan version 2.30.0":
        raise RuntimeError(f"需要 Conan 2.30.0, 实际为: {version}")
    return executable


def run(executable, *args, env=None):
    print("执行: conan " + " ".join(map(str, args)), flush=True)
    subprocess.run([executable, *map(str, args)], env=env, check=True)


def graph_args(profile, source):
    return ["graph", "info", source, f"--profile:host={profile}",
            f"--profile:build={profile}", "--build=never",
            f"--lockfile={ROOT / 'locks' / (profile + '.lock')}", "--format=json"]


def active_binaries(path):
    graph = read_json(path)["graph"]
    if graph.get("error"):
        raise RuntimeError(f"依赖图错误: {graph['error']}")
    active = {}
    for node in graph["nodes"].values():
        if node.get("binary") in (None, "Skip"):
            continue
        key = (node["ref"], node["package_id"], node["prev"])
        active[key] = node["binary"]
    return active


def expected_binaries(package_list):
    result = set()
    for recipes in package_list.values():
        for ref, item in recipes.items():
            for rrev, recipe in item["revisions"].items():
                for package_id, package in recipe.get("packages", {}).items():
                    for prev in package["revisions"]:
                        result.add((f"{ref}#{rrev}", package_id, prev))
    return result


def check_snapshot():
    snapshot = read_json(ROOT / "snapshot.json")
    for relative, expected in snapshot["files_sha256_lf"].items():
        if text_sha256(ROOT / relative) != expected:
            raise RuntimeError(f"快照文件校验失败: {relative}")
    return snapshot


def export_bundle(args):
    if sys.platform != "linux":
        raise RuntimeError("归档必须在 Linux 生成, 以保留文件权限和符号链接.")
    executable = conan_bin()
    snapshot = check_snapshot()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    profile = args.profile
    pins = ROOT / "packages" / f"{profile}.json"
    expected = expected_binaries(read_json(pins))
    archive = output / f"bot2-calib-{profile}-conan.tgz"
    source = ROOT / "consumer/app/bot2_calib"
    run(executable, "config", "install", ROOT / "config")
    # 先解析锁定的完整图, 取得所有配方, 包括被 Conan 跳过二进制的传递依赖.
    run(executable, *graph_args(profile, source), f"--out-file={output / 'online-graph.json'}")
    for remote in ("tea-gitea", "conancenter"):
        run(executable, "download", f"--list={ROOT / 'packages' / (profile + '-' + remote + '.json')}",
            f"--remote={remote}")
    run(executable, "cache", "check-integrity", f"--list={pins}")
    run(executable, "cache", "save", f"--list={pins}", "--no-source", f"--file={archive}")

    # 通过官方 cache restore 验证, 不直接修改或拼装 Conan 缓存.
    with tempfile.TemporaryDirectory(prefix="conan-verify-") as clean_cache:
        env = dict(os.environ, CONAN_HOME=clean_cache)
        run(executable, "config", "install", ROOT / "config", env=env)
        run(executable, "cache", "restore", archive, env=env)
        run(executable, "cache", "check-integrity", f"--list={pins}", env=env)
        graph = output / "offline-graph.json"
        run(executable, *graph_args(profile, source), "--no-remote",
            f"--out-file={graph}", env=env)
        restored = active_binaries(graph)
        if set(restored) != expected or set(restored.values()) != {"Cache"}:
            raise RuntimeError("干净缓存离线验证失败: 存在缺包或二进制版本不一致.")

    manifest = {
        "schema_version": 1,
        "profile": profile,
        "conan_version": "2.30.0",
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha256(archive),
        "package_list_sha256": sha256(pins),
        "snapshot_sha256": sha256(ROOT / "snapshot.json"),
        "source_files_sha256_lf": snapshot["source_files_sha256_lf"],
        "recipe_count": len(read_json(pins)["Local Cache"]),
        "binary_count": len(expected),
        "validation": {
            "cache_integrity": "passed",
            "clean_cache_restore": "passed",
            "offline_graph_all_expected_binaries": "passed",
            "target_compilation": "not_run",
            "hardware": "not_run",
        },
    }
    write_json(output / f"{profile}.manifest.json", manifest)
    (output / f"{profile}.sha256").write_text(
        f"{manifest['archive_sha256']}  {archive.name}\n", encoding="utf-8")
    print(f"完成: {len(expected)} 个二进制包, {archive.stat().st_size} 字节.", flush=True)


def native_profile():
    if sys.platform != "linux" or platform.machine() not in ("aarch64", "arm64"):
        raise RuntimeError("安装目标必须是 Ubuntu aarch64/arm64 机器人.")
    values = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip('"')
    if values.get("ID") != "ubuntu" or values.get("VERSION_ID") not in ("22.04", "24.04"):
        raise RuntimeError("仅支持 Ubuntu 22.04 或 24.04.")
    return "aarch" + values["VERSION_ID"][:2]


def install_bundle(args):
    profile = native_profile()
    if args.profile and args.profile != profile:
        raise RuntimeError(f"所选平台与当前机器人不符, 当前平台为: {profile}")
    executable = conan_bin()
    snapshot = check_snapshot()
    source = args.source.resolve()
    for relative, expected in snapshot["source_files_sha256_lf"].items():
        if text_sha256(source / relative) != expected:
            raise RuntimeError(f"项目依赖声明与快照不符: {relative}. 需要重新生成依赖包.")
    manifest = read_json(args.assets / f"{profile}.manifest.json")
    archive = args.assets / f"bot2-calib-{profile}-conan.tgz"
    if (manifest.get("profile") != profile or manifest.get("conan_version") != "2.30.0"
            or manifest.get("snapshot_sha256") != sha256(ROOT / "snapshot.json")
            or manifest.get("package_list_sha256") != sha256(ROOT / "packages" / f"{profile}.json")
            or manifest.get("archive") != archive.name
            or manifest.get("archive_sha256") != sha256(archive)):
        raise RuntimeError("归档或来源校验失败, 尚未导入 Conan 缓存.")
    deployer = source / "share/conan/runtime_libs.py"
    if not deployer.is_file():
        raise RuntimeError(f"缺少项目运行库部署脚本: {deployer}")
    run(executable, "config", "install", ROOT / "config")
    run(executable, "cache", "restore", archive)
    pins = ROOT / "packages" / f"{profile}.json"
    run(executable, "cache", "check-integrity", f"--list={pins}")
    # 只从恢复的缓存安装. 系统开发包须提前安装, 不自动运行联网 APT.
    run(executable, "install", source / "app/bot2_calib", f"--output-folder={source}",
        f"--profile:host={profile}", f"--profile:build={profile}",
        f"--lockfile={ROOT / 'locks' / (profile + '.lock')}",
        "--no-remote", "--build=never", "-c", "tools.cmake.cmaketoolchain:user_presets=",
        "-c:a", "tools.system.package_manager:mode=check",
        f"--deployer={deployer}", f"--deployer-folder={source / 'bin/bot2_calib/lib'}")
    presets = source / "CMakeUserPresets.json"
    temporary = source / "CMakeUserPresets.json.tmp"
    write_json(temporary, {"version": 4, "vendor": {"conan": {}},
                           "include": [".cache/conan/CMakePresets.json"]})
    os.replace(temporary, presets)
    print("离线依赖已部署. 下一步执行 build_app.py, 首次配置不要加 --skip-configure.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="在 Linux 生成及验证双平台之一的依赖归档")
    export.add_argument("--profile", choices=PROFILES, required=True)
    export.add_argument("--output", type=Path, required=True)
    install = commands.add_parser("install", help="在机器人恢复归档并离线生成项目依赖")
    install.add_argument("--profile", choices=PROFILES)
    install.add_argument("--source", type=Path, required=True)
    install.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        export_bundle(args)
    else:
        install_bundle(args)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"错误: {error}", file=sys.stderr)
        sys.exit(1)
