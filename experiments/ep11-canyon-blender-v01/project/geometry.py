"""Deterministic solid porcelain-bank and shard geometry for the EP11 study.

Coordinates follow the study contract: X is lateral, Y runs down the fissure,
and Z is vertical. Scene setup, materials, lighting, camera, and animation are
owned by the caller.
"""

from __future__ import annotations

from math import cos, pi, radians, sin, tau
from random import Random
from typing import Mapping

import bpy
from mathutils import Vector, noise


Y_MIN = -10.0
Y_MAX = 19.0
PIECES_PER_BANK = 9
ACROSS_STEPS = 16


def center_x(y: float) -> float:
    """Shared, gently bending centerline of the gold fissure."""
    return 0.42 * sin(0.28 * y) + 0.17 * sin(0.77 * y)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _fissure_half_width(y: float) -> float:
    """Widen the open crack toward the near-camera end (negative Y)."""
    near = _clamp((Y_MAX - y) / (Y_MAX - Y_MIN), 0.0, 1.0)
    return 0.68 + 0.34 * near + 0.07 * noise.noise(Vector((y*.73, 2.1, 4.2)))


def _inner_lip(y: float, side: int) -> float:
    broken_edge = .10 * noise.noise(Vector((y*.8, side*3.1, .2)))
    if side < 0:
        return 1.65 + 0.22 * sin(0.31 * y) + broken_edge
    return 2.1 + 0.32 * sin(0.27 * y + 0.7) + broken_edge


def _boundary_y(x: float, base_y: float, boundary_index: int) -> float:
    """Shared jagged cut path; adjacent pieces sample the same boundary curve."""
    index = float(boundary_index)
    return base_y + 0.18 * sin(0.9 * x + index) + 0.065 * sin(3.0 * x + 0.7 * index)


def _piece_boundaries(rng: Random, count: int) -> list[float]:
    weights = [rng.uniform(0.84, 1.16) for _ in range(count)]
    weight_sum = sum(weights)
    result = [Y_MIN]
    accumulated = Y_MIN
    for weight in weights:
        accumulated += (Y_MAX - Y_MIN) * weight / weight_sum
        result.append(accumulated)
    result[-1] = Y_MAX
    return result


def _station_values(rng: Random, y0: float, y1: float, count: int) -> list[float]:
    values = [y0]
    divisions = count - 1
    for index in range(1, divisions):
        t = index / divisions + rng.uniform(-0.12, 0.12) / divisions
        values.append(y0 + (y1 - y0) * t)
    values.append(y1)
    return values


def _append_face(
    faces: list[tuple[int, ...]],
    material_indices: list[int],
    smooth_flags: list[bool],
    face: tuple[int, ...],
    material_index: int,
    smooth: bool = False,
) -> None:
    faces.append(face)
    material_indices.append(material_index)
    smooth_flags.append(smooth)


def _boundary_ring(row_count: int, column_count: int, side: int) -> list[int]:
    """Return the top-grid perimeter counter-clockwise from above."""
    index = lambda row, column: row * column_count + column
    ring: list[int] = []
    if side > 0:
        ring.extend(index(0, column) for column in range(column_count))
        ring.extend(index(row, column_count - 1) for row in range(1, row_count))
        ring.extend(index(row_count - 1, column) for column in range(column_count - 2, -1, -1))
        ring.extend(index(row, 0) for row in range(row_count - 2, 0, -1))
    else:
        ring.extend(index(0, column) for column in range(column_count - 1, -1, -1))
        ring.extend(index(row, 0) for row in range(1, row_count))
        ring.extend(index(row_count - 1, column) for column in range(1, column_count))
        ring.extend(index(row, column_count - 1) for row in range(row_count - 2, 0, -1))
    return ring


def _add_bank_piece(
    name: str,
    side: int,
    base_y0: float,
    base_y1: float,
    boundary_index: int,
    gap_before: float,
    gap_after: float,
    piece_index: int,
    low_ledge: bool,
    materials: Mapping[str, bpy.types.Material],
    rng: Random,
) -> bpy.types.Object:
    row_count = rng.randint(32, 40)
    column_count = ACROSS_STEPS + 1
    row_fractions = _station_values(rng, 0.0, 1.0, row_count)
    outer_radius = rng.uniform(7.0, 7.72)
    outer_edge = [_clamp(outer_radius + .12 * noise.noise(
        Vector(((base_y0+(base_y1-base_y0)*r)*.45, side*2.7, 5.1))), 6.78, 7.96)
        for r in row_fractions]

    if side < 0:
        bank_peak = rng.uniform(2.2, 3.2)
        lip_clearance_floor = 2.37  # max(left inner lip) + 0.5
    else:
        bank_peak = rng.uniform(3.0, 4.8)
        lip_clearance_floor = 2.92  # max(right inner lip) + 0.5
    peak_height = max(bank_peak * 0.65, lip_clearance_floor) if low_ledge else max(bank_peak, lip_clearance_floor)
    base_z = rng.uniform(-0.34, -0.18)

    # Top grid samples one shared, jagged Y cut at each end and the unique outer edge.
    top_vertices: list[tuple[float, float, float]] = []
    for row, row_fraction in enumerate(row_fractions):
        outer_x = side * outer_edge[row]
        base_y = base_y0 + (base_y1 - base_y0) * row_fraction
        for column in range(column_count):
            u = column / (column_count - 1)
            across_jitter = 0.0
            start_inner = center_x(base_y) + side * (_fissure_half_width(base_y) + 0.02)
            x = start_inner + (outer_x - start_inner) * u + across_jitter
            for _ in range(5):
                start_y = _boundary_y(x, base_y0, boundary_index) + gap_before * 0.5
                end_y = _boundary_y(x, base_y1, boundary_index + 1) - gap_after * 0.5
                y = start_y + (end_y - start_y) * row_fraction
                inner_x = center_x(y) + side * (_fissure_half_width(y) + 0.02)
                x = inner_x + (outer_x - inner_x) * u + across_jitter
            start_y = _boundary_y(x, base_y0, boundary_index) + gap_before * 0.5
            end_y = _boundary_y(x, base_y1, boundary_index + 1) - gap_after * 0.5
            y = start_y + (end_y - start_y) * row_fraction
            inner_lip = _inner_lip(y, side)
            eased_u = u**1.35
            z = inner_lip + (peak_height - inner_lip) * eased_u
            top_vertices.append((x, y, z))

    top_vertex_count = len(top_vertices)
    vertices = list(top_vertices)
    vertices.extend((x, y, base_z) for x, y, _z in top_vertices)
    faces: list[tuple[int, ...]] = []
    material_indices: list[int] = []
    smooth_flags: list[bool] = []

    def orient_top(face: tuple[int, int, int]) -> tuple[int, int, int]:
        # Across-grid direction points toward +X on the right bank and -X on
        # the left. Reverse left-bank triangles to keep every top normal +Z.
        return face if side > 0 else (face[0], face[2], face[1])

    def grid_index(row: int, column: int) -> int:
        return row * column_count + column

    # Triangulate each gently curved top cell, alternating the diagonal.
    for row in range(row_count - 1):
        for column in range(column_count - 1):
            a = grid_index(row, column)
            b = grid_index(row, column + 1)
            c = grid_index(row + 1, column)
            d = grid_index(row + 1, column + 1)
            if (row + column + piece_index) % 2:
                triangles = ((a, b, d), (a, d, c))
            else:
                triangles = ((a, b, c), (b, d, c))
            for triangle in triangles:
                _append_face(faces, material_indices, smooth_flags, orient_top(triangle), 0, True)
                _append_face(
                    faces,
                    material_indices,
                    smooth_flags,
                    tuple(top_vertex_count + index for index in reversed(orient_top(triangle))),
                    1,
                )

    # Nonperiodic fracture displacement avoids a repeated folded-curtain pattern.
    # Every perimeter column shares intermediate vertices with its neighbours,
    # keeping the closed shell manifold while allowing real small undercuts.
    boundary = _boundary_ring(row_count, column_count, side)
    levels = 24
    rings = {}
    for top_index in boundary:
        x,y,z = vertices[top_index]
        col = top_index % column_count
        ids = [top_vertex_count + top_index]
        for k in range(1,levels):
            a = k / levels
            warp = sin(pi*a)
            p=Vector((y*.91, (base_z+(z-base_z)*a)*1.37, side*7.13))
            coarse=noise.noise_vector(p, noise_basis='PERLIN_ORIGINAL')
            fine=noise.noise_vector(p*3.7+Vector((2.1,7.4,3.8)), noise_basis='PERLIN_ORIGINAL')
            dx=side*warp*(.22*coarse.x+.035*fine.x) if col==0 else 0
            dy=warp*(.045*coarse.y+.012*fine.y) if col==0 else 0
            ids.append(len(vertices));vertices.append((x+dx,y+dy,base_z+(z-base_z)*a))
        ids.append(top_index);rings[top_index]=ids
    for pos,top_a in enumerate(boundary):
        top_b=boundary[(pos+1)%len(boundary)]
        inner=(top_a%column_count==0 and top_b%column_count==0)
        for k in range(levels):
            _append_face(faces,material_indices,smooth_flags,
                (rings[top_a][k+1],rings[top_a][k],rings[top_b][k],rings[top_b][k+1]),1,inner)

    mesh = bpy.data.meshes.new(f'{name}_Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    mesh.materials.append(materials['glaze'])
    mesh.materials.append(materials['fracture'])
    mesh.materials.append(materials['gold'])  # Reserved for caller-owned gold work.
    for polygon, material_index, smooth in zip(mesh.polygons, material_indices, smooth_flags):
        polygon.material_index = material_index
        polygon.use_smooth = smooth

    obj = bpy.data.objects.new(name, mesh)
    _link_to_active_collection(obj)
    _add_bevel_and_normals(obj, rng.uniform(0.05, 0.12))
    obj.modifiers['Porcelain weighted normals'].show_render = False
    obj['bank_side'] = 'left' if side < 0 else 'right'
    obj['piece_index'] = piece_index
    obj['low_ledge'] = low_ledge
    obj['top_grid_rows'] = row_count
    obj['top_grid_columns'] = column_count
    obj['top_grid_vertex_count'] = top_vertex_count
    return obj


def _link_to_active_collection(obj: bpy.types.Object) -> None:
    collection = bpy.context.collection or bpy.context.scene.collection
    collection.objects.link(obj)


def _add_bevel_and_normals(obj: bpy.types.Object, width: float) -> None:
    bevel = obj.modifiers.new('Rounded fired-glaze edges', 'BEVEL')
    bevel.width = width
    bevel.segments = 3
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = radians(28.0)
    bevel.harden_normals = True
    bevel.use_clamp_overlap = True

    weighted = obj.modifiers.new('Porcelain weighted normals', 'WEIGHTED_NORMAL')
    weighted.keep_sharp = True
    weighted.weight = 50


def build_banks(materials: Mapping[str, bpy.types.Material]) -> list[bpy.types.Object]:
    """Create nine distinct, closed porcelain slabs on each side of the crack."""
    objects: list[bpy.types.Object] = []
    for side, label, seed in ((-1, 'L', 271), (1, 'R', 619)):
        rng = Random(seed)
        boundaries = _piece_boundaries(rng, PIECES_PER_BANK)
        boundary_gaps = [rng.uniform(0.015, 0.05) for _ in range(PIECES_PER_BANK + 1)]
        ledge_count = 1 if side < 0 else 2
        low_ledge_indices = set(rng.sample(range(1, PIECES_PER_BANK - 1), ledge_count))
        for piece_index in range(PIECES_PER_BANK):
            piece_rng = Random(rng.randrange(0, 2**31))
            obj = _add_bank_piece(
                f'PorcelainBank_{label}_{piece_index + 1:02d}',
                side,
                boundaries[piece_index],
                boundaries[piece_index + 1],
                piece_index,
                boundary_gaps[piece_index],
                boundary_gaps[piece_index + 1],
                piece_index,
                piece_index in low_ledge_indices,
                materials,
                piece_rng,
            )
            objects.append(obj)
    return objects


def create_shard(
    name: str,
    materials: Mapping[str, bpy.types.Material],
    size: float = 0.4,
    seed: int = 1,
) -> bpy.types.Object:
    """Create one irregular, thick, beveled porcelain shard at the origin."""
    rng = Random(seed)
    vertex_count = rng.randint(5, 7)
    phase = rng.uniform(-0.16, 0.16)
    radii = [size * 0.5 * rng.uniform(0.76, 1.08) for _ in range(vertex_count)]
    thickness = size * rng.uniform(0.08, 0.18)
    half_thickness = thickness * 0.5

    top_ring: list[tuple[float, float, float]] = []
    for index, radius in enumerate(radii):
        angle = phase + tau * index / vertex_count
        top_ring.append((radius * cos(angle), radius * sin(angle), half_thickness))
    bottom_ring = [(x, y, -half_thickness) for x, y, _z in top_ring]
    top_center = (0.0, 0.0, half_thickness)
    bottom_center = (0.0, 0.0, -half_thickness)
    vertices = top_ring + bottom_ring + [top_center, bottom_center]
    top_center_index = vertex_count * 2
    bottom_center_index = top_center_index + 1

    faces: list[tuple[int, ...]] = []
    material_indices: list[int] = []
    smooth_flags: list[bool] = []
    for index in range(vertex_count):
        next_index = (index + 1) % vertex_count
        _append_face(
            faces,
            material_indices,
            smooth_flags,
            (top_center_index, index, next_index),
            0,
        )
        _append_face(
            faces,
            material_indices,
            smooth_flags,
            (bottom_center_index, vertex_count + next_index, vertex_count + index),
            1,
        )
        _append_face(
            faces,
            material_indices,
            smooth_flags,
            (index, vertex_count + index, vertex_count + next_index, next_index),
            1,
        )

    mesh = bpy.data.meshes.new(f'{name}_Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    mesh.materials.append(materials['glaze'])
    mesh.materials.append(materials['fracture'])
    mesh.materials.append(materials['gold'])  # Reserved for caller-owned gold work.
    for polygon, material_index in zip(mesh.polygons, material_indices):
        polygon.material_index = material_index
        polygon.use_smooth = False

    obj = bpy.data.objects.new(name, mesh)
    _link_to_active_collection(obj)
    _add_bevel_and_normals(obj, min(size * 0.045, thickness * 0.28))
    obj['porcelain_shard_size'] = size
    obj['porcelain_shard_thickness'] = thickness
    obj['porcelain_shard_seed'] = seed
    return obj
