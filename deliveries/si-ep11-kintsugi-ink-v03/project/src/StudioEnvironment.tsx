import React,{useEffect,useMemo} from 'react';
import {useThree} from '@react-three/fiber';
import * as THREE from 'three';
import {RoomEnvironment} from 'three/examples/jsm/environments/RoomEnvironment.js';

/** Local studio reflection map, shared by the two photographic worlds. */
export const StudioEnvironment:React.FC<{intensity?:number}>=({intensity=.7})=>{
 const {gl,scene}=useThree();
 const target=useMemo(()=>{
  const generator=new THREE.PMREMGenerator(gl);
  const room=new RoomEnvironment();
  const result=generator.fromScene(room,.04);
  room.dispose();generator.dispose();
  return result;
 },[gl]);
 useEffect(()=>{
  const previous=scene.environment;
  const before=scene.environmentIntensity;
  scene.environment=target.texture;scene.environmentIntensity=intensity;
  return()=>{scene.environment=previous;scene.environmentIntensity=before;};
 },[scene,target,intensity]);
 useEffect(()=>()=>target.dispose(),[target]);
 return null;
};
