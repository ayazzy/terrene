export type ReadFailure = { message: string; status?: number };
export type ReadResult<T> =
  | { data: T; failure: null }
  | { failure: ReadFailure };

// Each read settles independently so an unavailable optional source cannot
// discard successfully fetched saved assessments.
export async function readResource<T>(
  read: () => Promise<T>,
): Promise<ReadResult<T>> {
  try {
    return { data: await read(), failure: null };
  } catch (error) {
    return {
      failure: {
        message: error instanceof Error ? error.message : String(error),
        status:
          error instanceof Error &&
          'status' in error &&
          typeof error.status === 'number'
            ? error.status
            : undefined,
      },
    };
  }
}
export function isAccessFailure(failure?: ReadFailure | null) {
  return failure?.status === 401 || failure?.status === 403;
}
export function criticalReadFailure(
  failures: {
    sites?: ReadFailure | null;
    datasets?: ReadFailure | null;
    health?: ReadFailure | null;
    history?: ReadFailure | null;
  },
  hasLoadedSites: boolean,
) {
  return (
    Object.values(failures).find(isAccessFailure) ||
    (!hasLoadedSites ? failures.sites : null) ||
    null
  );
}
