"""Create a derived scene with a safer camera path for the returning shard.

This script only edits camera and focus animation in a new .blend file. It
does not render frames, modify user preferences, or overwrite either input.

Run from the repository root with Blender::

    blender --background --factory-startup --disable-autoexec \
      --python deliveries/si-ep11-kintsugi-ink-v03/project/blender/reframe_hero.py -- \
      --blend deliveries/si-ep11-kintsugi-ink-v03/project/blender/porcelain-canyon-v03.blend \
      --out-blend deliveries/si-ep11-kintsugi-ink-v03/project/blender/porcelain-canyon-hero-v03.blend \
      --report deliveries/si-ep11-kintsugi-ink-v03/review/reframe-hero-v03.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import struct
import sys
from pathlib import Path
from typing import Any


FRAME_START = 1
FRAME_END = 1525
FPS = 30
FILM_FRAME_START = 550
REFRAME_START = 1132
REFRAME_END = 1362
HERO_NAME = "Keystone / actual socket fragment"
PARENT_NAME = "Bank R03"
OUTPUT_BLEND_NAME = "porcelain-canyon-hero-v03.blend"
DOLLY_MAX = 4.0
MAX_BBOX_WIDTH = 0.68
MAX_BBOX_HEIGHT = 0.48
TARGET_CENTER = (0.45, 0.58)
SAFE_BOUNDS = {"min_x": 0.06, "max_x": 0.84, "min_y": 0.30, "max_y": 0.86}
SHIFT_EPSILON = 0.001
FIT_TOLERANCE = 1e-8
CENTER_TOLERANCE = 1e-5


class ReframeNeedsSol(RuntimeError):
    """A measured frame cannot meet the decided camera fit constraints."""

    def __init__(self, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Create a derived .blend with a fitted hero-shard camera animation."
    )
    result.add_argument("--blend", required=True, help="Exact saved source .blend file")
    result.add_argument("--out-blend", required=True, help=f"New output named {OUTPUT_BLEND_NAME}")
    result.add_argument("--report", required=True, help="New JSON report path under the v03 delivery")
    return result


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


def constrained_path(value: str, root: Path, suffix: str, *, exact_name: str | None = None) -> Path:
    root = root.resolve(strict=True)
    target = Path(value).expanduser().resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path must be inside {root}: {target}") from exc
    if target == root or target.suffix.lower() != suffix:
        raise ValueError(f"path must be a {suffix} file inside {root}: {target}")
    if exact_name and target.name != exact_name:
        raise ValueError(f"output filename must be {exact_name}")
    if not target.parent.is_dir():
        raise ValueError(f"output parent must already exist: {target.parent}")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing output: {target}")
    return target


def output_paths(out_blend_value: str, report_value: str, source: Path) -> tuple[Path, Path]:
    script_path = Path(__file__).resolve()
    delivery_root = script_path.parents[2]
    project_blender = script_path.parent
    delivery_blender = constrained_path(
        out_blend_value,
        project_blender,
        ".blend",
        exact_name=OUTPUT_BLEND_NAME,
    )
    report = constrained_path(report_value, delivery_root, ".json")
    if delivery_blender == source:
        raise ValueError("--out-blend must be a different path from --blend")
    return delivery_blender, report


def top_z(x: float, y: float) -> float:
    # Kept in sync with the canonical scene.py surface used by Bank R03.
    return 1.72 + 0.034 * x * x + 0.005 * y * y + 0.09 * math.sin(y * 0.48) + 0.022 * math.sin(x * 1.8 + y * 0.9)


def scene_contract(scene: Any) -> dict[str, Any]:
    effective_fps = float(scene.render.fps) / float(scene.render.fps_base)
    observed = {
        "frame_start": int(scene.frame_start),
        "frame_end": int(scene.frame_end),
        "fps": float(scene.render.fps),
        "fps_base": float(scene.render.fps_base),
        "effective_fps": effective_fps,
        "film_frame_start": scene.get("film_frame_start"),
        "source_fps": scene.get("source_fps"),
    }
    if (
        scene.frame_start != FRAME_START
        or scene.frame_end != FRAME_END
        or not math.isclose(effective_fps, FPS, rel_tol=0.0, abs_tol=1e-9)
        or scene.get("film_frame_start") != FILM_FRAME_START
        or float(scene.get("source_fps", -1)) != FPS
    ):
        raise RuntimeError(f"source scene contract mismatch: {observed}")
    handlers = {
        "frame_change_pre": len(__import__("bpy").app.handlers.frame_change_pre),
        "frame_change_post": len(__import__("bpy").app.handlers.frame_change_post),
    }
    if handlers["frame_change_pre"] or handlers["frame_change_post"]:
        raise RuntimeError(f"source scene must have no frame_change handlers: {handlers}")
    observed["frame_change_handlers"] = handlers
    return observed


def point_list(value: Any, prop_name: str, expected_count: int) -> list[tuple[float, float]]:
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"hero {prop_name} property is not valid JSON") from exc
    if not isinstance(decoded, list) or len(decoded) != expected_count:
        raise RuntimeError(f"hero {prop_name} must contain {expected_count} XY points")
    points: list[tuple[float, float]] = []
    for point in decoded:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise RuntimeError(f"hero {prop_name} contains an invalid XY point: {point!r}")
        points.append((float(point[0]), float(point[1])))
    return points


def evaluated_object(obj: Any, depsgraph: Any) -> Any:
    return obj.evaluated_get(depsgraph)


def subject_points(scene: Any, hero: Any, parent: Any, socket_xy: list[tuple[float, float]], Vector: Any) -> tuple[list[Any], dict[str, list[float]]]:
    bpy = __import__("bpy")
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_hero = evaluated_object(hero, depsgraph)
    evaluated_parent = evaluated_object(parent, depsgraph)

    bounds = [Vector(corner) for corner in evaluated_hero.bound_box]
    if len(bounds) != 8:
        raise RuntimeError(f"hero bound_box must have eight corners; found {len(bounds)}")
    local_min = Vector((min(corner.x for corner in bounds), min(corner.y for corner in bounds), min(corner.z for corner in bounds)))
    local_max = Vector((max(corner.x for corner in bounds), max(corner.y for corner in bounds), max(corner.z for corner in bounds)))
    padding = 0.04
    local_min -= Vector((padding, padding, padding))
    local_max += Vector((padding, padding, padding))
    hero_corners = [
        evaluated_hero.matrix_world @ Vector((x, y, z))
        for x in (local_min.x, local_max.x)
        for y in (local_min.y, local_max.y)
        for z in (local_min.z, local_max.z)
    ]
    socket_world = [
        evaluated_parent.matrix_world @ Vector((x, y, top_z(x, y)))
        for x, y in socket_xy
    ]
    all_points = hero_corners + socket_world
    minimum = [min(float(point[axis]) for point in all_points) for axis in range(3)]
    maximum = [max(float(point[axis]) for point in all_points) for axis in range(3)]
    center = [(minimum[axis] + maximum[axis]) / 2 for axis in range(3)]
    return all_points, {"min": minimum, "max": maximum, "center": center}


def action_fcurve_collections(id_block: Any) -> list[Any]:
    """Return the active Action's legacy and slotted F-Curve collections.

    Blender 4.4+ stores keyframes in Action layers/strips/channelbags. The
    legacy ``action.fcurves`` accessor can be empty for those Actions, so
    inspect the channelbag belonging to this data-block's active slot too.
    """
    animation = id_block.animation_data
    action = animation.action if animation else None
    if action is None:
        return []

    collections = []
    try:
        collections.append(action.fcurves)
    except (AttributeError, RuntimeError, TypeError):
        pass

    active_slot = getattr(animation, "action_slot", None)
    for layer in getattr(action, "layers", ()):
        for strip in layer.strips:
            if getattr(strip, "type", None) != "KEYFRAME":
                continue
            for channelbag in getattr(strip, "channelbags", ()):
                if active_slot is None or channelbag.slot == active_slot:
                    collections.append(channelbag.fcurves)
    return collections


def action_fcurve_entries(id_block: Any) -> list[tuple[Any, Any]]:
    result = []
    seen = set()
    for collection in action_fcurve_collections(id_block):
        for curve in collection:
            pointer = int(curve.as_pointer())
            if pointer not in seen:
                result.append((collection, curve))
                seen.add(pointer)
    return result


def camera_curves(camera: Any) -> list[tuple[Any, Any]]:
    result = []
    specifications = (
        (camera, {"location", "rotation_euler"}),
        (camera.data, {"lens", "shift_x", "shift_y"}),
    )
    for id_block, paths in specifications:
        result.extend(
            (id_block, curve)
            for _collection, curve in action_fcurve_entries(id_block)
            if curve.data_path in paths
        )
    return result


def mute_camera_curves(camera: Any, original_mutes: dict[int, tuple[Any, bool]]) -> None:
    for _id_block, curve in camera_curves(camera):
        pointer = int(curve.as_pointer())
        original_mutes.setdefault(pointer, (curve, bool(curve.mute)))
        curve.mute = True


def restore_camera_curves(original_mutes: dict[int, tuple[Any, bool]]) -> None:
    for curve, muted in original_mutes.values():
        curve.mute = muted


def remove_existing_shift_curves(camera: Any) -> int:
    removed = 0
    for collection, curve in action_fcurve_entries(camera.data):
        if curve.data_path in {"shift_x", "shift_y"}:
            collection.remove(curve)
            removed += 1
    return removed


def project_bbox(scene: Any, camera: Any, points: list[Any], world_to_camera_view: Any) -> dict[str, Any]:
    bpy = __import__("bpy")
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_camera = camera.evaluated_get(depsgraph)
    projected = [world_to_camera_view(scene, evaluated_camera, point) for point in points]
    xs = [float(point.x) for point in projected]
    ys = [float(point.y) for point in projected]
    depths = [float(point.z) for point in projected]
    minimum_x, maximum_x = min(xs), max(xs)
    minimum_y, maximum_y = min(ys), max(ys)
    return {
        "min_x": minimum_x,
        "max_x": maximum_x,
        "min_y": minimum_y,
        "max_y": maximum_y,
        "width": maximum_x - minimum_x,
        "height": maximum_y - minimum_y,
        "center_x": (minimum_x + maximum_x) / 2,
        "center_y": (minimum_y + maximum_y) / 2,
        "min_depth": min(depths),
        "max_depth": max(depths),
    }


def bbox_fits(bbox: dict[str, Any]) -> bool:
    return (
        bbox["min_depth"] > 0
        and bbox["width"] <= MAX_BBOX_WIDTH + FIT_TOLERANCE
        and bbox["height"] <= MAX_BBOX_HEIGHT + FIT_TOLERANCE
    )


def inside_safe_bounds(bbox: dict[str, Any]) -> bool:
    return (
        bbox["min_x"] >= SAFE_BOUNDS["min_x"] - FIT_TOLERANCE
        and bbox["max_x"] <= SAFE_BOUNDS["max_x"] + FIT_TOLERANCE
        and bbox["min_y"] >= SAFE_BOUNDS["min_y"] - FIT_TOLERANCE
        and bbox["max_y"] <= SAFE_BOUNDS["max_y"] + FIT_TOLERANCE
    )


def put_camera_pose(camera: Any, location: Any, rotation: Any, lens: float, frame: int) -> None:
    camera.location = location
    camera.rotation_euler = rotation
    camera.data.lens = lens
    camera.keyframe_insert(data_path="location", frame=frame)
    camera.keyframe_insert(data_path="rotation_euler", frame=frame)
    camera.data.keyframe_insert(data_path="lens", frame=frame)


def solve_shift(
    scene: Any,
    camera: Any,
    points: list[Any],
    world_to_camera_view: Any,
    frame: int,
) -> tuple[dict[str, Any], float, float]:
    def measure(shift_x: float, shift_y: float) -> dict[str, Any]:
        camera.data.shift_x = shift_x
        camera.data.shift_y = shift_y
        return project_bbox(scene, camera, points, world_to_camera_view)

    shift_x = 0.0
    shift_y = 0.0
    current = measure(shift_x, shift_y)
    for _iteration in range(8):
        error_x = TARGET_CENTER[0] - current["center_x"]
        error_y = TARGET_CENTER[1] - current["center_y"]
        if max(abs(error_x), abs(error_y)) <= CENTER_TOLERANCE:
            return current, shift_x, shift_y
        shifted_x = measure(shift_x + SHIFT_EPSILON, shift_y)
        shifted_y = measure(shift_x, shift_y + SHIFT_EPSILON)
        j11 = (shifted_x["center_x"] - current["center_x"]) / SHIFT_EPSILON
        j21 = (shifted_x["center_y"] - current["center_y"]) / SHIFT_EPSILON
        j12 = (shifted_y["center_x"] - current["center_x"]) / SHIFT_EPSILON
        j22 = (shifted_y["center_y"] - current["center_y"]) / SHIFT_EPSILON
        determinant = j11 * j22 - j12 * j21
        if abs(determinant) < 1e-12:
            raise ReframeNeedsSol(
                f"camera shift Jacobian is singular at frame {frame}",
                {"frame": frame, "bbox": current, "jacobian": [[j11, j12], [j21, j22]]},
            )
        delta_x = (error_x * j22 - error_y * j12) / determinant
        delta_y = (j11 * error_y - j21 * error_x) / determinant
        shift_x += delta_x
        shift_y += delta_y
        current = measure(shift_x, shift_y)
    if max(abs(current["center_x"] - TARGET_CENTER[0]), abs(current["center_y"] - TARGET_CENTER[1])) > CENTER_TOLERANCE:
        raise ReframeNeedsSol(
            f"camera shift did not converge at frame {frame}",
            {"frame": frame, "bbox": current, "shift_x": shift_x, "shift_y": shift_y},
        )
    return current, shift_x, shift_y


def set_constant_shift_curves(camera: Any) -> None:
    found = set()
    for _collection, curve in action_fcurve_entries(camera.data):
        if curve.data_path in {"shift_x", "shift_y"}:
            found.add(curve.data_path)
            for key in curve.keyframe_points:
                key.interpolation = "CONSTANT"
    if found != {"shift_x", "shift_y"}:
        raise RuntimeError(f"camera shift curves were not created: found {sorted(found)}")


def vector3(vector: Any) -> list[float]:
    return [float(vector[index]) for index in range(3)]


def geometry_state(scene: Any) -> tuple[str, list[dict[str, Any]]]:
    digest = hashlib.sha256()
    material_refs: list[dict[str, Any]] = []
    for obj in sorted((item for item in scene.objects if item.type == "MESH"), key=lambda item: item.name):
        mesh = obj.data
        digest.update(b"OBJECT\0")
        digest.update(obj.name.encode("utf-8") + b"\0")
        digest.update(mesh.name.encode("utf-8") + b"\0")
        digest.update(struct.pack(">III", len(mesh.vertices), len(mesh.edges), len(mesh.polygons)))
        for vertex in mesh.vertices:
            digest.update(struct.pack(">ddd", float(vertex.co.x), float(vertex.co.y), float(vertex.co.z)))
        digest.update(b"MATERIALS\0")
        refs = []
        for slot in mesh.materials:
            if slot is None:
                refs.append({"name": None, "library": None, "identity": None})
                digest.update(b"NONE\0")
            else:
                library = slot.library.filepath if slot.library else None
                identity = int(slot.as_pointer())
                refs.append({"name": slot.name_full, "library": library, "identity": identity})
                digest.update(json.dumps([slot.name_full, library], separators=(",", ":")).encode("utf-8") + b"\0")
        for polygon in mesh.polygons:
            digest.update(struct.pack(">I", len(polygon.vertices)))
            for index in polygon.vertices:
                digest.update(struct.pack(">I", int(index)))
            digest.update(struct.pack(">i", int(polygon.material_index)))
        material_refs.append({"object": obj.name, "mesh": mesh.name, "slots": refs})
    return digest.hexdigest(), material_refs


def restore_frame_change_handlers(bpy: Any) -> list[str]:
    return [
        f"pre:{getattr(handler, '__module__', '')}.{getattr(handler, '__qualname__', getattr(handler, '__name__', type(handler).__name__))}"
        for handler in bpy.app.handlers.frame_change_pre
    ] + [
        f"post:{getattr(handler, '__module__', '')}.{getattr(handler, '__qualname__', getattr(handler, '__name__', type(handler).__name__))}"
        for handler in bpy.app.handlers.frame_change_post
    ]


def run_reframe(bpy: Any, bmesh: Any, source: Path, out_blend: Path) -> dict[str, Any]:
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    scene = bpy.context.scene
    contract = scene_contract(scene)
    hero = scene.objects.get(HERO_NAME)
    parent = scene.objects.get(PARENT_NAME)
    camera = scene.camera
    if hero is None or hero.type != "MESH":
        raise RuntimeError(f"hero mesh is missing: {HERO_NAME}")
    if parent is None or parent.type != "MESH":
        raise RuntimeError(f"socket parent mesh is missing: {PARENT_NAME}")
    if camera is None or camera.type != "CAMERA":
        raise RuntimeError("scene has no active camera")
    focus = camera.data.dof.focus_object
    if focus is None:
        raise RuntimeError("camera depth-of-field focus object is missing")
    socket_xy = point_list(hero.get("socket_outline"), "socket_outline", 6)
    initial_frame = scene.frame_current
    geometry_before_sha, material_refs_before = geometry_state(scene)
    source_sha_before = sha256_file(source)
    original_projection_by_frame: dict[int, dict[str, Any]] = {}
    # Measure the actual saved camera before removing or muting any of its
    # animation curves, so the report records the crop that motivated this
    # derived scene rather than a partially corrected camera.
    for frame in range(REFRAME_START, REFRAME_END + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        points, _world_aabb = subject_points(scene, hero, parent, socket_xy, Vector)
        original_projection_by_frame[frame] = project_bbox(scene, camera, points, world_to_camera_view)
    scene.frame_set(initial_frame)
    bpy.context.view_layer.update()

    original_mutes: dict[int, tuple[Any, bool]] = {}
    cleared_shift_curves = remove_existing_shift_curves(camera)
    camera.data.shift_x = 0.0
    camera.data.shift_y = 0.0
    frame_solutions: list[dict[str, Any]] = []

    try:
        for frame in range(REFRAME_START, REFRAME_END + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            points, world_aabb = subject_points(scene, hero, parent, socket_xy, Vector)
            original_bbox = original_projection_by_frame[frame]
            mute_camera_curves(camera, original_mutes)
            camera.data.lens = 40.0
            camera.data.shift_x = 0.0
            camera.data.shift_y = 0.0
            bpy.context.view_layer.update()
            center = Vector(world_aabb["center"])
            u = (frame - REFRAME_START) / (REFRAME_END - REFRAME_START)
            base_location = Vector((-0.25 + 0.7 * u, -5.0 - 0.3 * u, 5.2 + 0.7 * u))
            offset = base_location - center
            if offset.length <= 1e-9:
                raise ReframeNeedsSol(
                    f"base camera position coincides with subject center at frame {frame}",
                    {"frame": frame, "subject_world_aabb": world_aabb},
                )
            direction = offset.normalized()
            rotation = (-direction).to_track_quat("-Z", "Y").to_euler()
            base_distance = offset.length

            def apply_factor(factor: float) -> dict[str, Any]:
                location = center + direction * (base_distance * factor)
                put_camera_pose(camera, location, rotation, 40.0, frame)
                camera.data.shift_x = 0.0
                camera.data.shift_y = 0.0
                bpy.context.view_layer.update()
                return project_bbox(scene, camera, points, world_to_camera_view)

            bbox_one = apply_factor(1.0)
            factor = 1.0
            fitted = bbox_one
            if not bbox_fits(bbox_one):
                bbox_four = apply_factor(DOLLY_MAX)
                if not bbox_fits(bbox_four):
                    raise ReframeNeedsSol(
                        f"subject cannot fit within factor {DOLLY_MAX:g} at frame {frame}",
                        {
                            "frame": frame,
                            "max_factor": DOLLY_MAX,
                            "bbox_at_factor_1": bbox_one,
                            "bbox_at_max_factor": bbox_four,
                            "subject_world_aabb": world_aabb,
                        },
                    )
                low, high = 1.0, DOLLY_MAX
                for _ in range(12):
                    middle = (low + high) / 2
                    measured = apply_factor(middle)
                    if bbox_fits(measured):
                        high = middle
                        fitted = measured
                    else:
                        low = middle
                factor = high
                fitted = apply_factor(factor)

            fitted, shift_x, shift_y = solve_shift(
                scene,
                camera,
                points,
                world_to_camera_view,
                frame,
            )
            if not bbox_fits(fitted):
                raise ReframeNeedsSol(
                    f"projected subject exceeds size limit after shift solve at frame {frame}",
                    {"frame": frame, "bbox": fitted, "dolly_factor": factor},
                )
            if not inside_safe_bounds(fitted):
                raise ReframeNeedsSol(
                    f"projected subject is outside the safe box at frame {frame}",
                    {"frame": frame, "bbox": fitted, "dolly_factor": factor},
                )

            camera.location = center + direction * (base_distance * factor)
            camera.rotation_euler = rotation
            camera.data.lens = 40.0
            camera.data.shift_x = shift_x
            camera.data.shift_y = shift_y
            camera.keyframe_insert(data_path="location", frame=frame)
            camera.keyframe_insert(data_path="rotation_euler", frame=frame)
            camera.data.keyframe_insert(data_path="lens", frame=frame)
            camera.data.keyframe_insert(data_path="shift_x", frame=frame)
            camera.data.keyframe_insert(data_path="shift_y", frame=frame)
            focus.location = center
            focus.keyframe_insert(data_path="location", frame=frame)
            camera.data.dof.aperture_fstop = 8.0
            camera.data.dof.keyframe_insert(data_path="aperture_fstop", frame=frame)
            mute_camera_curves(camera, original_mutes)

            frame_solutions.append(
                {
                    "frame": frame,
                    "time_seconds": (frame - FRAME_START) / FPS,
                    "subject_world_aabb": world_aabb,
                    "target_world_center": vector3(center),
                    "dolly_factor": factor,
                    "camera_location": vector3(camera.location),
                    "camera_rotation_euler": vector3(camera.rotation_euler),
                    "lens": 40.0,
                    "shift_x": shift_x,
                    "shift_y": shift_y,
                    "original_projected_bbox": original_bbox,
                    "fit_bbox_during_solution": fitted,
                }
            )

        # Shift must be exactly zero before and after the native hero segment.
        for frame in (REFRAME_START - 1, REFRAME_END + 1):
            scene.frame_set(frame)
            mute_camera_curves(camera, original_mutes)
            camera.data.shift_x = 0.0
            camera.data.shift_y = 0.0
            camera.data.keyframe_insert(data_path="shift_x", frame=frame)
            camera.data.keyframe_insert(data_path="shift_y", frame=frame)
            mute_camera_curves(camera, original_mutes)
        set_constant_shift_curves(camera)
    finally:
        restore_camera_curves(original_mutes)

    scene.frame_set(initial_frame)
    bpy.context.view_layer.update()
    geometry_after_sha, material_refs_after = geometry_state(scene)
    geometry_unchanged = geometry_before_sha == geometry_after_sha
    material_refs_unchanged = material_refs_before == material_refs_after
    if not geometry_unchanged or not material_refs_unchanged:
        raise ReframeNeedsSol(
            "camera correction changed mesh vertex or material-reference data",
            {
                "geometry_before_sha256": geometry_before_sha,
                "geometry_after_sha256": geometry_after_sha,
                "material_references_unchanged": material_refs_unchanged,
            },
        )

    solution_by_frame = {item["frame"]: item for item in frame_solutions}
    projected_frames = []
    for frame in range(REFRAME_START, REFRAME_END + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        points, world_aabb = subject_points(scene, hero, parent, socket_xy, Vector)
        bbox = project_bbox(scene, camera, points, world_to_camera_view)
        solution = solution_by_frame[frame]
        safe = bbox_fits(bbox) and inside_safe_bounds(bbox)
        center_error = {
            "x": bbox["center_x"] - TARGET_CENTER[0],
            "y": bbox["center_y"] - TARGET_CENTER[1],
        }
        if not safe or max(abs(center_error["x"]), abs(center_error["y"])) > CENTER_TOLERANCE:
            raise ReframeNeedsSol(
                f"final keyed camera fails projection verification at frame {frame}",
                {
                    "frame": frame,
                    "bbox": bbox,
                    "center_error": center_error,
                    "inside_safe_box": inside_safe_bounds(bbox),
                    "size_fit": bbox_fits(bbox),
                },
            )
        projected_frames.append(
            {
                "frame": frame,
                "time_seconds": (frame - FRAME_START) / FPS,
                "projected_bbox": bbox,
                "original_projected_bbox": solution["original_projected_bbox"],
                "within_safe_box": safe,
                "center_error": center_error,
                "dolly_factor": solution["dolly_factor"],
                "camera_location": vector3(camera.location),
                "camera_rotation_euler": vector3(camera.rotation_euler),
                "lens": float(camera.data.lens),
                "shift_x": float(camera.data.shift_x),
                "shift_y": float(camera.data.shift_y),
                "subject_world_aabb": world_aabb,
            }
        )

    scene.frame_set(initial_frame)
    bpy.context.view_layer.update()
    geometry_final_sha, material_refs_final = geometry_state(scene)
    if geometry_final_sha != geometry_before_sha or material_refs_final != material_refs_before:
        raise ReframeNeedsSol(
            "final camera evaluation changed mesh vertex or material-reference data",
            {
                "geometry_before_sha256": geometry_before_sha,
                "geometry_final_sha256": geometry_final_sha,
                "material_references_unchanged": material_refs_before == material_refs_final,
            },
        )
    if sha256_file(source) != source_sha_before:
        raise ReframeNeedsSol("source .blend changed during reframe", {"input_sha256_before": source_sha_before})

    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    output_sha = sha256_file(out_blend)
    source_sha_after = sha256_file(source)
    if source_sha_after != source_sha_before:
        raise ReframeNeedsSol(
            "source .blend hash changed while writing derived scene",
            {"input_sha256_before": source_sha_before, "input_sha256_after": source_sha_after},
        )

    widths = [item["projected_bbox"]["width"] for item in projected_frames]
    heights = [item["projected_bbox"]["height"] for item in projected_frames]
    factors = [item["dolly_factor"] for item in projected_frames]
    return {
        "schema_version": 1,
        "status": "DONE",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "blender_version": bpy.app.version_string,
        "source": {"path": str(source), "sha256": source_sha_before},
        "output": {"path": str(out_blend), "sha256": output_sha},
        "scene_contract": contract,
        "reframe": {
            "first_frame": REFRAME_START,
            "last_frame": REFRAME_END,
            "frame_count": len(projected_frames),
            "camera_lens": 40.0,
            "dolly_factor_range": [1.0, DOLLY_MAX],
            "maximum_bbox_width": MAX_BBOX_WIDTH,
            "maximum_bbox_height": MAX_BBOX_HEIGHT,
            "target_bbox_center": list(TARGET_CENTER),
            "safe_bounds": SAFE_BOUNDS,
            "local_hero_padding": 0.04,
            "shift_keys_outside_segment": {
                str(REFRAME_START - 1): [0.0, 0.0],
                str(REFRAME_END + 1): [0.0, 0.0],
                "interpolation": "CONSTANT",
                "removed_source_shift_curves": cleared_shift_curves,
            },
            "focus_fstop": 8.0,
            "geometry_vertex_material_sha256_before": geometry_before_sha,
            "geometry_vertex_material_sha256_after": geometry_final_sha,
            "geometry_unchanged": geometry_final_sha == geometry_before_sha,
            "material_references_unchanged": material_refs_final == material_refs_before,
            "material_reference_slots": [
                {
                    "object": item["object"],
                    "mesh": item["mesh"],
                    "slots": [
                        {"name": slot["name"], "library": slot["library"]}
                        for slot in item["slots"]
                    ],
                }
                for item in material_refs_before
            ],
            "projection_summary": {
                "verified_frame_count": len(projected_frames),
                "all_within_safe_bounds": all(item["within_safe_box"] for item in projected_frames),
                "max_bbox_width": max(widths),
                "max_bbox_height": max(heights),
                "max_dolly_factor": max(factors),
                "max_center_error_x": max(abs(item["center_error"]["x"]) for item in projected_frames),
                "max_center_error_y": max(abs(item["center_error"]["y"]) for item in projected_frames),
            },
            "projected_bboxes": projected_frames,
            "camera_solutions": frame_solutions,
        },
    }


def atomic_report(path: Path, report: dict[str, Any]) -> None:
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"refusing to overwrite report: {path}")
        os.link(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def main() -> int:
    p = parser()
    args = p.parse_args(script_args(sys.argv))
    script_path = Path(__file__).resolve()
    delivery_root = script_path.parents[2].parent
    project_blender = script_path.parent
    try:
        source = Path(args.blend).expanduser().resolve(strict=True)
        if not source.is_file() or source.suffix.lower() != ".blend":
            raise ValueError(f"--blend must name an existing .blend file: {source}")
        out_blend, report_path = output_paths(args.out_blend, args.report, source)
    except Exception as exc:
        print(f"reframe_hero.py: error: {exc}", file=sys.stderr, flush=True)
        return 2

    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "ERROR",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": {"path": str(source), "sha256": None},
        "output": {"path": str(out_blend), "sha256": None},
        "error": None,
    }
    try:
        if "--factory-startup" not in sys.argv or "--disable-autoexec" not in sys.argv:
            raise RuntimeError("launch Blender with --factory-startup and --disable-autoexec")
        source_sha = sha256_file(source)
        report["source"]["sha256"] = source_sha
        import bpy
        import bmesh  # noqa: F401 - Blender module required by its saved-scene mesh types.

        bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
        if sha256_file(source) != source_sha:
            raise RuntimeError("source .blend changed while opening")
        report = run_reframe(bpy, bmesh, source, out_blend)
    except ReframeNeedsSol as exc:
        report.update(
            {
                "status": "NEEDS_SOL",
                "error": str(exc),
                "failure_evidence": exc.evidence,
            }
        )
        print(f"reframe_hero.py: NEEDS_SOL: {exc}", file=sys.stderr, flush=True)
    except Exception as exc:
        report.update({"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"})
        print(f"reframe_hero.py: error: {exc}", file=sys.stderr, flush=True)

    try:
        atomic_report(report_path, report)
    except Exception as exc:
        print(f"reframe_hero.py: could not write report: {exc}", file=sys.stderr, flush=True)
        return 2
    print(f"reframe report: {report_path}", flush=True)
    if report.get("status") == "DONE":
        print(f"derived scene: {report['output']['path']}", flush=True)
        return 0
    return 3 if report.get("status") == "NEEDS_SOL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
