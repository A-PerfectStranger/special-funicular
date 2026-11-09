// Keep the first failure observable while always attempting required recovery.
export async function withRecovery(operation, recover, captureFailure) {
  let failed = false, failure;
  try { await operation(); }
  catch (error) { failed = true; failure = error; captureFailure('operation'); }
  try { await recover(); }
  catch (error) {
    captureFailure('recovery');
    if (!failed) { failed = true; failure = error; }
  }
  if (failed) throw failure;
}
