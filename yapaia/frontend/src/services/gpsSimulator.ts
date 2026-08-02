type PositionCallback = (lon: number, lat: number, speedKmh: number, heading: number) => void;

let timer: ReturnType<typeof setInterval> | null = null;

function haversineM(a: [number, number], b: [number, number]): number {
  const R = 6_371_000;
  const dLat = (b[1] - a[1]) * Math.PI / 180;
  const dLon = (b[0] - a[0]) * Math.PI / 180;
  const s = Math.sin(dLat / 2) ** 2
    + Math.cos(a[1] * Math.PI / 180) * Math.cos(b[1] * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
}

export function startSimulator(
  coords: [number, number][],
  callback: PositionCallback,
  /** Per-waypoint speed in km/h (from route max_speed). Falls back to 50. */
  speedsKmh: number[] = [],
  /** Reactive multiplier — read each tick so live changes take effect. */
  getMultiplier: () => number = () => 1,
  intervalMs = 100,
) {
  stopSimulator();
  if (coords.length < 2) return;

  // Pre-compute cumulative distances
  const cumDist: number[] = [0];
  for (let i = 1; i < coords.length; i++) {
    cumDist.push(cumDist[i - 1] + haversineM(coords[i - 1], coords[i]));
  }
  const totalDist = cumDist[cumDist.length - 1];
  let distanceTraveled = 0;

  function segmentAt(d: number): number {
    let lo = 0, hi = cumDist.length - 2;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (cumDist[mid] <= d) lo = mid; else hi = mid - 1;
    }
    return lo;
  }

  timer = setInterval(() => {
    // Speed at current position (before advancing)
    const curSeg = segmentAt(distanceTraveled);
    const speed = speedsKmh[curSeg] ?? 50;
    const multiplier = Math.max(0.1, getMultiplier());

    distanceTraveled += intervalMs * speed / 3.6 / 1000 * multiplier;

    if (distanceTraveled >= totalDist) {
      const last = coords[coords.length - 1];
      callback(last[0], last[1], 0, 0);
      stopSimulator();
      return;
    }

    const i = segmentAt(distanceTraveled);
    const segLen = cumDist[i + 1] - cumDist[i];
    const t = segLen > 0 ? (distanceTraveled - cumDist[i]) / segLen : 0;
    const lon = coords[i][0] + (coords[i + 1][0] - coords[i][0]) * t;
    const lat = coords[i][1] + (coords[i + 1][1] - coords[i][1]) * t;

    const dLon = coords[i + 1][0] - coords[i][0];
    const dLat = coords[i + 1][1] - coords[i][1];
    let heading = (Math.atan2(dLon, dLat) * 180) / Math.PI;
    if (heading < 0) heading += 360;

    callback(lon, lat, speed, heading);
  }, intervalMs);
}

export function stopSimulator() {
  if (timer) { clearInterval(timer); timer = null; }
}

export function isRunning(): boolean {
  return timer !== null;
}
