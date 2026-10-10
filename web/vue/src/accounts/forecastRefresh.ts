export interface ForecastPoint {
  snapshot_date: string
  value_cents: number
}

/** Each new refresh invalidates results from all earlier requests. */
export const createRefreshGate = () => {
  let generation = 0
  return {
    begin: () => ++generation,
    isCurrent: (token: number) => token === generation,
  }
}

/** Fetch the longest horizon once and reuse its daily path for shorter widgets. */
export async function loadForecastRanges<T extends ForecastPoint>(
  fetchForecast: (throughDate: string) => Promise<T[]>,
  anchor: string,
  next30: string,
  projection: string,
  today: string,
) {
  const points = await fetchForecast(projection > next30 ? projection : next30)
  return {
    projection: points,
    next30: points.filter((point) => point.snapshot_date <= next30),
    trend: anchor > today ? points.filter((point) => point.snapshot_date <= anchor) : [],
  }
}
