"""EP11 v03: a fractured porcelain sheet that can actually fit back together.

Blender 4.5, no add-ons or external textures. All animation is saved as native
keyframes. Frame 1 maps to film frame 550; 1525 frames at 30 fps map exactly to
the 3050-frame canyon interval of the 60 fps Remotion composition.
"""
from __future__ import annotations
import argparse, json, math, random, sys, time
from pathlib import Path
import bpy, bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

N=1525
FPS=30
ROOT=Path(__file__).resolve().parent

def smooth(v):
    v=max(0.,min(1.,v));return v*v*(3-2*v)

def mix(a,b,t):return a+(b-a)*t

def ztop(x,y):return 1.72+.034*x*x+.005*y*y+.09*math.sin(y*.48)+.022*math.sin(x*1.8+y*.9)

def cx(y):
    # Interpolated chisel points, shared by both banks, never independently made.
    knots=[(-12+i*.25, .24*math.sin(i*.25*.77)+.14*math.sin(i*.25*2.13)+.032*math.sin(i*2.19)) for i in range(113)]
    for (a,x),(b,u) in zip(knots,knots[1:]):
        if y<=b:return mix(x,u,max(0.,(y-a)/(b-a)))
    return knots[-1][1]

def mat(name,color,rough=.3,metal=0):
    m=bpy.data.materials.new(name);m.use_nodes=True
    n=m.node_tree.nodes.get('Principled BSDF')
    n.inputs['Base Color'].default_value=(*color,1)
    n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal
    return m,n

def materials():
    glaze,p=mat('Fired ivory porcelain / clear glaze',(.69,.76,.75),.2)
    p.inputs['IOR'].default_value=1.48;p.inputs['Coat Weight'].default_value=.4
    p.inputs['Coat Roughness'].default_value=.13
    nt=glaze.node_tree;noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=42
    bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.055;bump.inputs['Distance'].default_value=.007
    nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    vor=nt.nodes.new('ShaderNodeTexVoronoi');vor.feature='DISTANCE_TO_EDGE';vor.inputs['Scale'].default_value=24
    ramp=nt.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.0009
    ramp.color_ramp.elements[0].color=(.49,.56,.55,1);ramp.color_ramp.elements[1].position=.004
    ramp.color_ramp.elements[1].color=(.69,.76,.75,1)
    nt.links.new(vor.outputs['Distance'],ramp.inputs[0]);nt.links.new(ramp.outputs['Color'],p.inputs['Base Color'])
    core,p=mat('Angular bisque fracture / unglazed core',(.38,.39,.33),.65)
    nt=core.node_tree;noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=68;noise.inputs['Detail'].default_value=3
    bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.3;bump.inputs['Distance'].default_value=.019
    nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    gold,p=mat('Gold / seated repair alloy',(.93,.49,.105),.22,1)
    p.inputs['Coat Weight'].default_value=.15
    dark,p=mat('Obsidian studio',(.008,.018,.022),.67)
    ink,p=mat('Dark fired crack edges',(.025,.038,.038),.5)
    return dict(glaze=glaze,core=core,gold=gold,dark=dark,ink=ink)

def solid(name,xy,mats,thickness=1.42):
    # Polygon top and bottom are separately triangulated. Shared boundary values
    # make every shard's rest surface coincide with its parent socket.
    xy=list(xy)
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(xy,xy[1:]+xy[:1]))
    if area<0:xy.reverse()
    v=[(x,y,ztop(x,y)) for x,y in xy]+[(x,y,ztop(x,y)-thickness) for x,y in xy]
    size=len(xy);flat=[Vector((x,y,0)) for x,y in xy]
    ids={tuple(p):i for i,p in enumerate(flat)}
    tris=tessellate_polygon([flat]);faces=[];indices=[]
    for t in tris:
        ix=tuple(p if isinstance(p,int) else ids[tuple(p)] for p in t);faces.append(ix);indices.append(0)
        faces.append(tuple(i+size for i in reversed(ix)));indices.append(1)
    for i in range(size):faces.append((i,(i+1)%size,(i+1)%size+size,i+size));indices.append(1)
    me=bpy.data.meshes.new(name);me.from_pydata(v,[],faces);me.update()
    obj=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(obj)
    me.materials.append(mats['glaze']);me.materials.append(mats['core'])
    for f,k in zip(me.polygons,indices):f.material_index=k
    bm=bmesh.new();bm.from_mesh(me)
    # Curvature must be sampled across the wide glaze surfaces, rather than
    # reading as the planar triangles of a low-poly CAD object.
    top_edges=[e for e in bm.edges if any(f.material_index==0 for f in e.link_faces)]
    bmesh.ops.subdivide_edges(bm,edges=top_edges,cuts=10,use_grid_fill=True)
    for vtx in bm.verts:
        if any(f.material_index==0 for f in vtx.link_faces):vtx.co.z=ztop(vtx.co.x,vtx.co.y)
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
    for f in me.polygons:
        if f.material_index==0:f.use_smooth=True
    bevel=obj.modifiers.new('Glaze catches a thin rim light','BEVEL');bevel.width=.022;bevel.segments=3
    bevel.affect='EDGES';bevel.limit_method='ANGLE';bevel.angle_limit=.28
    # Smooth glaze only; the exposed core keeps its sharp fracture normal.
    return obj

def curve(name,points,material,radius=.022):
    d=bpy.data.curves.new(name,'CURVE');d.dimensions='3D';d.resolution_u=12
    d.bevel_depth=radius;d.bevel_resolution=3
    s=d.splines.new('POLY');s.points.add(len(points)-1)
    for p,co in zip(s.points,points):p.co=(*co,1)
    ob=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(ob);d.materials.append(material)
    return ob

def seated_gold_geometry(obj):
    """Native geometry nodes: the river rests on the floor, then joins the lip.

    One keyed spatial front lifts the metal only as the porcelain closes. The
    line never hangs as an unrelated cord in the empty canyon.
    """
    tree=bpy.data.node_groups.new('Gold follows the closing fracture','GeometryNodeTree')
    tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    ns=tree.nodes;ls=tree.links
    gi=ns.new('NodeGroupInput');go=ns.new('NodeGroupOutput')
    pos=ns.new('GeometryNodeInputPosition');xyz=ns.new('ShaderNodeSeparateXYZ');ls.new(pos.outputs['Position'],xyz.inputs[0])
    front=ns.new('ShaderNodeValue');front.name='Closure front Y'
    def math_node(op,left=None,right=None):
        n=ns.new('ShaderNodeMath');n.operation=op
        for index,value in enumerate((left,right)):
            if value is None:continue
            if isinstance(value,(float,int)):n.inputs[index].default_value=value
            else:ls.new(value,n.inputs[index])
        return n.outputs[0]
    v=math_node('SUBTRACT',front.outputs[0],xyz.outputs['Y'])
    v=math_node('ADD',v,1.6);v=math_node('DIVIDE',v,3.2)
    v=math_node('MAXIMUM',v,0);v=math_node('MINIMUM',v,1)
    r=math_node('MULTIPLY',math_node('MULTIPLY',v,v),math_node('SUBTRACT',3,math_node('MULTIPLY',2,v)))
    delta=math_node('MULTIPLY',math_node('SUBTRACT',1,r),math_node('SUBTRACT',-.125,xyz.outputs['Z']))
    vec=ns.new('ShaderNodeCombineXYZ');ls.new(delta,vec.inputs['Z'])
    move=ns.new('GeometryNodeSetPosition');ls.new(gi.outputs['Geometry'],move.inputs['Geometry']);ls.new(vec.outputs[0],move.inputs['Offset']);ls.new(move.outputs['Geometry'],go.inputs['Geometry'])
    modifier=obj.modifiers.new('Seat gold on floor and repaired lips','NODES');modifier.node_group=tree
    return front.outputs[0]

def point(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

def light(name,pos,target,energy,color,size,sy):
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.color=color;d.shape='RECTANGLE';d.size=size;d.size_y=sy
    ob=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(ob);ob.location=pos;point(ob,target);return ob

def animate(obj,frame,loc=None,rot=None,scale=None):
    if loc is not None:obj.location=loc;obj.keyframe_insert('location',frame=frame)
    if rot is not None:obj.rotation_euler=rot;obj.keyframe_insert('rotation_euler',frame=frame)
    if scale is not None:obj.scale=scale;obj.keyframe_insert('scale',frame=frame)

def repair_front(t):
    # Freeze at film47s, gold reaches the keystone at film49s. One spatial clock
    # drives the bead, line reveal and delayed closure behind it.
    return max(-12.,min(16.,-12.+6.*(t-37.833333333333)))

def repair(y,t):
    # Banks close behind the gold after the returning shard has cleared the lip.
    return smooth((repair_front(t-2.8)-y+1.6)/3.2)

def bank_offset(side,y,t):
    open_amount=1.5+.16*math.sin(y*.52)
    spread=.10*smooth((t-13)/3)*(1-smooth((t-24)/3))
    return side*((open_amount+spread)*(1-repair(y,t))+.022*repair(y,t))

def build_geometry(mats):
    pieces=[];seams=[]
    # Common transverse breaks are diagonals across a single original sheet.
    cuts=[-12,-8.9,-5.6,-2.2,1.9,5.0,8.3,11.6,16]
    for side in [-1,1]:
        for j,(lo,hi) in enumerate(zip(cuts,cuts[1:])):
            ys=[lo+(hi-lo)*k/20 for k in range(21)]
            inner=[(cx(y),y) for y in ys]
            # Extract a V-shaped keystone from the right bank, with the same
            # shared side-wall vertices. No Boolean tolerance or fake matching.
            if side==1 and j==3:
                a=(cx(-1.5),-1.5);b=(cx(.8),.8)
                socket=[a,(.58,-1.09),(1.18,-.38),(1.40,.03),(.97,.43),b]
                inner=[(cx(y),y) for y in ys if y<-1.5]+socket+[(cx(y),y) for y in ys if y>.8]
                hero_outline=[(cx(-1.5+k*2.3/12),-1.5+k*2.3/12) for k in range(13)]+list(reversed(socket[1:-1]))
                hero=solid('Keystone / actual socket fragment',hero_outline,mats)
                hero['rest_outline']=json.dumps(hero_outline);hero['parent']='Bank R03'
            outer=side*8.5
            # A common irregular transverse break is reused by both neighbours.
            # It must not read as a stack of equal, straight ceramic shelves.
            def transverse(y,index):
                pts=[]
                for k in range(19):
                    u=k/18;x=mix(cx(y),outer,u)
                    yy=y+.85*math.sin(index*2.6)*u+.22*math.sin(u*8+index)*math.sin(math.pi*u)
                    pts.append((x,yy))
                return pts
            lower=transverse(lo,j);upper=transverse(hi,j+1)
            poly=inner+upper[1:]+list(reversed(lower[1:]))
            ob=solid(f'Bank {"R" if side==1 else "L"}{j:02}',poly,mats)
            ob['side']=side;ob['mid_y']=(lo+hi)/2;pieces.append(ob)
            if j>0:
                line=[(x,y,ztop(x,y)+.014) for x,y in lower]
                seam=curve('Gold transverse join '+ob.name,line,mats['gold'],.023);seams.append((seam,side,(lo+hi)/2))
    hero['socket_outline']=json.dumps(socket)
    # The outline is a curve in the exact parent coordinates and moves with it.
    socket_gold=curve('Gold socket / matching keystone edge',[(x,y,ztop(x,y)+.017) for x,y in socket],mats['gold'],.029)
    return pieces,seams,hero,socket_gold

def build(a):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc=bpy.context.scene;sc.render.engine=a.engine
    sc.render.resolution_x=a.width;sc.render.resolution_y=a.height;sc.render.resolution_percentage=100
    sc.render.fps=FPS;sc.frame_start=1;sc.frame_end=N
    sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGB';sc.render.image_settings.color_depth='8';sc.render.image_settings.compression=20
    # Deliberate crisp 30fps animation. Global camera motion blur blends poses
    # across hard edits in Eevee; depth of field supplies optical separation.
    sc.render.film_transparent=False;sc.render.use_motion_blur=False
    sc.render.threads_mode='FIXED';sc.render.threads=4
    sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=-.65
    if a.engine=='CYCLES':
        cp=bpy.context.preferences.addons['cycles'].preferences;cp.compute_device_type='METAL';cp.get_devices()
        for d in cp.devices:d.use=d.type=='METAL'
        assert any(d.use for d in cp.devices),'Metal unavailable'
        sc.cycles.device='GPU';sc.cycles.samples=a.samples;sc.cycles.use_denoising=True
        sc.cycles.adaptive_threshold=.07;sc.cycles.adaptive_min_samples=8;sc.cycles.max_bounces=6;sc.cycles.use_persistent_data=True
    else:
        sc.eevee.taa_render_samples=a.samples;sc.eevee.use_raytracing=True
        sc.eevee.ray_tracing_options.resolution_scale='2'
        sc.eevee.ray_tracing_options.screen_trace_quality=1
        sc.eevee.ray_tracing_options.screen_trace_thickness=.12
    world=bpy.data.worlds.new('Blue hour');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.11,.18,.22,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.22;sc.world=world
    mats=materials();pieces,seams,hero,socket_gold=build_geometry(mats)
    bpy.ops.mesh.primitive_plane_add(size=180,location=(0,0,-.18));bpy.context.object.name='Infinite ink base';bpy.context.object.data.materials.append(mats['dark'])
    # A continuous cove removes the finite plane's hard horizon behind the valley.
    vv=[]
    for j in range(33):
        angle=math.pi*.5*j/32;y=19+8*math.sin(angle);z=-.18+8*(1-math.cos(angle))
        vv.extend([(-70,y,z),(70,y,z)])
    vv.extend([(-70,27,60),(70,27,60)])
    me=bpy.data.meshes.new('Seamless ink cove');me.from_pydata(vv,[],[(2*j,2*j+1,2*j+3,2*j+2) for j in range(33)]);me.update()
    cove=bpy.data.objects.new('Seamless ink cove',me);bpy.context.collection.objects.link(cove);me.materials.append(mats['dark'])
    for face in me.polygons:face.use_smooth=True
    light('Long warm window',(-5,-1,8),(0,2,1),2200,(1,.91,.75),5,12)
    light('Cool reflection strip',(5,5,7),(0,2,1),1800,(.56,.8,1),4,10)
    light('Foreground porcelain softbox',(0,-7,5),(0,-1,1),650,(.85,.93,1),3,5)
    light('Distant gold backlight',(-2,14,6),(0,3,1),1600,(1,.63,.24),3,5)
    light('Gold reflection card',(-.5,1,9),(0,1,0),1200,(1,.95,.82),1,12)
    # Geometry is real, all gold lies on a closed join rather than a river below.
    main_gold=curve('Main kintsugi seam',[(cx(y),y,ztop(cx(y),y)+.027) for y in [-12+i*28/240 for i in range(241)]],mats['gold'],.037)
    closure_front=seated_gold_geometry(main_gold)
    focus=bpy.data.objects.new('Focus / action',None);bpy.context.collection.objects.link(focus)
    cd=bpy.data.cameras.new('Macro portrait camera');cam=bpy.data.objects.new('Macro portrait camera',cd);bpy.context.collection.objects.link(cam);sc.camera=cam
    cd.lens=42;cd.sensor_width=36;cd.clip_start=.05;cd.clip_end=200
    cd.dof.use_dof=True;cd.dof.focus_object=focus;cd.dof.aperture_fstop=4.5;cd.dof.aperture_blades=7
    rng=random.Random(1103);chips=[]
    for k in range(22):
        x=rng.uniform(-.5,.5);y=rng.uniform(-3,14);r=rng.uniform(.035,.12)
        ob=solid(f'Fine porcelain rain {k:02}',[(x-r,y-r),(x+r,y-r*.4),(x+.4*r,y+r)],mats,thickness=r*.55)
        anchor=Vector((x,y,ztop(x,y)))
        for vert in ob.data.vertices:vert.co-=anchor
        chips.append((ob,anchor,1 if x>=0 else -1,rng.uniform(.2,1.9),rng.random()*6.28))
    # Repair bead is an actual metallic object, seated at the moving fracture tip.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=.07)
    bead=bpy.context.object;bead.name='Advancing gold meniscus';bead.data.materials.append(mats['gold'])
    # Wrong routes briefly light, then recede. Fine 3D wires lie inside the valley.
    routes=[]
    for j in range(7):
        pts=[]
        for k in range(30):
            u=k/29;y=-4+u*(10+j*.7);x=cx(y)+math.sin(u*3.14)*(j-3)*.25
            pts.append((x,y,.28+.12*math.sin(u*8+j)))
        ob=curve(f'Explored narrow route {j:02}',pts,mats['gold'],.009 if j!=3 else .022);routes.append(ob)
    # Native animation, no frame handlers or hidden runtime dependencies.
    for f in range(1,N+1):
        t=(f-1)/FPS
        for ob in pieces:
            side=ob['side'];y=ob['mid_y'];dx=bank_offset(side,y,t)
            animate(ob,f,(dx,0,0))
        for ob,side,y in seams:
            r=repair(y,t);animate(ob,f,(bank_offset(side,y,t),0,0),scale=(1,1,1))
            ob.hide_render=r<.97;ob.keyframe_insert('hide_render',frame=f)
        # A small descent, then a clearly held beat, then exact return to parent.
        fall=smooth((t-36.833333333333)/1.0);rise=smooth((t-39.833333333333)/3.166666666667)
        parent=bank_offset(1,-.15,t)
        dy=.12*fall*(1-rise);dz=-.82*fall*(1-rise)
        animate(hero,f,(parent-.35*fall*(1-rise),dy,dz),(.26*fall*(1-rise),-.44*fall*(1-rise),-.15*fall*(1-rise)))
        r=repair(-.15,t);animate(socket_gold,f,(parent,0,0),scale=(1,1,1))
        socket_gold.hide_render=rise<.97;socket_gold.keyframe_insert('hide_render',frame=f)
        front=repair_front(t);main_gold.data.bevel_factor_end=max(.00001,(front+12)/28)
        main_gold.data.keyframe_insert('bevel_factor_end',frame=f)
        closure_front.default_value=repair_front(t-2.8);closure_front.keyframe_insert('default_value',frame=f)
        animate(bead,f,(cx(front),front,-.09),scale=(1,1,max(.001,smooth((t-37.833333333333)/.3)*(1-smooth((t-42.5)/.5)))))
        for j,ob in enumerate(routes):
            vis=smooth((t-25-j*.45)/1.2)*(1-smooth((t-33-j*.25)/1.7))
            animate(ob,f,scale=(1,1,max(.001,vis)))
            ob.hide_render=vis<.01;ob.keyframe_insert('hide_render',frame=f)
        for k,(ob,anchor,side,drop,phase) in enumerate(chips):
            # The entire rain reverses, leaving no tiles hovering in the result.
            d=smooth((t-36.4-k*.012)/1.4)*(1-smooth((t-40-k*.025)/3.6))
            dx=bank_offset(side,anchor.y,t)
            animate(ob,f,(anchor.x+dx*(1-.70*d)+.07*math.sin(phase)*d,anchor.y,anchor.z-drop*d),(.4*d*math.sin(phase),.5*d,.2*d))
            ob.hide_render=t<35.8 or t>44.2;ob.keyframe_insert('hide_render',frame=f)
        # Each shot has a distinct action and continuous spatial movement.
        if t<12.8333:
            u=t/12.8333;pos=(mix(-.35,.4,u),mix(-8,-5.1,u),mix(6.0,4.8,u));target=(0,mix(1,3,u),1.1);lens=42
        elif t<25.8333:
            u=(t-12.8333)/13;pos=(mix(-1.2,.5,u),mix(-4.8,-2.4,u),mix(3.7,4.4,u));target=(0,3.5,1.1);lens=43
        elif t<37.6667:
            u=(t-25.8333)/11.8334;pos=(mix(2.0,.5,u),mix(-5.0,-3.8,u),mix(7.2,5.7,u));target=(0,3,1.0);lens=40
        elif t<45.4:
            u=(t-37.6667)/7.7333;pos=(mix(-.25,.45,u),mix(-5.0,-5.3,u),mix(5.2,5.9,u));target=(mix(1.0,.60,u),-.55,mix(1.05,1.7,u));lens=40
        else:
            u=(t-45.4)/(50.8333-45.4);pos=(mix(.45,0,u),mix(-4.7,-5.5,u),mix(5.5,11,u));target=(0,1.5,1.7);lens=mix(46,36,u)
        animate(cam,f,pos);point(cam,target);cam.keyframe_insert('rotation_euler',frame=f)
        cd.lens=lens;cd.keyframe_insert('lens',frame=f)
        if 1132<=f<1363:
            anchor=Vector((.58,-.30,ztop(.58,-.30)))
            focus.location=hero.rotation_euler.to_matrix()@anchor+hero.location
            cd.dof.aperture_fstop=8.0
        else:
            focus.location=target;cd.dof.aperture_fstop=4.5
        focus.keyframe_insert('location',frame=f);cd.dof.keyframe_insert('aperture_fstop',frame=f)
    for dat in [*sc.objects,*bpy.data.curves,cd]:
        if dat.animation_data and dat.animation_data.action:
            for fc in dat.animation_data.action.fcurves:
                if fc.data_path=='hide_render':continue
                for k in fc.keyframe_points:k.interpolation='LINEAR'
    checks=[]
    for ob in [*pieces,hero]:
        bm=bmesh.new();bm.from_mesh(ob.data);bad=sum(not e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);bm.free()
        assert bad==0 and volume>0,(ob.name,bad,volume)
        checks.append(dict(name=ob.name,non_manifold_edges=bad,volume=volume))
    sc['geometry_checks_json']=json.dumps(checks);sc['film_frame_start']=550;sc['source_fps']=30
    sc['description']='Matched original sheet fragments, native keyframes; gold reveal is art-directed geometry, not a fluid simulation.'
    sc.frame_set(1)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.save).resolve()))
    return sc

def main():
    p=argparse.ArgumentParser();p.add_argument('--engine',default='BLENDER_EEVEE_NEXT',choices=['BLENDER_EEVEE_NEXT','CYCLES'])
    p.add_argument('--width',type=int,default=540);p.add_argument('--height',type=int,default=960)
    p.add_argument('--samples',type=int,default=32);p.add_argument('--frames',default='1160,1260,1400')
    p.add_argument('--out',required=True);p.add_argument('--save')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    sc=build(a);rows=[]
    for f in map(int,a.frames.split(',')):
        assert 1<=f<=N
        sc.frame_set(f);sc.render.filepath=str(out/f'frame-{f:04}.png');start=time.monotonic();bpy.ops.render.render(write_still=True)
        rows.append(dict(frame=f,seconds=time.monotonic()-start,path=sc.render.filepath))
    (out/'render-times.json').write_text(json.dumps(rows,indent=2)+'\n')

if __name__=='__main__':main()
