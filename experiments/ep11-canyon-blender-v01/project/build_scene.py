"""Blender 4.5 porcelain fissure study. Original geometry, no downloaded assets."""
from __future__ import annotations
import argparse, json, math, random, sys, time
from pathlib import Path
import bpy, bmesh
from mathutils import Vector

HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path: sys.path.insert(0,str(HERE))
from geometry import build_banks, create_shard, center_x


def args():
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True)
    p.add_argument('--frames',default='96')
    p.add_argument('--width',type=int,default=540)
    p.add_argument('--height',type=int,default=960)
    p.add_argument('--samples',type=int,default=32)
    p.add_argument('--save',action='store_true')
    p.add_argument('--blend-out')
    return p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])


def node(nt,kind,name=None):
    n=nt.nodes.new(kind)
    if name:n.name=name;n.label=name
    return n


def base_material(name,color,roughness,metallic=0):
    m=bpy.data.materials.new(name);m.use_nodes=True
    nt=m.node_tree;nt.nodes.clear()
    out=node(nt,'ShaderNodeOutputMaterial');bs=node(nt,'ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Roughness'].default_value=roughness
    bs.inputs['Metallic'].default_value=metallic
    nt.links.new(bs.outputs['BSDF'],out.inputs['Surface'])
    return m,nt,bs


def materials():
    glaze,nt,bs=base_material('Ivory porcelain / clear glaze',(.72,.78,.77),.20)
    bs.inputs['IOR'].default_value=1.48
    bs.inputs['Coat Weight'].default_value=.30
    bs.inputs['Coat Roughness'].default_value=.12
    bs.inputs['Subsurface Weight'].default_value=.035
    bs.inputs['Subsurface Radius'].default_value=(.16,.08,.04)
    tex=node(nt,'ShaderNodeTexNoise','Glaze microvariation');tex.inputs['Scale'].default_value=29
    tex.inputs['Detail'].default_value=3;tex.inputs['Roughness'].default_value=.6
    ramp=node(nt,'ShaderNodeValToRGB','Subtle glaze roughness')
    ramp.color_ramp.elements[0].color=(.13,.13,.13,1);ramp.color_ramp.elements[1].color=(.27,.27,.27,1)
    nt.links.new(tex.outputs['Fac'],ramp.inputs[0]);nt.links.new(ramp.outputs['Color'],bs.inputs['Roughness'])
    vor=node(nt,'ShaderNodeTexVoronoi','Faint fired-glaze crazing');vor.feature='DISTANCE_TO_EDGE';vor.inputs['Scale'].default_value=55
    edge=node(nt,'ShaderNodeValToRGB');edge.color_ramp.elements[0].position=.002;edge.color_ramp.elements[0].color=(.16,.16,.16,1)
    edge.color_ramp.elements[1].position=.013;edge.color_ramp.elements[1].color=(.8,.8,.8,1)
    nt.links.new(vor.outputs['Distance'],edge.inputs[0])
    crazing=node(nt,'ShaderNodeValToRGB','Delicate fired glaze crackle')
    crazing.color_ramp.elements[0].position=.0015;crazing.color_ramp.elements[0].color=(.26,.31,.29,1)
    crazing.color_ramp.elements[1].position=.006;crazing.color_ramp.elements[1].color=(.72,.78,.77,1)
    nt.links.new(vor.outputs['Distance'],crazing.inputs[0]);nt.links.new(crazing.outputs['Color'],bs.inputs['Base Color'])
    bump=node(nt,'ShaderNodeBump');bump.inputs['Strength'].default_value=.08;bump.inputs['Distance'].default_value=.004
    nt.links.new(edge.outputs['Color'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    fracture,nt,bs=base_material('Warm bisque / broken porcelain core',(.60,.55,.46),.65)
    bs.inputs['Subsurface Weight'].default_value=.025
    noise=node(nt,'ShaderNodeTexNoise');noise.inputs['Scale'].default_value=32;noise.inputs['Detail'].default_value=4
    bump=node(nt,'ShaderNodeBump');bump.inputs['Strength'].default_value=.28;bump.inputs['Distance'].default_value=.028
    nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    gold,nt,bs=base_material('Gold / physical conductor',(.83,.42,.075),.23,1)
    noise=node(nt,'ShaderNodeTexNoise','Slow liquid surface');noise.noise_dimensions='4D';noise.inputs['Scale'].default_value=7;noise.inputs['Detail'].default_value=3
    noise.inputs['W'].default_value=0;noise.inputs['W'].keyframe_insert('default_value',frame=1)
    noise.inputs['W'].default_value=.42;noise.inputs['W'].keyframe_insert('default_value',frame=192)
    bump=node(nt,'ShaderNodeBump');bump.inputs['Strength'].default_value=.17;bump.inputs['Distance'].default_value=.022
    nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    floor,nt,bs=base_material('Deep teal porcelain under the fracture',(.018,.035,.04),.45,0)
    noise=node(nt,'ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1.7;noise.inputs['Detail'].default_value=3
    bump=node(nt,'ShaderNodeBump');bump.inputs['Strength'].default_value=.13;bump.inputs['Distance'].default_value=.06
    nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    return dict(glaze=glaze,fracture=fracture,gold=gold,floor=floor)


def point_at(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()


def area(name,location,target,energy,color,size,size_y=None):
    data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.color=color
    data.shape='RECTANGLE';data.size=size;data.size_y=size if size_y is None else size_y
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.location=location;point_at(obj,target)
    return obj


def curve(name,coords,mat,radius):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=16
    c.bevel_depth=radius;c.bevel_resolution=4
    s=c.splines.new('POLY');s.points.add(len(coords)-1)
    for p,co in zip(s.points,coords):p.co=(*co,1)
    obj=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(obj);obj.data.materials.append(mat)
    return obj


def gold_pool(mat):
    # Rounded meniscus with narrow uneven banks; physical conductor reflects the studio.
    verts=[];faces=[];ny=200;nx=14
    for j in range(ny):
        y=-11+31*j/(ny-1);c=center_x(y);w=.11+.045*math.sin(y*.7)+.025*math.sin(y*2.6)
        for i in range(nx):
            u=-1+2*i/(nx-1);x=c+u*w
            z=.055+.045*(1-u*u)+.009*math.sin(y*3.2+u*4)
            verts.append((x,y,z))
    for j in range(ny-1):
        for i in range(nx-1):
            a=j*nx+i;faces.append((a,a+1,a+nx+1,a+nx))
    mesh=bpy.data.meshes.new('Gold meniscus mesh');mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new('A narrow pool of real gold',mesh);bpy.context.collection.objects.link(obj)
    for p in mesh.polygons:p.use_smooth=True
    # Reveal the metal with a spatially advancing, soft front. Position/reflectance,
    # not an emissive plane, defines the liquid surface.
    m=mat.copy();m.name='Gold pool / advancing repair front';nt=m.node_tree
    out=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL');gold=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
    unfilled=node(nt,'ShaderNodeBsdfPrincipled','Empty dark fissure');unfilled.inputs['Base Color'].default_value=(.012,.025,.026,1);unfilled.inputs['Roughness'].default_value=.5
    geo=node(nt,'ShaderNodeNewGeometry');sep=node(nt,'ShaderNodeSeparateXYZ');nt.links.new(geo.outputs['Position'],sep.inputs[0])
    front=node(nt,'ShaderNodeValue','Repair front Y');front.outputs[0].default_value=-11;front.outputs[0].keyframe_insert('default_value',frame=1)
    front.outputs[0].keyframe_insert('default_value',frame=72);front.outputs[0].default_value=19;front.outputs[0].keyframe_insert('default_value',frame=192)
    delta=node(nt,'ShaderNodeMath');delta.operation='SUBTRACT';nt.links.new(front.outputs[0],delta.inputs[0]);nt.links.new(sep.outputs['Y'],delta.inputs[1])
    mr=node(nt,'ShaderNodeMapRange');mr.inputs['From Min'].default_value=-.25;mr.inputs['From Max'].default_value=.25;mr.clamp=True;nt.links.new(delta.outputs[0],mr.inputs['Value'])
    mix=node(nt,'ShaderNodeMixShader');nt.links.new(mr.outputs['Result'],mix.inputs[0]);nt.links.new(unfilled.outputs['BSDF'],mix.inputs[1]);nt.links.new(gold.outputs['BSDF'],mix.inputs[2]);nt.links.new(mix.outputs[0],out.inputs['Surface'])
    obj.data.materials.append(m)
    if nt.animation_data and nt.animation_data.action:
        for fc in nt.animation_data.action.fcurves:
            for kp in fc.keyframe_points:kp.interpolation='LINEAR'
    return obj


def animate_shards(mats):
    rng=random.Random(1163)
    hero=create_shard('The shard that stops time',mats,size=.62,seed=11)
    ring_count=(len(hero.data.vertices)-2)//2
    for idx in (1,ring_count+1):
        hero.data.vertices[idx].co.x*=.38;hero.data.vertices[idx].co.y*=.38
    for vert in hero.data.vertices:
        vert.co.z += .65*(vert.co.x*vert.co.x+vert.co.y*vert.co.y)
    for face in hero.data.polygons:
        if face.material_index==0:face.use_smooth=True
    bpy.context.view_layer.update()
    # The shard carries its actual glaze and fracture edge, without an icon-like
    # decorative zigzag. Gold belongs to the broken joins in the parent banks.
    focus=bpy.data.objects.new('Focus / stopped shard',None);bpy.context.collection.objects.link(focus)
    chips=[]
    for i in range(18):
        y=rng.uniform(.0,16);x=center_x(y)+rng.uniform(-.52,.52)
        obj=create_shard(f'Porcelain rain {i:02d}',mats,size=rng.uniform(.065,.19),seed=500+i)
        chips.append((obj,x,y,rng.uniform(.8,3.3),rng.uniform(.12,.24),3+((y+7)/24)*4.5,rng.uniform(-2,2)))
    # Native keyed animation, fully reopenable without Python handlers.
    for frame in range(1,193):
        t=(frame-1)/24
        if t<1:z=1.78-.42*t
        elif t<3:z=1.36
        else:z=1.36+.085*(t-3)**2
        y=-1.2+.025*max(t-3,0)**2
        hero.location=(center_x(y)-.07,y,z)
        if t<1:spin=t
        elif t<3:spin=1
        else:spin=1+.10*(t-3)**2
        hero.rotation_euler=(math.radians(61)+.13*spin,.20*spin,math.radians(-18)+.22*spin)
        hero.keyframe_insert('location',frame=frame);hero.keyframe_insert('rotation_euler',frame=frame)
        focus.location=hero.location;focus.keyframe_insert('location',frame=frame)
        for obj,x,y,z0,v,tc,phase in chips:
            dt=max(t-tc,0);obj.location=(x+.025*math.sin(t+phase),y,z0-v*t+.12*dt*dt)
            obj.rotation_euler=(phase+t*.3,phase*.4+t*.19,phase+t*.23)
            obj.keyframe_insert('location',frame=frame);obj.keyframe_insert('rotation_euler',frame=frame)
    for ob in [hero,focus,*[x[0] for x in chips]]:
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                for kp in fc.keyframe_points:kp.interpolation='LINEAR'
    return hero,focus


def setup(a):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.render.engine='CYCLES'
    cp=bpy.context.preferences.addons['cycles'].preferences;cp.compute_device_type='METAL';cp.get_devices()
    for dev in cp.devices:dev.use=dev.type=='METAL'
    assert any(d.use for d in cp.devices),'No Metal device available'
    scene.cycles.device='GPU';scene.cycles.samples=a.samples;scene.cycles.use_denoising=True
    scene.cycles.denoiser='OPENIMAGEDENOISE';scene.cycles.adaptive_threshold=.06;scene.cycles.adaptive_min_samples=8
    scene.cycles.max_bounces=8;scene.cycles.diffuse_bounces=3;scene.cycles.glossy_bounces=4;scene.cycles.transmission_bounces=4;scene.cycles.volume_bounces=1
    scene.cycles.use_persistent_data=True
    scene.render.resolution_x=a.width;scene.render.resolution_y=a.height;scene.render.resolution_percentage=100
    scene.render.fps=24;scene.frame_start=1;scene.frame_end=192
    scene.render.threads_mode='FIXED';scene.render.threads=4
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.color_depth='8';scene.render.image_settings.compression=30
    scene.render.film_transparent=False
    scene.render.use_motion_blur=True;scene.render.motion_blur_shutter=.35
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=-.65
    world=bpy.data.worlds.new('Blue hour studio');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.10,.15,.19,1);world.node_tree.nodes['Background'].inputs[1].default_value=.18;scene.world=world
    mats=materials();banks=build_banks(mats)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.045));floor=bpy.context.object;floor.name='Dark porcelain base';floor.data.materials.append(mats['floor'])
    # A seamless cyclorama removes the hard horizon of the temporary studio floor.
    coords=[]
    for j in range(33):
        theta=(math.pi/2)*j/32;y=17+8*math.sin(theta);z=-.045+8*(1-math.cos(theta));coords.extend([(-60,y,z),(60,y,z)])
    coords.extend([(-60,25,40),(60,25,40)])
    faces=[(2*j,2*j+1,2*j+3,2*j+2) for j in range(33)]
    me=bpy.data.meshes.new('Smooth studio cove');me.from_pydata(coords,[],faces);me.update()
    cove=bpy.data.objects.new('Seamless distant blue cove',me);bpy.context.collection.objects.link(cove);cove.data.materials.append(mats['floor'])
    for f in me.polygons:f.use_smooth=True
    pool=gold_pool(mats['gold']);mats['repair_gold']=pool.data.materials[0];hero,focus=animate_shards(mats)
    for ob in banks:
        if ob.get('piece_index',0) % 3 != 1:continue
        verts=ob.data.vertices;n=ob['top_grid_vertex_count'];cols=ob['top_grid_columns']
        edge=[tuple(v.co) for v in verts[n-cols:n]]
        edge=[(x,y+.012,z-.01) for x,y,z in edge]
        curve('Gold seated inside a broken join '+ob.name,edge,pool.data.materials[0],.022)
    area('Large warm softbox',(-5,1,5),(0,1,1),1250,(1,.91,.72),7,10)
    area('Soft reflection for the stopped shard',(0,-7,5),(0,-1,1.5),380,(.85,.93,1),4,4)
    area('Cool side reflection',(5,4,7),(0,3,1.8),650,(.64,.83,1),5,9)
    area('Warm edge at the far turn',(-1,14,7),(0,1,1),1900,(1,.69,.32),4,4)
    area('Long gold reflection card',(-.6,3,8),(0,2,0),1100,(1,.96,.87),1.4,9)
    # Bounded participating atmosphere, genuinely ray-traced by Cycles.
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,13,3));fog=bpy.context.object;fog.name='Restrained volume in the recesses';fog.scale=(20,16,7);fog.visible_glossy=False;fog.visible_diffuse=False
    fogmat=bpy.data.materials.new('Thin blue atmosphere');fogmat.use_nodes=True;nt=fogmat.node_tree;nt.nodes.clear();out=node(nt,'ShaderNodeOutputMaterial');v=node(nt,'ShaderNodeVolumePrincipled');v.inputs['Density'].default_value=.003;v.inputs['Color'].default_value=(.58,.72,.78,1);v.inputs['Anisotropy'].default_value=.25;nt.links.new(v.outputs['Volume'],out.inputs['Volume']);fog.data.materials.append(fogmat)
    camdata=bpy.data.cameras.new('Macro cinema camera');cam=bpy.data.objects.new('Macro cinema camera',camdata);bpy.context.collection.objects.link(cam);scene.camera=cam
    camdata.lens=45;camdata.sensor_width=36;camdata.clip_start=.05;camdata.clip_end=100
    camdata.dof.use_dof=True;camdata.dof.focus_object=focus;camdata.dof.aperture_fstop=3.2;camdata.dof.aperture_blades=7
    for f in range(1,193):
        t=(f-1)/191;y=-8.8+1.15*t;x=center_x(y)+.18-.27*t
        cam.location=(x,y,5.55+.12*t);point_at(cam,(center_x(.3),.3,1.0+.12*t));cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_euler',frame=f)
    if cam.animation_data:
        for fc in cam.animation_data.action.fcurves:
            for k in fc.keyframe_points:k.interpolation='LINEAR'
    geometry_checks=[]
    for ob in [*banks,hero,*[o for o in scene.objects if o.name.startswith('Porcelain rain')]]:
        bm=bmesh.new();bm.from_mesh(ob.data)
        bad=sum(not e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);bm.free()
        assert bad==0 and volume>0,(ob.name,bad,volume)
        geometry_checks.append({'name':ob.name,'non_manifold_edges':bad,'signed_volume':volume})
    scene['geometry_checks_json']=json.dumps(geometry_checks)
    scene['study']='EP11 porcelain canyon / material and motion experiment01'
    scene['sound_source']='v02 score+sfx46–54seconds, narration deliberately omitted'
    scene['original_assets']='Generated locally with Blender; no external meshes/textures/fonts required'
    return scene,banks


def main():
    a=args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    scene,banks=setup(a)
    if a.save:
        blend=Path(a.blend_out).resolve() if a.blend_out else out/'porcelain-canyon.blend'
        if blend.exists():raise RuntimeError(f'Refusing to replace {blend}')
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    frames=[]
    for part in a.frames.split(','):
        if '-' in part:
            lo,hi=map(int,part.split('-'));frames.extend(range(lo,hi+1))
        else:frames.append(int(part))
    report={'blender':bpy.app.version_string,'engine':scene.render.engine,'device':scene.cycles.device,'samples':scene.cycles.samples,'native_dimensions':[a.width,a.height],'fps':24,'frames':[],'bank_objects':len(banks),'total_objects':len(scene.objects),'motion_blur_shutter':scene.render.motion_blur_shutter,'dof_fstop':scene.camera.data.dof.aperture_fstop,'denoiser':scene.cycles.denoiser,'geometry_checks':json.loads(scene['geometry_checks_json'])}
    for f in frames:
        dst=out/f'{f:04d}.png'
        if dst.exists():raise RuntimeError(f'Refusing to replace {dst}')
        scene.frame_set(f);scene.render.filepath=str(dst);t=time.monotonic();bpy.ops.render.render(write_still=True)
        report['frames'].append({'frame':f,'seconds':(f-1)/24,'render_seconds':time.monotonic()-t,'path':dst.name})
        (out/'render-report.json').write_text(json.dumps(report,indent=2)+'\n')
        print('EP11_FRAME_DONE',f,report['frames'][-1]['render_seconds'],flush=True)

if __name__=='__main__':main()
