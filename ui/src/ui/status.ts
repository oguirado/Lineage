type AnnouncementKind = 'update' | 'status' | 'alert';

const alertChannels = new Set([
  'error', 'validation', 'refused', 'refusal', 'create-refused', 'agents-error',
  'arena:error', 'lineage:error', 'ledger:read-error', 'ledger:verify-error',
  'ledger:export-validation', 'ledger:export-error',
]);
const updateChannels = new Set([
  'ready', 'loading', 'stale', 'notice', 'agents-loading', 'agents-ready',
  'ledger:fold', 'ledger:focus', 'ledger:removal', 'ledger:resync', 'lineage:removed',
]);

function announcementKind(key: string): AnnouncementKind {
  // Screen keys begin with a caller-defined channel. The rest is deduplication data.
  const [source, topic] = key.split(':', 2);
  const channel = source === 'arena' || source === 'ledger' || source === 'lineage'
    ? `${source}:${topic}` : source;
  if (alertChannels.has(channel)) return 'alert';
  // Screen-local restoreFocus callers use the same serialized removal key.
  if (updateChannels.has(channel) || key.startsWith('["removed",')) return 'update';
  return 'status';
}

/** Persistent announcements plus an AX outcome whose name contains the result. */
export function createStatusRegion(host: HTMLElement) {
  const element = document.createElement('div');
  element.setAttribute('role', 'status');
  element.setAttribute('aria-label', 'Application updates');
  element.setAttribute('aria-live', 'polite');
  element.setAttribute('aria-atomic', 'true');
  element.className = 'application-status';
  host.append(element);

  const outcome = document.createElement('output');
  outcome.className = 'action-outcome';
  outcome.hidden = true;
  host.append(outcome);

  let disposed = false;
  let lastOutcome: {key: string; message: string; kind: AnnouncementKind} | null = null;
  return {
    element,
    clear() {
      lastOutcome = null;
      outcome.hidden = true;
      outcome.textContent = '';
      outcome.removeAttribute('aria-label');
      outcome.removeAttribute('role');
    },
    announce(key: string, message: string, kind = announcementKind(key)) {
      if (disposed) return;
      if (kind !== 'update' && lastOutcome?.key === key
          && lastOutcome.message === message && lastOutcome.kind === kind) return;
      if (element.textContent !== message) element.textContent = message;
      if (kind === 'update') return;

      lastOutcome = {key, message, kind};
      const text = kind === 'alert' && !message.startsWith('Error:') ? 'Error: ' + message : message;
      outcome.hidden = false;
      outcome.textContent = text;
      outcome.setAttribute('aria-label', text);
      if (kind === 'alert') outcome.setAttribute('role', 'alert');
      else outcome.removeAttribute('role');
    },
    dispose() { disposed = true; },
  };
}
