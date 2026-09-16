import type { Transaction } from '../../api/client';

export function ConfidenceBadge({ transaction }: { transaction: Transaction }) {
  if (transaction.category === null) {
    return <span className="badge badge-slate">uncategorized</span>;
  }

  const confidence = transaction.confidence;
  const tone =
    confidence === null
      ? 'slate'
      : confidence >= 0.9
        ? 'green'
        : confidence >= 0.5
          ? 'amber'
          : 'red';
  const percent = confidence === null ? '' : `${Math.round(confidence * 100)}%`;
  const source = transaction.category_source ?? '';
  const label = percent ? `${percent} · ${source}` : source;

  return <span className={`badge badge-${tone}`}>{label}</span>;
}
