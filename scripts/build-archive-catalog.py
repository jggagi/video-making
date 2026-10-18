#!/usr/bin/env python3
"""Index retained films for GitHub Releases without moving or re-encoding them."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import quote

REPOSITORY = "jggagi/video-making"
HISTORICAL = (
    ("lanting", "兰亭集序", ["out", "out/museum", "out/extended", "out/time-bridge"], "."),
    ("madman", "狂人日记", ["out/madman"], "."),
    ("si-eternity", "一眼万年", ["si-eternity/out"], "si-eternity"),
    ("si-cage-7plus2", "7±2 的囚笼", ["si-cage-7plus2/out"], "si-cage-7plus2"),
    ("qstory-ep03", "余问 QStory EP.03：十万亿个分身", ["qstory-ep03/out"], "qstory-ep03"),
)
PREVIEW = re.compile(r"sample|preview|draft|opening-title|ending-title|样片|点睛片段", re.I)


def file_hash(path: Path) -> str:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for data in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(data)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError(f"File changed during hashing: {path}")
    return digest.hexdigest()


def probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    video = next(stream for stream in data["streams"] if stream.get("codec_type") == "video")
    return {
        "width": video["width"], "height": video["height"],
        "fps": video["avg_frame_rate"], "frames": video.get("nb_frames"),
        "video_duration_seconds": float(video["duration"]),
        "container_duration_seconds": float(data["format"]["duration"]),
    }


def discover(root: Path) -> list[dict]:
    works = []
    for work_id, title, directories, project in HISTORICAL:
        files = sorted({path for directory in directories for path in (root / directory).glob("*")
                        if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".webm", ".zip"}})
        if files:
            works.append({"id": work_id, "title": title, "files": files,
                          "release_tag": f"archive-{work_id}-v1", "historical": True,
                          "project_path": project, "delivery_directory": f"deliveries/legacy-{work_id}"})
    deliveries = root / "deliveries"
    if deliveries.exists():
        for directory in sorted(deliveries.iterdir()):
            manifest_path = directory / "delivery.json"
            if not directory.is_dir() or not manifest_path.is_file():
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("schema_version") != 1 or manifest.get("duration_seconds") != 120:
                raise ValueError(f"New delivery must use schema1/120 seconds: {manifest_path}")
            slug = manifest["slug"]
            if not re.fullmatch(r"[A-Za-z0-9\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff ._-]*", slug):
                raise ValueError(f"Use a stable work slug for archive tags: {slug}")
            files = sorted(path for path in directory.rglob("*") if path.is_file()
                           and path.suffix.lower() in {".mp4", ".mov", ".webm", ".zip"}
                           and not any(part.startswith("bundle") or part == "node_modules" for part in path.parts))
            if files:
                works.append({"id": slug, "title": manifest["title"], "files": files,
                              "release_tag": f"film-{slug}", "historical": False,
                              "project_path": (directory / "project").relative_to(root).as_posix(),
                              "delivery_directory": directory.relative_to(root).as_posix()})
    return works


def make_asset(root: Path, work: dict, path: Path) -> dict:
    if path.is_symlink():
        raise ValueError(f"Media symlinks must be resolved explicitly: {path}")
    relative = path.relative_to(root).as_posix()
    digest = file_hash(path)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", str(Path(relative).with_suffix("")).replace("/", "--")).strip(".-")
    prefix = re.sub(r"[^A-Za-z0-9._-]+", "-", work["id"]).strip(".-") or "film"
    name = prefix + "--" + stem + "--" + digest[:12] + path.suffix.lower()
    if len(name.encode("utf-8")) > 255:
        raise ValueError(f"Release asset name too long: {relative}")
    size = path.stat().st_size
    if not 0 < size < 2 * 1024**3:
        raise ValueError(f"Release asset must be nonempty and under2GiB: {relative}")
    kind = "project" if path.suffix.lower() == ".zip" else "video"
    measurements = {} if kind == "project" else probe(path)
    if kind == "project":
        platform = "工程"
    elif PREVIEW.search(path.name):
        platform = "预览"
    else:
        platform = "小红书" if measurements["height"] > measurements["width"] else "B站"
    if not work["historical"] and kind == "video" and path.parent.name in {"B站", "小红书"}:
        expected_size = (3840, 2160) if path.parent.name == "B站" else (1080, 1920)
        if (measurements["width"], measurements["height"]) != expected_size:
            raise ValueError(f"New platform output has wrong dimensions: {relative}")
        from fractions import Fraction
        fps = Fraction(measurements["fps"])
        if fps not in {24, 25, 30, 50, 60} or measurements["frames"] != str(120 * int(fps)):
            raise ValueError(f"New platform output must contain exactly120 seconds of frames: {relative}")
        if abs(measurements["video_duration_seconds"] - 120) > 1 / float(fps):
            raise ValueError(f"New platform output is not120 seconds: {relative}")
    return {"path": relative, "name": name, "bytes": size, "sha256": digest,
            "kind": kind, "platform": platform, "measurements": measurements,
            "download_url": f"https://github.com/{REPOSITORY}/releases/download/{quote(work['release_tag'], safe='')}/{quote(name, safe='')}"}


def table(assets: list[dict]) -> str:
    rows = ["| 文件 | 规格 | 大小 |", "| --- | --- | --- |"]
    for asset in assets:
        measured = asset["measurements"]
        spec = (f"{measured['width']}×{measured['height']}，{measured['video_duration_seconds']:.3f}秒"
                if measured else "可编辑工程 / 历史快照")
        rows.append(f"| [{Path(asset['path']).name}]({asset['download_url']}) | {spec} | {asset['bytes'] / 1024**2:.1f} MiB |")
    return "\n".join(rows) + "\n"


def write_work(root: Path, work: dict, assets: list[dict]) -> None:
    delivery = root / work["delivery_directory"]
    delivery.mkdir(parents=True, exist_ok=True)
    release = f"https://github.com/{REPOSITORY}/releases/tag/{quote(work['release_tag'], safe='')}"
    historical = ("这是历史归档，保留原时长、画幅与版本；不声称符合后续两分钟规格。\n"
                  if work["historical"] else "两版制作目标均为120秒，验收状态见本作品 review/。\n")
    text = f"# {work['title']}\n\n{historical}\n"
    text += f"[完整 Release 与全部下载]({release}) · [B站横屏](B站/README.md) · [小红书竖屏](小红书/README.md)\n\n"
    text += f"源码位置：`{work['project_path']}`。成片在 GitHub Releases；本机原始路径、SHA-256、实测规格见 [archive.json](archive.json)。\n\n"
    projects = [asset for asset in assets if asset["platform"] == "工程"]
    if projects:
        text += "## 工程归档\n\n" + table(projects) + "\n"
    previews = [asset for asset in assets if asset["platform"] == "预览"]
    if previews:
        text += "## 样片与历史草稿\n\n这些文件仅作制作过程记录，不能视为最终成片。\n\n" + table(previews)
    (delivery / "README.md").write_text(text, encoding="utf-8")
    for platform in ("B站", "小红书"):
        folder = delivery / platform
        folder.mkdir(exist_ok=True)
        selected = [asset for asset in assets if asset["platform"] == platform]
        text = f"# {work['title']} · {platform}\n\n"
        text += "按画幅分类归档，不表示已经发布到平台账号。\n\n"
        text += table(selected) if selected else "当前未发现此画幅的成片；未为归档补做或裁切视频。\n"
        (folder / "README.md").write_text(text, encoding="utf-8")
    record = {key: value for key, value in work.items() if key != "files"}
    record["assets"] = assets
    (delivery / "archive.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Copy only compact historical evidence/subtitles; never move the originals.
    if work["historical"]:
        for directory in sorted({path.parent for path in work["files"]}):
            for path in sorted(directory.glob("*")):
                if not path.is_file() or path.is_symlink():
                    continue
                suffix = path.suffix.lower()
                if suffix in {".srt", ".vtt"}:
                    platform = "小红书" if re.search(r"xhs|portrait", path.name, re.I) else "B站"
                    name = path.relative_to(root).as_posix().replace("/", "--")
                    target = delivery / platform / name
                elif suffix in {".json", ".txt"} and path.stat().st_size < 512 * 1024:
                    folder = delivery / "review"
                    folder.mkdir(exist_ok=True)
                    target = folder / path.relative_to(root).as_posix().replace("/", "--")
                else:
                    continue
                if target.exists() and target.read_bytes() != path.read_bytes():
                    raise ValueError(f"Existing archive evidence differs; preserve it and use a new version: {target}")
                if not target.exists():
                    shutil.copyfile(path, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    works = discover(root)
    catalog = {"schema_version": 1, "repository": REPOSITORY, "works": []}
    # Inspect/hash every source before emitting catalog/index changes.
    prepared = [(work, [make_asset(root, work, path) for path in work["files"]]) for work in works]
    for work, assets in prepared:
        write_work(root, work, assets)
        record = {key: value for key, value in work.items() if key != "files"}
        record["assets"] = assets
        catalog["works"].append(record)
    directory = root / "archive"
    directory.mkdir(exist_ok=True)
    (directory / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(asset["bytes"] for _, assets in prepared for asset in assets)
    count = sum(len(assets) for _, assets in prepared)
    index = "# 全部作品索引\n\n每部作品独立目录，按 B站/小红书画幅提供下载索引。成片和工程 ZIP 位于本仓库 Releases。\n\n"
    for work, assets in prepared:
        relative = Path(work["delivery_directory"]).relative_to("deliveries").as_posix()
        index += f"- [{work['title']}]({quote(relative, safe='/')}/README.md)：{len(assets)} 个视频/工程资产。\n"
    (root / "deliveries" / "README.md").write_text(index, encoding="utf-8")
    print(f"Indexed {len(works)} works, {count} media/project assets, {total:,} bytes; originals unchanged")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, StopIteration, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Archive indexing stopped: {error}") from None
