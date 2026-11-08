import type { MobileRole } from './identity';

// A photo picker may retain an in-memory form behind the privacy mask. Ordinary
// background transitions discard it. Only a current online check reveals data.
export class SessionVisibility {
  private generation = 0;
  private active = false;
  private live = true;
  private interactive = false;
  private pickerDepth = 0;
  private readonly check: () => Promise<MobileRole>;
  private readonly update: (role: MobileRole | null | undefined, visible: boolean, denied?: boolean) => void;

  constructor(
    check: () => Promise<MobileRole>,
    update: (role: MobileRole | null | undefined, visible: boolean, denied?: boolean) => void,
  ) { this.check = check; this.update = update; }

  start(state: string) {
    this.live = true;
    this.changed(state);
  }

  changed(state: string) {
    if (!this.live) return;
    this.active = state === 'active';
    const generation = ++this.generation;
    if (!this.active) {
      this.update(this.pickerDepth ? undefined : null, false);
      return;
    }
    this.update(undefined, false);
    if (this.interactive) return;
    const current = () => this.live && this.active && generation === this.generation;
    this.check().then(role => {
      if (current()) this.update(role, true);
    }).catch(() => {
      if (current()) this.update(null, false, true);
    });
  }

  async photoActivity(select: () => Promise<void>) {
    ++this.pickerDepth;
    try { await select(); }
    finally { --this.pickerDepth; }
  }

  beginInteractive() {
    this.interactive = true;
    ++this.generation;
    this.update(null, false);
  }

  finishInteractive(role: MobileRole | null) {
    this.interactive = false;
    ++this.generation;
    if (this.live) this.update(role, this.active && role !== null);
  }

  dispose() {
    this.live = false;
    ++this.generation;
  }
}
