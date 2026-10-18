/** Analytical models used by the EP05 scientific plots.
 *
 * These helpers describe idealized equations and explicitly stated model
 * assumptions. They do not simulate a physical device, climate, or organism.
 */
export const BOLTZMANN = 1.380649e-23; // J K^-1, exact SI value
export const PLANCK = 6.62607015e-34; // J s, exact SI value
export const LIGHT_SPEED = 299_792_458; // m s^-1, exact SI value
export const STEFAN_BOLTZMANN = 5.670374419e-8; // W m^-2 K^-4
export const WIEN_B = 2.897771955e-3; // m K

export const ROOM_TEMPERATURE = 300;
export const CMB_TEMPERATURE = 2.725;
export const EARTH_RADIUS = 6_371_000; // m
export const EARTH_EMISSIVITY = 0.61; // fixed illustrative greybody assumption
export const SOLAR_ALBEDO = 0.30; // fixed illustrative model assumption
export const SOLAR_CONSTANT = 1361; // W m^-2
export const SOLAR_INTERCEPT = Math.PI * EARTH_RADIUS ** 2 * SOLAR_CONSTANT;
export const ABSORBED_SOLAR = (1 - SOLAR_ALBEDO) * SOLAR_INTERCEPT;

const clamp01 = (value: number): number => Math.max(0, Math.min(1, value));
const smoothstep = (value: number): number => {
  const t = clamp01(value);
  return t * t * (3 - 2 * t);
};

/** Landauer energy floor in joules per erased bit. */
export function landauer(temperature: number): number {
  return BOLTZMANN * temperature * Math.LN2;
}

/**
 * Planck spectral radiance B_lambda in W m^-2 sr^-1 μm^-1.
 * The wavelength input is in micrometres.
 */
export function planck(lambdaMicron: number, temperature: number): number {
  if (!(lambdaMicron > 0) || !(temperature > 0)) return 0;
  const lambda = lambdaMicron * 1e-6;
  const exponent = (PLANCK * LIGHT_SPEED) / (lambda * BOLTZMANN * temperature);
  if (exponent > 700) return 0;
  const denominator = Math.expm1(exponent);
  if (!Number.isFinite(denominator) || denominator <= 0) return 0;
  // Convert spectral density per metre to spectral density per micrometre.
  return (2 * PLANCK * LIGHT_SPEED ** 2) / (lambda ** 5 * denominator) * 1e-6;
}

/** Wien peak wavelength in micrometres for the plotted B_lambda spectrum. */
export function wien(temperature: number): number {
  return temperature > 0 ? (WIEN_B / temperature) * 1e6 : Number.POSITIVE_INFINITY;
}

/** Total spherical blackbody output power, with a stated greybody emissivity. */
export function radiated(temperature: number, epsilon = EARTH_EMISSIVITY): number {
  return 4 * Math.PI * EARTH_RADIUS ** 2 * epsilon * STEFAN_BOLTZMANN * temperature ** 4;
}

/** Koomey regression, converted from computations/kWh to computations/J. */
export function koomey(year: number): number {
  return Math.exp(0.440243 * year - 849.259) / 3_600_000;
}

/** Dimensionless quartic double-well shape with a linear tilt term. */
export function potential(x: number, alpha: number, tilt = 0): number {
  return x ** 4 - 2 * alpha * x ** 2 + tilt * x;
}

/** Equal-child Murray branching radius: 2 r_child^3 = r_parent^3. */
export function murrayChild(parentRadius: number): number {
  return parentRadius > 0 ? parentRadius * 2 ** (-1 / 3) : 0;
}

export type PhysicsState = {
  temperature: number;
  efficiency: number;
  wasteHeat: number;
  bitEnergy: number;
  year: number;
  absorbedSolar: number;
  outgoingRadiation: number;
  landauerOpsPerJ: number;
};

/**
 * Deterministic frame-derived telemetry. The Koomey line is used only in its
 * chart interval; elsewhere efficiency reports the ideal 1-erasure/op bound.
 * Earth power is the fixed greybody illustration described above.
 */
export function state(frame: number): PhysicsState {
  const f = Math.max(0, Math.min(7199, Number.isFinite(frame) ? frame : 0));
  let temperature = ROOM_TEMPERATURE;
  if (f >= 3600 && f < 5400) {
    temperature = 300 + 45 * smoothstep((f - 3600) / 1800);
  } else if (f >= 5400) {
    temperature = 300 + (CMB_TEMPERATURE - 300) * smoothstep((f - 5400) / 900);
  }

  const year = 1946 + 134 * clamp01((f - 1800) / 1800);
  const landauerOpsPerJ = 1 / landauer(temperature);
  const efficiency = f >= 1800 && f < 3600
    ? Math.min(koomey(year), 1 / landauer(ROOM_TEMPERATURE))
    : landauerOpsPerJ;
  const outgoingRadiation = radiated(temperature);

  return {
    temperature,
    efficiency,
    wasteHeat: Math.max(0, outgoingRadiation - ABSORBED_SOLAR),
    bitEnergy: landauer(temperature),
    year,
    absorbedSolar: ABSORBED_SOLAR,
    outgoingRadiation,
    landauerOpsPerJ,
  };
}
