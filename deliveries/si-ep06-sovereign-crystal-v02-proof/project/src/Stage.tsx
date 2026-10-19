import React, {useLayoutEffect, useMemo} from 'react';
import {useThree} from '@react-three/fiber';
import * as THREE from 'three';

/** A locally authored studio, not a downloaded HDRI. Broad softboxes give the
 * objects readable form; every sample is deterministic. */
export const StudioEnvironment: React.FC = () => {
  const {scene,gl} = useThree();
  useLayoutEffect(() => {
    const width=256,height=128,data=new Float32Array(width*height*4);
    const box=(u:number,v:number,x:number,y:number,w:number,h:number)=>
      Math.exp(-Math.pow((u-x)/w,8)-Math.pow((v-y)/h,8));
    for(let y=0;y<height;y++) for(let x=0;x<width;x++){
      const u=x/width,v=y/height,i=(y*width+x)*4;
      const white=box(u,v,.24,.38,.075,.24)*8+box(u,v,.76,.42,.035,.22)*5;
      const warm=box(u,v,.52,.25,.15,.025)*4;
      data[i]=.045+white+warm;data[i+1]=.05+white+warm*.72;data[i+2]=.06+white+warm*.38;data[i+3]=1;
    }
    const texture=new THREE.DataTexture(data,width,height,THREE.RGBAFormat,THREE.FloatType);
    texture.mapping=THREE.EquirectangularReflectionMapping;texture.needsUpdate=true;
    const pmrem=new THREE.PMREMGenerator(gl);const target=pmrem.fromEquirectangular(texture);
    scene.environment=target.texture;scene.environmentIntensity=.5;
    gl.toneMapping=THREE.ACESFilmicToneMapping;gl.toneMappingExposure=1;
    gl.outputColorSpace=THREE.SRGBColorSpace;
    return()=>{scene.environment=null;target.dispose();texture.dispose();pmrem.dispose();};
  },[scene,gl]);
  return <>
    <ambientLight intensity={.18}/>
    <directionalLight position={[-3,7,4]} intensity={2.4} color="#fff1d9" castShadow shadow-mapSize={[2048,2048]} shadow-bias={-.0005} shadow-normalBias={.04} shadow-camera-left={-8} shadow-camera-right={8} shadow-camera-top={8} shadow-camera-bottom={-8}/>
    <directionalLight position={[5,2,-4]} intensity={1.9} color="#a5d8dd"/>
    <directionalLight position={[-5,0,-2]} intensity={.7} color="#b8c5d4"/>
  </>;
};

export const CameraAim:React.FC<{target:[number,number,number]}>=({target})=>{
  const {camera}=useThree();
  useLayoutEffect(()=>{camera.lookAt(...target);camera.updateProjectionMatrix();},[camera,target[0],target[1],target[2]]);
  return null;
};

export const Floor:React.FC<{y?:number;color?:string}>=({y=-1.72,color='#121923'})=><mesh rotation={[-Math.PI/2,0,0]} position={[0,y,0]} receiveShadow>
  <planeGeometry args={[200,200]}/><meshStandardMaterial color={color} roughness={.7} metalness={.05} envMapIntensity={.12}/>
</mesh>;

export const Tube:React.FC<{points:THREE.Vector3[];radius?:number;color?:string;emission?:number;opacity?:number}>=({points,radius=.012,color='#d9ad61',emission=.15,opacity=1})=>{
  const geometry=useMemo(()=>new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points),Math.max(8,Math.min(160,points.length*2)),radius,7,false),[points,radius]);
  useLayoutEffect(()=>()=>geometry.dispose(),[geometry]);
  return <mesh geometry={geometry}><meshStandardMaterial color={color} emissive={color} emissiveIntensity={emission} metalness={.6} roughness={.25} transparent={opacity<1} opacity={opacity}/></mesh>;
};
