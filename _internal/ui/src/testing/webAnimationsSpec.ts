// Web Animations "cancel an animation": the finished promise is rejected with an AbortError and marked handled, so a
// cancelled animation is never an unhandled rejection in a browser. happy-dom rejects without marking it handled, so every
// exit motion cut short (Presence, Collapse, morphs) surfaced as "Unhandled Rejection: AbortError" and failed the run.
// Code that awaits `animation.finished` itself still sees the rejection, exactly as in a browser.
type Cancellable = { finished?: Promise<unknown>; cancel(): void };

const proto = (globalThis as { Animation?: { prototype: Cancellable } }).Animation?.prototype;
if (proto) {
  const cancel = proto.cancel;
  proto.cancel = function (this: Cancellable) {
    this.finished?.catch(() => undefined);
    cancel.call(this);
  };
}
