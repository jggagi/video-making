import React, {useEffect, useLayoutEffect, useRef, useState} from 'react';
import {useDelayRender} from 'remotion';

export type SurfaceMode = 'stream' | 'gathering' | 'landscape' | 'still';

export const PaintedSurface: React.FC<{
  src: string;
  frame: number;
  mode: SurfaceMode;
  width?: number;
  height?: number;
}> = ({src, frame, mode, width = 1920, height = 1080}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const imageSourceRef = useRef<string | null>(null);
  const resourcesRef = useRef<SurfaceResources | null>(null);
  const pendingDelayRef = useRef<PendingDelay | null>(null);
  const [loadedSource, setLoadedSource] = useState<string | null>(null);
  const {delayRender, continueRender, cancelRender} = useDelayRender();

  useEffect(() => {
    const handle = delayRender(`Loading painted surface image: ${src}`);
    const pending: PendingDelay = {src, handle, completed: false};
    pendingDelayRef.current = pending;

    if (!src) {
      pending.completed = true;
      cancelRender(new Error('PaintedSurface received an empty image src.'));
      return () => {
        continueRender(handle);
      };
    }

    let cancelled = false;
    const image = new window.Image();
    image.onload = () => {
      if (cancelled) {
        return;
      }
      imageRef.current = image;
      imageSourceRef.current = src;
      setLoadedSource(src);
    };
    image.onerror = () => {
      if (cancelled) {
        return;
      }
      pending.completed = true;
      cancelRender(new Error(`PaintedSurface could not load image: ${src}`));
    };
    image.src = src;

    return () => {
      cancelled = true;
      image.onload = null;
      image.onerror = null;
      if (imageSourceRef.current === src) {
        imageRef.current = null;
        imageSourceRef.current = null;
      }
      if (!pending.completed) {
        pending.completed = true;
        continueRender(handle);
      }
      if (pendingDelayRef.current === pending) {
        pendingDelayRef.current = null;
      }
    };
  }, [src, delayRender, continueRender, cancelRender]);

  useLayoutEffect(() => {
    if (loadedSource !== src || imageSourceRef.current !== src) {
      return;
    }

    const canvas = canvasRef.current;
    const image = imageRef.current;
    if (!canvas || !image) {
      return;
    }

    try {
      let resources = resourcesRef.current;
      if (!resources) {
        resources = createSurfaceResources(canvas);
        resourcesRef.current = resources;
      }

      drawSurface(resources, canvas, image, frame, mode, width, height);

      const pending = pendingDelayRef.current;
      if (pending?.src === src && !pending.completed) {
        pending.completed = true;
        continueRender(pending.handle);
      }
    } catch (error) {
      const pending = pendingDelayRef.current;
      if (pending?.src === src) {
        pending.completed = true;
      }
      cancelRender(
        error instanceof Error
          ? error
          : new Error(`PaintedSurface failed for ${src}: ${String(error)}`),
      );
    }
  }, [
    src,
    loadedSource,
    frame,
    mode,
    width,
    height,
    continueRender,
    cancelRender,
  ]);

  useLayoutEffect(() => {
    return () => {
      if (resourcesRef.current) {
        disposeSurfaceResources(resourcesRef.current);
        resourcesRef.current = null;
      }
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        display: 'block',
        width: '100%',
        height: '100%',
        aspectRatio: `${width} / ${height}`,
      }}
    />
  );
};

type GLContext = WebGLRenderingContext | WebGL2RenderingContext;

type PendingDelay = {
  src: string;
  handle: number;
  completed: boolean;
};

type SurfaceResources = {
  gl: GLContext;
  isWebGL2: boolean;
  program: WebGLProgram;
  vertexBuffer: WebGLBuffer;
  texture: WebGLTexture;
  positionLocation: number;
  uvLocation: number;
  frameLocation: WebGLUniformLocation;
  resolutionLocation: WebGLUniformLocation;
  modeLocation: WebGLUniformLocation;
  fitScaleLocation: WebGLUniformLocation;
  textureLocation: WebGLUniformLocation;
  uploadedImage: HTMLImageElement | null;
};

const vertexShaderBody = `
__ATTRIBUTE__ vec2 aPosition;
__ATTRIBUTE__ vec2 aUv;
__VARYING_OUT__ vec2 vUv;
uniform vec2 uFitScale;

void main() {
  gl_Position = vec4(aPosition * uFitScale, 0.0, 1.0);
  vUv = aUv;
}
`;

const fragmentShaderBody = `
precision mediump float;
__VARYING_IN__ vec2 vUv;
uniform sampler2D uImage;
uniform vec2 uResolution;
uniform float uFrame;
uniform float uMode;
__FRAGMENT_OUTPUT_DECL__

float streamEdgeDistance(vec2 p, vec2 a, vec2 b) {
  vec2 edge = b - a;
  return (edge.x * (p.y - a.y) - edge.y * (p.x - a.x)) / length(edge);
}

float streamPolygonMask(vec2 p) {
  float insideDistance = streamEdgeDistance(p, vec2(0.00, 0.24), vec2(0.43, 0.23));
  insideDistance = min(insideDistance, streamEdgeDistance(p, vec2(0.43, 0.23), vec2(0.64, 0.45)));
  insideDistance = min(insideDistance, streamEdgeDistance(p, vec2(0.64, 0.45), vec2(0.83, 0.62)));
  insideDistance = min(insideDistance, streamEdgeDistance(p, vec2(0.83, 0.62), vec2(0.98, 1.00)));
  insideDistance = min(insideDistance, streamEdgeDistance(p, vec2(0.98, 1.00), vec2(0.00, 1.00)));
  insideDistance = min(insideDistance, streamEdgeDistance(p, vec2(0.00, 1.00), vec2(0.00, 0.24)));
  return smoothstep(0.0, 0.012, insideDistance);
}

float ellipseKeep(vec2 p, vec2 center, vec2 radius) {
  float distanceFromCenter = length((p - center) / radius);
  return smoothstep(0.92, 1.16, distanceFromCenter);
}

float streamMask(vec2 p) {
  float mask = streamPolygonMask(p);
  mask *= ellipseKeep(p, vec2(0.34, 0.96), vec2(0.085, 0.060));
  mask *= ellipseKeep(p, vec2(0.57, 0.96), vec2(0.110, 0.072));
  mask *= ellipseKeep(p, vec2(0.77, 0.93), vec2(0.105, 0.078));
  mask *= ellipseKeep(p, vec2(0.93, 0.78), vec2(0.085, 0.145));

  float bankLimit = mix(0.84, 0.72, smoothstep(0.58, 1.0, p.y));
  mask *= 1.0 - smoothstep(bankLimit - 0.016, bankLimit + 0.016, p.x);
  return mask;
}

float gatheringSegmentDistance(vec2 p, vec2 a, vec2 b, float startWidth, float endWidth) {
  vec2 aspect = vec2(1.0, 0.5625);
  vec2 metricPoint = p * aspect;
  vec2 metricStart = a * aspect;
  vec2 metricEnd = b * aspect;
  vec2 segment = metricEnd - metricStart;
  float amount = clamp(dot(metricPoint - metricStart, segment) / dot(segment, segment), 0.0, 1.0);
  float width = mix(startWidth, endWidth, amount);
  return length(metricPoint - (metricStart + segment * amount)) - width;
}

float gatheringMask(vec2 p) {
  float distanceToWater = gatheringSegmentDistance(p, vec2(0.49, 1.00), vec2(0.455, 0.84), 0.10, 0.075);
  distanceToWater = min(distanceToWater, gatheringSegmentDistance(p, vec2(0.455, 0.84), vec2(0.55, 0.69), 0.075, 0.080));
  distanceToWater = min(distanceToWater, gatheringSegmentDistance(p, vec2(0.55, 0.69), vec2(0.70, 0.48), 0.080, 0.047));
  distanceToWater = min(distanceToWater, gatheringSegmentDistance(p, vec2(0.70, 0.48), vec2(0.77, 0.30), 0.047, 0.025));

  float mask = 1.0 - smoothstep(-0.010, 0.010, distanceToWater);
  mask *= ellipseKeep(p, vec2(0.36, 0.69), vec2(0.088, 0.092));
  mask *= ellipseKeep(p, vec2(0.54, 0.94), vec2(0.063, 0.069));
  return mask;
}

void main() {
  vec2 topLeftUv = vec2(vUv.x, 1.0 - vUv.y);
  float mask = 0.0;
  vec2 flow = vec2(-0.87, 0.49);

  if (uMode > 0.5 && uMode < 1.5) {
    mask = streamMask(topLeftUv);
  } else if (uMode > 1.5 && uMode < 2.5) {
    mask = gatheringMask(topLeftUv);
    flow = vec2(-0.65, 0.76);
  }

  vec2 perpendicular = vec2(-flow.y, flow.x);
  float alongFlow = dot(topLeftUv, flow);
  float acrossFlow = dot(topLeftUv, perpendicular);
  float waveA = sin(alongFlow * 71.0 - uFrame * 0.085 + sin(acrossFlow * 16.0 + uFrame * 0.012) * 0.60);
  float waveB = sin(alongFlow * 122.0 - uFrame * 0.11 + acrossFlow * 24.0);
  vec2 displacementPixels = flow * (waveA * 1.65) + perpendicular * (waveB * 2.0);
  vec2 textureOffset = vec2(displacementPixels.x / uResolution.x, -displacementPixels.y / uResolution.y) * mask;
  vec2 sampleUv = clamp(vUv + textureOffset, vec2(0.0), vec2(1.0));
  vec4 color = __SAMPLE_TEXTURE__(uImage, sampleUv);

  float crestA = sin(alongFlow * 88.0 - uFrame * 0.078 + sin(acrossFlow * 19.0 + uFrame * 0.014) * 0.72);
  float crestB = sin(alongFlow * 151.0 - uFrame * 0.115 + acrossFlow * 21.0 + sin(alongFlow * 12.0 + uFrame * 0.025) * 0.38);
  float highlight = smoothstep(0.54, 0.96, crestA * 0.64 + crestB * 0.36) * mask;
  color.rgb += vec3(0.70, 0.82, 0.78) * (highlight * 0.045);
  __FRAGMENT_OUTPUT__ = color;
}
`;

const compileShader = (gl: GLContext, type: number, source: string, label: string) => {
  const shader = gl.createShader(type);
  if (!shader) {
    throw new Error(`PaintedSurface could not create the ${label} shader.`);
  }
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const details = gl.getShaderInfoLog(shader) ?? 'No shader details were provided.';
    gl.deleteShader(shader);
    throw new Error(`PaintedSurface ${label} shader failed to compile: ${details}`);
  }
  return shader;
};

const requireUniform = (gl: GLContext, program: WebGLProgram, name: string) => {
  const location = gl.getUniformLocation(program, name);
  if (!location) {
    throw new Error(`PaintedSurface could not find shader uniform ${name}.`);
  }
  return location;
};

const createSurfaceResources = (canvas: HTMLCanvasElement): SurfaceResources => {
  const attributes: WebGLContextAttributes = {
    alpha: true,
    antialias: false,
    premultipliedAlpha: false,
    preserveDrawingBuffer: true,
  };
  const webgl2 = canvas.getContext('webgl2', attributes);
  const webgl1 = webgl2 ? null : canvas.getContext('webgl', attributes);
  const gl = webgl2 ?? webgl1;
  if (!gl) {
    throw new Error('PaintedSurface could not create a WebGL2 or WebGL context.');
  }
  const isWebGL2 = webgl2 !== null;

  const vertexSource = `${isWebGL2 ? '#version 300 es\n' : ''}${vertexShaderBody
    .replaceAll('__ATTRIBUTE__', isWebGL2 ? 'in' : 'attribute')
    .replace('__VARYING_OUT__', isWebGL2 ? 'out' : 'varying')}`;
  const fragmentSource = `${isWebGL2 ? '#version 300 es\n' : ''}${fragmentShaderBody
    .replace('__VARYING_IN__', isWebGL2 ? 'in' : 'varying')
    .replace('__FRAGMENT_OUTPUT_DECL__', isWebGL2 ? 'out vec4 outColor;' : '')
    .replaceAll('__SAMPLE_TEXTURE__', isWebGL2 ? 'texture' : 'texture2D')
    .replaceAll('__FRAGMENT_OUTPUT__', isWebGL2 ? 'outColor' : 'gl_FragColor')}`;

  const vertexShader = compileShader(gl, gl.VERTEX_SHADER, vertexSource, 'vertex');
  let fragmentShader: WebGLShader;
  try {
    fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource, 'fragment');
  } catch (error) {
    gl.deleteShader(vertexShader);
    throw error;
  }

  let program: WebGLProgram | null = null;
  let vertexBuffer: WebGLBuffer | null = null;
  let texture: WebGLTexture | null = null;
  try {
    program = gl.createProgram();
    if (!program) {
      throw new Error('PaintedSurface could not create a WebGL program.');
    }
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      const details = gl.getProgramInfoLog(program) ?? 'No program details were provided.';
      throw new Error(`PaintedSurface shader program failed to link: ${details}`);
    }

    const positionLocation = gl.getAttribLocation(program, 'aPosition');
    const uvLocation = gl.getAttribLocation(program, 'aUv');
    if (positionLocation < 0 || uvLocation < 0) {
      throw new Error('PaintedSurface shader attributes were not linked.');
    }

    const frameLocation = requireUniform(gl, program, 'uFrame');
    const resolutionLocation = requireUniform(gl, program, 'uResolution');
    const modeLocation = requireUniform(gl, program, 'uMode');
    const fitScaleLocation = requireUniform(gl, program, 'uFitScale');
    const textureLocation = requireUniform(gl, program, 'uImage');
    vertexBuffer = gl.createBuffer();
    texture = gl.createTexture();
    if (!vertexBuffer || !texture) {
      throw new Error('PaintedSurface could not allocate its WebGL buffers.');
    }

    gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([
        -1, -1, 0, 0,
        1, -1, 1, 0,
        -1, 1, 0, 1,
        1, 1, 1, 1,
      ]),
      gl.STATIC_DRAW,
    );
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, 1);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 0);
    gl.clearColor(0, 0, 0, 0);

    const glError = gl.getError();
    if (glError !== gl.NO_ERROR) {
      throw new Error(`PaintedSurface WebGL setup failed with error 0x${glError.toString(16)}.`);
    }

    return {
      gl,
      isWebGL2,
      program,
      vertexBuffer,
      texture,
      positionLocation,
      uvLocation,
      frameLocation,
      resolutionLocation,
      modeLocation,
      fitScaleLocation,
      textureLocation,
      uploadedImage: null,
    };
  } catch (error) {
    if (texture) {
      gl.deleteTexture(texture);
    }
    if (vertexBuffer) {
      gl.deleteBuffer(vertexBuffer);
    }
    if (program) {
      gl.deleteProgram(program);
    }
    throw error;
  } finally {
    gl.deleteShader(vertexShader);
    gl.deleteShader(fragmentShader);
  }
};

const drawSurface = (
  resources: SurfaceResources,
  canvas: HTMLCanvasElement,
  image: HTMLImageElement,
  frame: number,
  mode: SurfaceMode,
  width: number,
  height: number,
) => {
  const {gl} = resources;
  if (width <= 0 || height <= 0) {
    throw new Error(`PaintedSurface requires positive dimensions, received ${width}x${height}.`);
  }
  if (canvas.width !== width) {
    canvas.width = width;
  }
  if (canvas.height !== height) {
    canvas.height = height;
  }

  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.useProgram(resources.program);
  gl.bindBuffer(gl.ARRAY_BUFFER, resources.vertexBuffer);
  gl.enableVertexAttribArray(resources.positionLocation);
  gl.vertexAttribPointer(resources.positionLocation, 2, gl.FLOAT, false, 16, 0);
  gl.enableVertexAttribArray(resources.uvLocation);
  gl.vertexAttribPointer(resources.uvLocation, 2, gl.FLOAT, false, 16, 8);

  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, resources.texture);
  if (resources.uploadedImage !== image) {
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
    resources.uploadedImage = image;
  }

  const imageAspect = image.naturalWidth / image.naturalHeight;
  const outputAspect = width / height;
  const fitX = imageAspect < outputAspect ? imageAspect / outputAspect : 1;
  const fitY = imageAspect > outputAspect ? outputAspect / imageAspect : 1;
  const modeValue = mode === 'stream' ? 1 : mode === 'gathering' ? 2 : 0;

  gl.uniform2f(resources.fitScaleLocation, fitX, fitY);
  gl.uniform1f(resources.frameLocation, frame);
  gl.uniform2f(resources.resolutionLocation, image.naturalWidth, image.naturalHeight);
  gl.uniform1f(resources.modeLocation, modeValue);
  gl.uniform1i(resources.textureLocation, 0);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  gl.flush();

  const glError = gl.getError();
  if (glError !== gl.NO_ERROR) {
    throw new Error(`PaintedSurface WebGL draw failed with error 0x${glError.toString(16)}.`);
  }
};

const disposeSurfaceResources = (resources: SurfaceResources) => {
  resources.gl.deleteTexture(resources.texture);
  resources.gl.deleteBuffer(resources.vertexBuffer);
  resources.gl.deleteProgram(resources.program);
  resources.uploadedImage = null;
};
