import React, {useMemo} from 'react';
import * as THREE from 'three';
import {authoredChoicePath,choicePotential,computeShieldRay,createGeodesicMesh,integrateChoicePath,seededUnit,smoothstep} from './math';
import {Floor,Tube} from './Stage';

const gold='#d6ab61';

export const Coffee:React.FC=()=>{
  const cup=useMemo(()=>new THREE.LatheGeometry([
    [0.04,.04],[.55,.04],[.61,.08],[.64,.15],[.69,.98],[.68,1.04],
    [.65,1.06],[.62,1.02],[.59,.24],[.54,.19],[.04,.19],
  ].map(([x,y])=>new THREE.Vector2(x,y)),96),[]);
  const saucer=useMemo(()=>new THREE.LatheGeometry([
    [.03,0],[.68,0],[1,.06],[1.08,.12],[1.08,.15],[1.01,.17],[.7,.08],[.03,.06],
  ].map(([x,y])=>new THREE.Vector2(x,y)),96),[]);
  const shadow=useMemo(()=>{
    const s=new THREE.Shape();s.moveTo(-2.4,-.32);s.bezierCurveTo(-1.6,-.3,-1.5,-.35,-1.1,-.29);
    s.bezierCurveTo(-.83,-.64,-.43,-.8,-.07,-.77);
    s.bezierCurveTo(.25,-.76,.23,-.61,.04,-.57);s.lineTo(-.35,-.48);
    s.bezierCurveTo(-.04,-.43,.43,-.42,.8,-.37);s.bezierCurveTo(1.04,-.33,.98,-.18,.77,-.18);s.lineTo(.08,-.17);
    s.lineTo(.9,-.07);s.bezierCurveTo(1.13,-.03,1.08,.12,.85,.12);s.lineTo(.06,.05);
    s.lineTo(.71,.25);s.bezierCurveTo(.92,.31,.81,.46,.62,.41);s.lineTo(-.02,.26);
    s.lineTo(.38,.49);s.bezierCurveTo(.54,.6,.42,.71,.26,.62);s.lineTo(-.47,.31);
    s.bezierCurveTo(-.76,.3,-.94,.22,-1.13,.13);s.lineTo(-2.4,.2);s.closePath();return new THREE.ShapeGeometry(s,32);
  },[]);
  const steam=useMemo(()=>Array.from({length:3},(_,i)=>Array.from({length:40},(_,j)=>{
    const t=j/39;return new THREE.Vector3(.06+Math.sin(t*6+i*1.9)*.13,.99+t*1.05,(i-1)*.1+Math.cos(t*5)*.07);
  })),[]);
  return <>
    <Floor y={-.32} color="#25282b"/>
    <group position={[1.2,-.27,-.2]} scale={1.55} rotation={[0,-.22,0]}>
      <mesh geometry={saucer} castShadow receiveShadow><meshPhysicalMaterial color="#e4ddd0" roughness={.24} clearcoat={.7} clearcoatRoughness={.18}/></mesh>
      <group position={[0,.1,0]}>
        <mesh geometry={cup} castShadow receiveShadow><meshPhysicalMaterial color="#e5ded1" roughness={.2} clearcoat={.8} clearcoatRoughness={.18}/></mesh>
        <mesh position={[.86,.59,0]} castShadow><torusGeometry args={[.36,.085,20,64]}/><meshPhysicalMaterial color="#e2dacd" roughness={.22} clearcoat={.8}/></mesh>
        <mesh position={[0,.96,0]}><cylinderGeometry args={[.627,.627,.012,96]}/><meshPhysicalMaterial color="#170a03" roughness={.32} clearcoat={.25} clearcoatRoughness={.12} envMapIntensity={.18}/></mesh>
        <mesh position={[0,1.045,0]} rotation={[Math.PI/2,0,0]}><torusGeometry args={[.65,.009,8,96]}/><meshStandardMaterial color="#f4ede0" roughness={.19}/></mesh>
        {steam.map((p,i)=><Tube key={i} points={p} radius={.008} color="#d6d6ca" opacity={.12} emission={0}/>)}
      </group>
    </group>
    {/* Explicit thought-experiment projection, not a measured neural signal. */}
    <mesh geometry={shadow} rotation={[-Math.PI/2,0,-.25]} position={[-.25,-.311,.85]} scale={1.12}>
      <meshBasicMaterial color="#5b9296" transparent opacity={.32} depthWrite={false}/>
    </mesh>
    <mesh rotation={[-Math.PI/2,0,0]} position={[1.1,-.306,-.1]}>
      <ringGeometry args={[1.72,1.735,128]}/><meshBasicMaterial color="#a4b0a9" transparent opacity={.24}/>
    </mesh>
  </>;
};

// A monotonic presentation transform compresses extreme toy-potential values.
// The underlying potential and authored/gradient-driven paths are unmodified.
const heightAt=(x:number,z:number)=>Math.atan(choicePotential(x,z,true,.58)*.24)*.62;
export const Choice:React.FC=()=>{
  const terrain=useMemo(()=>{
    const g=new THREE.PlaneGeometry(8.8,7.4,110,92);g.rotateX(-Math.PI/2);
    const p=g.attributes.position;const colors=[];
    for(let i=0;i<p.count;i++){
      const x=p.getX(i),z=p.getZ(i),y=heightAt(x,z);p.setY(i,y);
      const c=new THREE.Color('#56636c').lerp(new THREE.Color('#c4c4b5'),(y+1)/2);
      colors.push(c.r,c.g,c.b);
    }
    g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));g.computeVertexNormals();return g;
  },[]);
  const skirt=useMemo(()=>{
    const boundary:THREE.Vector3[]=[];
    for(let i=0;i<=110;i++)boundary.push(new THREE.Vector3(-4.4+i/110*8.8,0,-3.7));
    for(let i=1;i<=92;i++)boundary.push(new THREE.Vector3(4.4,0,-3.7+i/92*7.4));
    for(let i=1;i<=110;i++)boundary.push(new THREE.Vector3(4.4-i/110*8.8,0,3.7));
    for(let i=1;i<=92;i++)boundary.push(new THREE.Vector3(-4.4,0,3.7-i/92*7.4));
    const positions:number[]=[];
    for(let i=0;i<boundary.length-1;i++){
      const a=boundary[i].clone(),b=boundary[i+1].clone();a.y=heightAt(a.x,a.z);b.y=heightAt(b.x,b.z);
      const lowA=new THREE.Vector3(a.x,-1.22,a.z),lowB=new THREE.Vector3(b.x,-1.22,b.z);
      for(const p of [a,b,lowA,b,lowB,lowA])positions.push(...p.toArray());
    }
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));g.computeVertexNormals();return g;
  },[]);
  const paths=useMemo(()=>Array.from({length:10},(_,i)=>authoredChoicePath(i,60).map(p=>new THREE.Vector3(p.x,heightAt(p.x,p.y)+.025,p.y))),[]);
  const driven=useMemo(()=>integrateChoicePath(1,true,.58,100).map(p=>new THREE.Vector3(p.x,heightAt(p.x,p.y)+.06,p.y)),[]);
  const ball=driven[58];
  return <>
    <Floor y={-1.65}/>
    <group position={[1.1,-.5,0]} rotation={[0,-.22,0]} scale={.59}>
      <mesh geometry={terrain} castShadow receiveShadow><meshStandardMaterial vertexColors roughness={.53} metalness={.28} side={THREE.DoubleSide}/></mesh>
      <mesh geometry={skirt} castShadow receiveShadow><meshStandardMaterial color="#313b43" metalness={.25} roughness={.55} side={THREE.DoubleSide}/></mesh>
      {paths.map((p,i)=><Tube key={i} points={p} radius={.009} color="#a1b0ae" emission={0} opacity={.35}/>)}
      <Tube points={driven} radius={.031} color={gold} emission={.32}/>
      <mesh position={ball} castShadow><sphereGeometry args={[.18,48,32]}/><meshPhysicalMaterial color="#c68b31" metalness={.8} roughness={.19} clearcoat={.8}/></mesh>
      <pointLight position={[ball.x,ball.y+.4,ball.z]} intensity={.32} color="#e8b967" distance={2}/>
    </group>
  </>;
};

const ico=createGeodesicMesh(0);
const facets=ico.faces.map((face,i)=>{
  const v=face.map(k=>new THREE.Vector3(ico.vertices[k].x,ico.vertices[k].y,ico.vertices[k].z).multiplyScalar(1.43));
  const center=v[0].clone().add(v[1]).add(v[2]).divideScalar(3);
  const direction=center.clone().normalize();
  const local=v.map(p=>p.clone().sub(center).multiplyScalar(.982));
  const inner=local.map(p=>p.clone().addScaledVector(direction,-.085));
  const positions:number[]=[];
  const tri=(a:THREE.Vector3,b:THREE.Vector3,c:THREE.Vector3)=>positions.push(...a.toArray(),...b.toArray(),...c.toArray());
  tri(local[0],local[1],local[2]);tri(inner[2],inner[1],inner[0]);
  for(let j=0;j<3;j++){const n=(j+1)%3;tri(local[j],inner[j],local[n]);tri(local[n],inner[j],inner[n]);}
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.computeVertexNormals();
  return {geometry,center,direction,order:i};
});

export const Crystal:React.FC<{frame:number}>=({frame})=>{
  const close=smoothstep(Math.min(1,Math.max(0,(frame-220)/80)));
  const pulse=Math.max(0,1-(frame-300)/80)*(frame>=300?1:0);
  const rays=useMemo(()=>Array.from({length:6},(_,i)=>{
    const r=computeShieldRay(i*3,1.5);
    const source=new THREE.Vector3(r.origin.x,r.origin.y,r.origin.z);
    const hit=r.hit?new THREE.Vector3(r.hit.x,r.hit.y,r.hit.z):source.clone().multiplyScalar(.34);
    const out=r.exit?new THREE.Vector3(r.exit.x,r.exit.y,r.exit.z):hit.clone().multiplyScalar(2);
    return {source,hit,out,arc:r.arc.map(p=>new THREE.Vector3(p.x,p.y,p.z))};
  }),[]);
  const edges=useMemo(()=>ico.edges.map(([a,b])=>[ico.vertices[a],ico.vertices[b]].map(p=>new THREE.Vector3(p.x,p.y,p.z).multiplyScalar(1.445))),[]);
  const stars=useMemo(()=>Array.from({length:22},(_,i)=>{
    const theta=seededUnit(i,9)*Math.PI*2,phi=Math.acos(2*seededUnit(i,12)-1),r=.62+seededUnit(i,15)*.22;
    return new THREE.Vector3(Math.sin(phi)*Math.cos(theta)*r,Math.cos(phi)*r,Math.sin(phi)*Math.sin(theta)*r);
  }),[]);
  return <>
    <Floor/>
    <mesh position={[1.05,-1.66,0]} receiveShadow><cylinderGeometry args={[1.55,1.59,.1,96]}/><meshStandardMaterial color="#10151b" metalness={.4} roughness={.35} envMapIntensity={.25}/></mesh>
    <mesh position={[1.05,-1.605,0]} rotation={[Math.PI/2,0,0]}><torusGeometry args={[1.42,.008,8,128]}/><meshStandardMaterial color={gold} metalness={.8} roughness={.24}/></mesh>
    <group position={[1.05,.06,0]} rotation={[.16,frame/720*.18-.15,.06]}>
      <mesh rotation={[frame/1300,frame/1000,.15]} castShadow>
        <icosahedronGeometry args={[.55,2]}/><meshPhysicalMaterial color="#d49a39" metalness={.25} roughness={.24} emissive="#e58a13" emissiveIntensity={1.6+pulse*.65} clearcoat={.6}/>
      </mesh>
      <mesh><sphereGeometry args={[.19,40,32]}/><meshBasicMaterial color="#ffde8b"/></mesh>
      {stars.map((p,i)=><mesh key={i} position={p}><sphereGeometry args={[.013+seededUnit(i,2)*.014,8,8]}/><meshStandardMaterial color="#edc578" emissive="#ce8e37" emissiveIntensity={.65}/></mesh>)}
      {facets.map(({geometry,center,direction,order})=>{
        const progress=smoothstep(Math.min(1,Math.max(0,(frame-170-order*3)/Math.max(40,130-order*3))));
        const distance=(1-progress)*(.8+seededUnit(order,1)*.25);
        const position=center.clone().addScaledVector(direction,distance);
        return <mesh key={order} geometry={geometry} position={position} rotation={[0,(1-progress)*.13,0]} castShadow>
          <meshPhysicalMaterial color={order%4===0?'#bb9557':'#f6faf8'} metalness={order%4===0?.7:0} roughness={order%4===0?.18:.055} transmission={order%4===0?0:.98} thickness={.12} ior={1.46} envMapIntensity={order%4===0?1.25:.7} clearcoat={.45} side={THREE.DoubleSide}/>
        </mesh>;
      })}
      {edges.map((points,i)=><group key={i} visible={close>.02}><Tube points={points} radius={.009} color={gold} emission={.2+pulse} opacity={close}/></group>)}
      {rays.map(({source,hit,out,arc},i)=>{
        // Preserve the deterministic intersection/deflection math; light strands
        // visualize a design boundary, not a measured security guarantee.
        const phase=(((frame+i*63)%240+240)%240)/240;
        const p=source.clone().lerp(hit,phase);
        return <group key={i}>
          <Tube points={[source,hit]} radius={.0045} color="#739ca7" opacity={.14+.12*close} emission={.35}/>
          <Tube points={[hit,...arc,out]} radius={.0045} color="#739ca7" opacity={.26*smoothstep(Math.max(0,(close-.35)/.65))} emission={.35}/>
          <mesh position={p}><sphereGeometry args={[.021,12,8]}/><meshBasicMaterial color="#b5e0e5"/></mesh>
        </group>;
      })}
      {pulse>0&&<mesh scale={1+(1-pulse)*1.2} rotation={[-Math.PI/2,0,0]}><torusGeometry args={[1.52,.012,8,128]}/><meshBasicMaterial color="#ecd2a0" transparent opacity={pulse*.7}/></mesh>}
    </group>
  </>;
};
