import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import ts from 'typescript';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const source=fs.readFileSync(path.join(root,'src/physics.ts'),'utf8');
const transpiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const sandbox={exports:{},Math,Number};vm.runInNewContext(transpiled,sandbox);const p=sandbox.exports;
// Independent quadrature over wavelength verifies both the per-micrometre
// conversion and the hemispherical pi factor against Stefan–Boltzmann.
function integrateExitance(T){
 let sum=0;const n=24000,lo=Math.log(0.001),hi=Math.log(100000);
 for(let i=0;i<n;i++){
  const a=Math.exp(lo+(hi-lo)*i/n),b=Math.exp(lo+(hi-lo)*(i+1)/n);
  sum+=(p.planck(a,T)+p.planck(b,T))*(b-a)/2;
 }
 return Math.PI*sum;
}
const spectra=[300,330,348].map(T=>{const integral=integrateExitance(T),expected=p.STEFAN_BOLTZMANN*T**4;return {T,integral_W_m2:integral,sigmaT4_W_m2:expected,relative_error:Math.abs(integral/expected-1)};});
const branch=[1,2,3,4,5,6,7].map(level=>{const parent=.03*p.murrayChild(1)**(level-1),child=p.murrayChild(parent);return {level,parent_radius_m:parent,child_radius_m:child,cubic_ratio:2*child**3/parent**3};});
const balances=[3600,3900,4800,5399].map(frame=>{const s=p.state(frame);const equilibriumT=((s.absorbedSolar+s.wasteHeat)/(4*Math.PI*p.EARTH_RADIUS**2*p.EARTH_EMISSIVITY*p.STEFAN_BOLTZMANN))**.25;const equilibriumOut=p.radiated(equilibriumT);return {frame,authored_scenario_T:s.temperature,compute_W:s.wasteHeat,comparison_equilibrium_T:equilibriumT,relative_residual:(s.absorbedSolar+s.wasteHeat-equilibriumOut)/equilibriumOut};});
const failures=[];
if(spectra.some(s=>s.relative_error>1e-5))failures.push('Planck integral does not match sigma T^4');
if(branch.some(b=>Math.abs(b.cubic_ratio-1)>1e-12))failures.push('Murray cubic conservation fails');
if(balances.some(b=>Math.abs(b.relative_residual)>1e-12))failures.push('Independent greybody equilibrium comparison fails');
const coldFloor=p.landauer(2.725),warmFloor=p.landauer(300);
const report={status:failures.length?'FAIL':'PASS',source_sha256:crypto.createHash('sha256').update(source).digest('hex'),spectral_exitance:spectra,murray_branch_conservation:branch,independent_equilibrium_comparison:balances,temperature_montage_is_not_this_equilibrium:true,landauer:{warm_J:warmFloor,cold_J:coldFloor,ideal_ratio:warmFloor/coldFloor,trillion_erasures_at_300K_nJ:warmFloor*1e21},model_boundaries:'../project/scientific-notes.md',failures};
fs.writeFileSync(path.join(root,'../review/physics-conservation.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));if(failures.length)process.exitCode=1;
