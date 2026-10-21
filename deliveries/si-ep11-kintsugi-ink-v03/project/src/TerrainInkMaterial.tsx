import React,{useMemo,useLayoutEffect} from 'react';
import * as THREE from 'three';

/** Ink and gold are evaluated on the rock itself, so no floating overlay can
 * intersect a differently triangulated surface. This is an authored metaphor. */
export const TerrainInkMaterial:React.FC<{frame:number;marble:THREE.Texture}>=({frame,marble})=>{
 const uniform=useMemo(()=>({value:frame}),[]);
 const material=useMemo(()=>{
  const m=new THREE.MeshPhysicalMaterial({color:'#FFFFFF',map:marble,bumpMap:marble,bumpScale:.035,vertexColors:true,roughness:.53,metalness:.04,clearcoat:.28,clearcoatRoughness:.36,envMapIntensity:.34,side:THREE.DoubleSide});
  m.onBeforeCompile=s=>{
   s.uniforms.uInkFrame=uniform;
   s.vertexShader=s.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 vTerrainP;').replace('#include <begin_vertex>','#include <begin_vertex>\nvTerrainP=position;');
   s.fragmentShader=s.fragmentShader.replace('#include <common>',`#include <common>
varying vec3 vTerrainP;uniform float uInkFrame;
float tiHash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float tiNoise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(tiHash(i),tiHash(i+vec2(1.,0.)),f.x),mix(tiHash(i+vec2(0.,1.)),tiHash(i+vec2(1.,1.)),f.x),f.y);}
float tiFbm(vec2 p){float v=0.,a=.5;for(int k=0;k<5;k++){v+=a*tiNoise(p);p=mat2(1.6,1.2,-1.2,1.6)*p;a*=.5;}return v;}`);
   s.fragmentShader=s.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>
float tiCenter=.35*sin(vTerrainP.z*.22)+.15*sin(vTerrainP.z*.59);
float tiBranch=clamp((-16.-vTerrainP.z)*.28,0.,9.8);
float tiDistance=min(abs(vTerrainP.x-tiCenter-tiBranch),abs(vTerrainP.x-tiCenter+tiBranch));
float tiChannel=1.-smoothstep(.4,.68,tiDistance);
float tiFront=mix(6.,-30.,smoothstep(2940.,3300.,uInkFrame));
float tiRepaired=smoothstep(2940.,2990.,uInkFrame)*smoothstep(tiFront-.9,tiFront+.9,vTerrainP.z);
float tiClock=mix(uInkFrame*.011,64.-uInkFrame*.011,tiRepaired);
float tiN=tiFbm(vec2(vTerrainP.x*2.3,vTerrainP.z*.55+tiClock));
float tiVein=pow(.5+.5*sin((vTerrainP.x-tiCenter)*31.+tiN*16.-tiClock*.6),14.);
vec3 tiInk=mix(vec3(.005,.006,.008),vec3(.022,.019,.016),tiN);
vec3 tiGold=mix(vec3(.16,.075,.014),vec3(.9,.56,.16),tiVein*.85+tiN*.12);
diffuseColor.rgb=mix(diffuseColor.rgb,mix(tiInk,tiGold,tiRepaired),tiChannel*.96);`);
   s.fragmentShader=s.fragmentShader.replace('#include <roughnessmap_fragment>','#include <roughnessmap_fragment>\nroughnessFactor=mix(roughnessFactor,.2,tiChannel);');
   s.fragmentShader=s.fragmentShader.replace('#include <metalnessmap_fragment>','#include <metalnessmap_fragment>\nmetalnessFactor=mix(metalnessFactor,.83,tiChannel*tiRepaired);');
   s.fragmentShader=s.fragmentShader.replace('#include <emissivemap_fragment>','#include <emissivemap_fragment>\ntotalEmissiveRadiance+=vec3(.52,.28,.06)*tiChannel*tiRepaired*(.2+tiVein*.7);');
  };
  m.customProgramCacheKey=()=> 'ep11-conformal-ink-v1';
  return m;
 },[marble,uniform]);
 useLayoutEffect(()=>{uniform.value=frame;},[uniform,frame]);
 return <primitive attach="material" object={material}/>;
};
