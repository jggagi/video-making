export const MODEL_KIND='illustrative mixture of two deterministic episode policies, not paper data';
export const policyMetrics=(q:number)=>({q,proxyReward:1+5*q,normalizedProxy:(1+5*q)/6,finishRate:1-q});
export const SPRING={forceN:10,assumedStiffnessNPerM:1000,trueStiffnessNPerM:500,limitMm:15,predictedMm:10,observedMm:20};
