"""Collect geometry and native-keyframe evidence from a saved EP11 v03 scene.

Example invocation::

    blender --background --factory-startup --disable-autoexec \
      --python verify_scene.py -- --blend scene.blend \
      --out ../../review/blender-scene-evidence.json

The output report must be a new JSON path inside this version's review folder.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


FRAME_START = 1
FRAME_END = 1525
SOURCE_FPS = 30
FILM_FRAME_START = 550
HERO_NAME = "Keystone / actual socket fragment"
PARENT_NAME = "Bank R03"
SAMPLE_FRAMES = (1081, 1136, 1171, 1297, 1471)
POINT_TOLERANCE = 1e-5
POSE_TOLERANCE = 1e-6
BANK_NAME_RE = re.compile(r"^Bank [LR](\d{2})$")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Verify saved-scene timing, shard geometry, outlines, and native poses."
    )
    p.add_argument("--blend", required=True, help="Exact saved .blend file to inspect")
    p.add_argument("--out", required=True, help="New JSON report path inside v03/review")
    return p


def script_args(argv: list[str]) -> list[str]:
    if "--" in argv:
        return argv[argv.index("--") + 1 :]
    return argv[1:]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def review_output_path(value: str) -> Path:
    review_root = (Path(__file__).resolve().parents[2] / "review").resolve(strict=True)
    out = Path(value).expanduser().resolve(strict=False)
    try:
        out.relative_to(review_root)
    except ValueError as exc:
        raise ValueError(f"--out must be inside {review_root}; got {out}") from exc
    if out == review_root or out.suffix.lower() != ".json":
        raise ValueError("--out must name a .json report file inside the review directory")
    if not out.parent.is_dir():
        raise ValueError(f"report parent directory must already exist: {out.parent}")
    if out.exists() or out.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing evidence report: {out}")
    return out


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, **details: Any) -> None:
    checks.append({"id": check_id, "passed": bool(passed), **details})


def as_float_list(values: Any) -> list[float]:
    return [float(value) for value in values]


def matrix_rows(matrix: Any) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def vector_close(left: Any, right: Any, tolerance: float) -> bool:
    return len(left) == len(right) and all(
        abs(float(a) - float(b)) <= tolerance for a, b in zip(left, right)
    )


def xyz(matrix: Any) -> list[float]:
    return [float(matrix[row][3]) for row in range(3)]


def object_pose(obj: Any, frame: int, time_seconds: float) -> dict[str, Any]:
    matrix = obj.matrix_world.copy()
    return {
        "name": obj.name,
        "frame": frame,
        "time_seconds": time_seconds,
        "local_location": as_float_list(obj.location),
        "local_rotation_euler": as_float_list(obj.rotation_euler),
        "local_scale": as_float_list(obj.scale),
        "world_location": xyz(matrix),
        "world_matrix": matrix_rows(matrix),
    }


def unique_points(points: list[tuple[float, float]], tolerance: float = 1e-8) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for point in points:
        if not any(math.dist(point, prior) <= tolerance for prior in result):
            result.append(point)
    return result


def static_xy_boundary(obj: Any, tolerance: float = 1e-8) -> list[list[float]]:
    """Find XY vertices joined by actual vertical extrusion edges in the mesh."""
    vertices = obj.data.vertices
    points: list[tuple[float, float]] = []
    for edge in obj.data.edges:
        first = vertices[edge.vertices[0]].co
        second = vertices[edge.vertices[1]].co
        if (
            abs(float(first.x) - float(second.x)) <= tolerance
            and abs(float(first.y) - float(second.y)) <= tolerance
            and abs(float(first.z) - float(second.z)) > tolerance
        ):
            points.append(((float(first.x) + float(second.x)) / 2, (float(first.y) + float(second.y)) / 2))
    return [[x, y] for x, y in unique_points(points, tolerance)]


def outline_points(value: Any, property_name: str) -> list[list[float]]:
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{property_name} is not valid JSON") from exc
    if not isinstance(decoded, list) or not decoded:
        raise ValueError(f"{property_name} must be a non-empty point list")
    points: list[list[float]] = []
    for point in decoded:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError(f"{property_name} contains a non-XY point: {point!r}")
        points.append([float(point[0]), float(point[1])])
    return points


def points_match(
    expected: list[list[float]],
    actual: list[list[float]],
    tolerance: float,
    *,
    exact: bool,
) -> bool:
    if exact and len(expected) != len(actual):
        return False
    unmatched = list(actual)
    for point in expected:
        candidate = next(
            (index for index, other in enumerate(unmatched) if math.dist(point, other) <= tolerance),
            None,
        )
        if candidate is None:
            return False
        unmatched.pop(candidate)
    return not unmatched if exact else True


def mesh_evidence(obj: Any, bmesh: Any) -> dict[str, Any]:
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
        volume = float(bm.calc_volume(signed=True))
    finally:
        bm.free()
    return {
        "name": obj.name,
        "vertex_count": len(obj.data.vertices),
        "edge_count": len(obj.data.edges),
        "face_count": len(obj.data.polygons),
        "non_manifold_edges": non_manifold,
        "signed_volume": volume,
        "manifold": non_manifold == 0,
        "positive_volume": volume > 0,
    }


def handler_identity(handler: Any) -> dict[str, str]:
    return {
        "module": str(getattr(handler, "__module__", "")),
        "name": str(getattr(handler, "__qualname__", getattr(handler, "__name__", type(handler).__name__))),
    }


def verify_scene(bpy: Any, bmesh: Any, blend: Path, opened_sha256: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    scene = bpy.context.scene
    actual_fps = float(scene.render.fps) / float(scene.render.fps_base)
    timing = {
        "frame_start": int(scene.frame_start),
        "frame_end": int(scene.frame_end),
        "fps": float(scene.render.fps),
        "fps_base": float(scene.render.fps_base),
        "effective_fps": actual_fps,
        "film_frame_start": scene.get("film_frame_start"),
        "source_fps": scene.get("source_fps"),
    }
    add_check(
        checks,
        "native_scene_timing",
        scene.frame_start == FRAME_START
        and scene.frame_end == FRAME_END
        and math.isclose(actual_fps, SOURCE_FPS, rel_tol=0.0, abs_tol=1e-9)
        and scene.get("film_frame_start") == FILM_FRAME_START
        and float(scene.get("source_fps", -1)) == SOURCE_FPS,
        expected={
            "frame_start": FRAME_START,
            "frame_end": FRAME_END,
            "fps": SOURCE_FPS,
            "film_frame_start": FILM_FRAME_START,
        },
        observed=timing,
    )

    handlers_pre = [handler_identity(item) for item in bpy.app.handlers.frame_change_pre]
    handlers_post = [handler_identity(item) for item in bpy.app.handlers.frame_change_post]
    add_check(
        checks,
        "no_frame_change_handlers",
        not handlers_pre and not handlers_post,
        observed={"frame_change_pre": handlers_pre, "frame_change_post": handlers_post},
    )

    stored_geometry: list[dict[str, Any]] = []
    stored_value = scene.get("geometry_checks_json")
    try:
        parsed = json.loads(stored_value) if isinstance(stored_value, str) else None
        if isinstance(parsed, list):
            stored_geometry = parsed
        stored_ok = bool(stored_geometry) and all(
            int(row.get("non_manifold_edges", -1)) == 0
            and float(row.get("volume", 0)) > 0
            for row in stored_geometry
        )
    except (TypeError, ValueError, json.JSONDecodeError, AttributeError):
        stored_ok = False
    add_check(
        checks,
        "saved_geometry_checks_json",
        stored_ok,
        entry_count=len(stored_geometry),
        entries=stored_geometry,
    )

    banks = [
        obj
        for obj in scene.objects
        if obj.type == "MESH" and BANK_NAME_RE.fullmatch(obj.name)
    ]
    banks_by_name = {obj.name: obj for obj in banks}
    expected_bank_names = [f"Bank {side}{index:02d}" for side in "LR" for index in range(8)]
    add_check(
        checks,
        "sixteen_named_bank_meshes",
        len(banks) == 16 and sorted(banks_by_name) == sorted(expected_bank_names),
        expected=sorted(expected_bank_names),
        observed=sorted(banks_by_name),
    )

    hero = scene.objects.get(HERO_NAME)
    parent = scene.objects.get(PARENT_NAME)
    mesh_objects = [obj for obj in banks if obj.type == "MESH"]
    if hero is not None and hero.type == "MESH":
        mesh_objects.append(hero)
    else:
        add_check(checks, "hero_mesh_exists", False, expected=HERO_NAME, observed=None)
    if parent is None or parent.type != "MESH":
        add_check(checks, "hero_parent_mesh_exists", False, expected=PARENT_NAME, observed=None)

    actual_mesh_checks: list[dict[str, Any]] = []
    for obj in mesh_objects:
        try:
            evidence = mesh_evidence(obj, bmesh)
            actual_mesh_checks.append(evidence)
            add_check(
                checks,
                f"actual_mesh_{obj.name}",
                evidence["manifold"] and evidence["positive_volume"],
                **evidence,
            )
        except Exception as exc:
            add_check(checks, f"actual_mesh_{obj.name}", False, error=f"{type(exc).__name__}: {exc}")
    expected_mesh_names = set(expected_bank_names + [HERO_NAME])
    observed_mesh_names = {row["name"] for row in actual_mesh_checks}
    add_check(
        checks,
        "independent_mesh_set_complete",
        observed_mesh_names == expected_mesh_names
        and all(row["manifold"] and row["positive_volume"] for row in actual_mesh_checks),
        expected_count=17,
        observed_count=len(actual_mesh_checks),
        missing=sorted(expected_mesh_names - observed_mesh_names),
    )

    outline_report: dict[str, Any] = {}
    if hero is not None and hero.type == "MESH" and parent is not None and parent.type == "MESH":
        hero_boundary = static_xy_boundary(hero)
        parent_boundary = static_xy_boundary(parent)
        parent_label = hero.get("parent")
        add_check(
            checks,
            "hero_parent_label",
            parent_label == PARENT_NAME and parent.name == PARENT_NAME,
            expected=PARENT_NAME,
            observed={"label": parent_label, "resolved_object": parent.name},
        )
        try:
            rest = outline_points(hero.get("rest_outline"), "rest_outline")
            rest_matches = points_match(rest, hero_boundary, POINT_TOLERANCE, exact=True)
            add_check(
                checks,
                "rest_outline_matches_actual_hero_xy_boundary",
                rest_matches,
                tolerance=POINT_TOLERANCE,
                outline_point_count=len(rest),
                actual_boundary_point_count=len(hero_boundary),
                outline_points=rest,
                actual_boundary=hero_boundary,
            )
            socket = outline_points(hero.get("socket_outline"), "socket_outline")
            socket_on_hero = points_match(socket, hero_boundary, POINT_TOLERANCE, exact=False)
            socket_on_parent = points_match(socket, parent_boundary, POINT_TOLERANCE, exact=False)
            add_check(
                checks,
                "socket_outline_matches_shared_mesh_boundary_points",
                socket_on_hero and socket_on_parent,
                tolerance=POINT_TOLERANCE,
                socket_point_count=len(socket),
                actual_hero_boundary_point_count=len(hero_boundary),
                actual_parent_boundary_point_count=len(parent_boundary),
                socket_points=socket,
                hero_boundary=hero_boundary,
                parent_boundary=parent_boundary,
                matches_hero=socket_on_hero,
                matches_parent=socket_on_parent,
            )
            outline_report = {
                "tolerance": POINT_TOLERANCE,
                "hero_static_xy_boundary": hero_boundary,
                "parent_static_xy_boundary": parent_boundary,
                "rest_outline": rest,
                "socket_outline": socket,
            }
        except Exception as exc:
            add_check(checks, "outline_properties_and_mesh_boundary", False, error=f"{type(exc).__name__}: {exc}")

    poses: list[dict[str, Any]] = []
    hold_a: dict[str, Any] | None = None
    hold_b: dict[str, Any] | None = None
    final_hero: dict[str, Any] | None = None
    final_parent: dict[str, Any] | None = None
    if hero is not None and hero.type == "MESH" and parent is not None and parent.type == "MESH":
        for frame in SAMPLE_FRAMES:
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            seconds = (frame - FRAME_START) / SOURCE_FPS
            hero_pose = object_pose(hero, frame, seconds)
            parent_pose = object_pose(parent, frame, seconds)
            relative_translation = [
                hero_pose["world_location"][index] - parent_pose["world_location"][index]
                for index in range(3)
            ]
            record = {
                "frame": frame,
                "time_seconds": seconds,
                "hero": hero_pose,
                "parent": parent_pose,
                "hero_minus_parent_world_translation": relative_translation,
            }
            poses.append(record)
            if frame == 1136:
                hold_a = record
            elif frame == 1171:
                hold_b = record
            elif frame == 1471:
                final_hero = hero_pose
                final_parent = parent_pose

    if hold_a is not None and hold_b is not None:
        same_hold_displacement = vector_close(
            hold_a["hero_minus_parent_world_translation"],
            hold_b["hero_minus_parent_world_translation"],
            POSE_TOLERANCE,
        )
        add_check(
            checks,
            "hero_hold_displacement_frames_1136_1171",
            same_hold_displacement,
            tolerance=POSE_TOLERANCE,
            frame_1136=hold_a["hero_minus_parent_world_translation"],
            frame_1171=hold_b["hero_minus_parent_world_translation"],
        )
    else:
        add_check(checks, "hero_hold_displacement_frames_1136_1171", False, error="sample poses unavailable")

    if final_hero is not None and final_parent is not None:
        same_position = vector_close(
            final_hero["world_location"], final_parent["world_location"], POSE_TOLERANCE
        )
        zero_euler = all(abs(value) <= POSE_TOLERANCE for value in final_hero["local_rotation_euler"])
        world_matrix = final_hero["world_matrix"]
        zero_world_rotation = all(
            abs(world_matrix[row][col] - (1.0 if row == col else 0.0)) <= POSE_TOLERANCE
            for row in range(3)
            for col in range(3)
        )
        add_check(
            checks,
            "hero_final_transform_matches_parent_location_zero_euler",
            same_position and zero_euler and zero_world_rotation,
            tolerance=POSE_TOLERANCE,
            hero_world_location=final_hero["world_location"],
            parent_world_location=final_parent["world_location"],
            hero_local_rotation_euler=final_hero["local_rotation_euler"],
            hero_world_rotation_matrix=[row[:3] for row in world_matrix[:3]],
        )
    else:
        add_check(checks, "hero_final_transform_matches_parent_location_zero_euler", False, error="final sample pose unavailable")

    if parent is not None and parent.type == "MESH":
        final_frame = SAMPLE_FRAMES[-1]
        scene.frame_set(final_frame)
        bpy.context.view_layer.update()
        bank_final: list[dict[str, Any]] = []
        bank_checks_ok = len(banks) == 16
        for bank in sorted(banks, key=lambda obj: obj.name):
            side = int(bank.get("side", 0))
            expected_x = side * 0.022
            world_location = xyz(bank.matrix_world)
            matches = (
                side in (-1, 1)
                and abs(world_location[0] - expected_x) <= POSE_TOLERANCE
                and abs(world_location[1]) <= POSE_TOLERANCE
                and abs(world_location[2]) <= POSE_TOLERANCE
            )
            bank_checks_ok = bank_checks_ok and matches
            row = {
                "name": bank.name,
                "side": side,
                "expected_x": expected_x,
                "world_location": world_location,
                "matches": matches,
            }
            bank_final.append(row)
            add_check(
                checks,
                f"final_bank_location_{bank.name}",
                matches,
                tolerance=POSE_TOLERANCE,
                **row,
            )
        add_check(
            checks,
            "all_banks_final_x_matches_side_offset",
            bank_checks_ok,
            tolerance=POSE_TOLERANCE,
            bank_count=len(bank_final),
            banks=bank_final,
        )
    else:
        bank_final = []
        add_check(checks, "all_banks_final_x_matches_side_offset", False, error="parent mesh unavailable")

    if sha256_file(blend) != opened_sha256:
        add_check(checks, "blend_unchanged_during_inspection", False, error="saved .blend changed during verification")
    else:
        add_check(checks, "blend_unchanged_during_inspection", True, sha256=opened_sha256)

    failed = [item["id"] for item in checks if not item["passed"]]
    return {
        "schema_version": 1,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "blend": {"path": str(blend), "sha256": opened_sha256},
        "blender": {"version": bpy.app.version_string},
        "scene_timing": timing,
        "checks": checks,
        "saved_geometry_checks_json": {
            "entry_count": len(stored_geometry),
            "entries": stored_geometry,
        },
        "actual_mesh_checks": actual_mesh_checks,
        "outlines": outline_report,
        "sampled_poses": poses,
        "banks_at_frame_1471": bank_final,
        "summary": {"passed": not failed, "failed_check_ids": failed},
    }


def atomic_write_report(path: Path, report: dict[str, Any]) -> None:
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"refusing to overwrite existing evidence report: {path}")
        os.link(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def main() -> int:
    p = parser()
    args = p.parse_args(script_args(sys.argv))
    try:
        blend = Path(args.blend).expanduser().resolve(strict=True)
        if not blend.is_file() or blend.suffix.lower() != ".blend":
            raise ValueError(f"--blend must name an existing .blend file: {blend}")
        out = review_output_path(args.out)
    except Exception as exc:
        print(f"verify_scene.py: error: {exc}", file=sys.stderr, flush=True)
        return 2

    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "blend": {"path": str(blend)},
        "checks": [],
        "summary": {"passed": False, "failed_check_ids": ["verification_not_completed"]},
    }
    try:
        if "--factory-startup" not in sys.argv or "--disable-autoexec" not in sys.argv:
            raise RuntimeError("launch Blender with --factory-startup and --disable-autoexec")
        opened_sha256 = sha256_file(blend)
        import bpy
        import bmesh

        bpy.ops.wm.open_mainfile(filepath=str(blend), load_ui=False, use_scripts=False)
        if sha256_file(blend) != opened_sha256:
            raise RuntimeError("saved .blend changed while it was being opened")
        report = verify_scene(bpy, bmesh, blend, opened_sha256)
    except Exception as exc:
        report["fatal_error"] = f"{type(exc).__name__}: {exc}"
        report["summary"] = {"passed": False, "failed_check_ids": ["fatal_error"]}
        print(f"verify_scene.py: error: {exc}", file=sys.stderr, flush=True)

    try:
        atomic_write_report(out, report)
    except Exception as exc:
        print(f"verify_scene.py: could not write report: {exc}", file=sys.stderr, flush=True)
        return 2
    print(f"verification report: {out}", flush=True)
    print(json.dumps(report.get("summary", {}), sort_keys=True), flush=True)
    return 0 if report.get("summary", {}).get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
