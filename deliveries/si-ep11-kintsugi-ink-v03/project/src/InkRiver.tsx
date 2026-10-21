import React,{useLayoutEffect,useMemo} from 'react';
import * as THREE from 'three';

type Props={frame:number;heightAt:(x:number,z:number)=>number;centerAt:(z:number)=>number;fromZ?:number;toZ?:number;width?:number};

/** An authored viscous ink surface, not a biological or fluid-dynamics simulation. */
export const InkRiver:React.FC<Props>=({frame,heightAt,centerAt,fromZ=14,toZ=-42,width=2.1})=>{
 const geometry=useMemo(()=>{
  const n=640,m=24,vertices:number[]=[],uv:number[]=[],indices:number[]=[];
  for(let j=0;j<=n;j++)for(let i=0;i<=m;i++){
   const z=fromZ+(toZ-fromZ)*j/n,x=centerAt(z)+(i/m-.5)*width;
   // A continuous liquid level bridges the small rubble in the bed. Sampling
   // a different triangulation of the rock caused alternating occlusion bands.
   vertices.push(x,Math.max(-1.38,heightAt(x,z)+.08),z);uv.push(i/m,j/n);
   if(j<n&&i<m){const a=j*(m+1)+i,b=a+1,c=a+m+1,d=c+1;indices.push(a,c,b,b,c,d);}
  }
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));g.setIndex(indices);g.computeVertexNormals();return g;
 },[heightAt,centerAt,fromZ,toZ,width]);
 const material=useMemo(()=>new THREE.ShaderMaterial({transparent:true,depthWrite:false,side:THREE.DoubleSide,uniforms:{uFrame:{value:frame}},vertexShader:`
  varying vec2 vUv;varying vec3 vP;uniform float uFrame;
  void main(){vUv=uv;vP=position;vec3 p=position;p.y+=sin(p.z*1.8+uFrame*.012)*.009;gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.);}
 `,fragmentShader:`
  varying vec2 vUv;varying vec3 vP;uniform float uFrame;
  float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
  float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
  float fbm(vec2 p){float v=0.,a=.5;for(int k=0;k<5;k++){v+=a*noise(p);p=mat2(1.6,1.2,-1.2,1.6)*p;a*=.5;}return v;}
  void main(){
   float front=mix(6.,-30.,smoothstep(2940.,3300.,uFrame));
   float repaired=smoothstep(2940.,2990.,uFrame)*smoothstep(front-.9,front+.9,vP.z);
   float clock=uFrame*.011;clock=mix(clock,64.-clock,repaired);
   vec2 p=vec2(vUv.x*3.,vP.z*.35+clock);
   float n=fbm(p+vec2(fbm(p*.7+clock*.08),fbm(p*.9-clock*.07)));
   float veins=pow(.5+.5*sin(vUv.x*37.+n*18.-clock*.6),18.);
   float edge=smoothstep(0.,.12,vUv.x)*(1.-smoothstep(.86,1.,vUv.x));
   vec3 ink=mix(vec3(.009,.011,.014),vec3(.035,.03,.025),n);
   vec3 gold=mix(vec3(.12,.052,.012),vec3(.68,.39,.095),veins*.9+n*.12);
   vec3 color=mix(ink,gold,repaired*.9);
   float gloss=pow(max(0.,sin(n*13.+clock*.22)),30.)*.035;
   color+=vec3(gloss*.9,gloss*.8,gloss*.64);
   gl_FragColor=vec4(color,edge*mix(.86,.63,repaired));
   #include <tonemapping_fragment>
   #include <colorspace_fragment>
  }
 `}),[]);
 useLayoutEffect(()=>{material.uniforms.uFrame.value=frame;},[material,frame]);
 return <mesh geometry={geometry} material={material} renderOrder={2} frustumCulled={false}/>;
};
