export function configureSingleInstance(app, focusExistingWindow) {
  const primary = app.requestSingleInstanceLock();
  if (!primary) {
    app.quit();
    return false;
  }
  app.on("second-instance", focusExistingWindow);
  return true;
}
