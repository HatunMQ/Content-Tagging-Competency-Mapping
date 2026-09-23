// Single source of truth for how each real Learning_type value (from
// content.json, produced by tag_chunks.py's AI tagging against the VARK
// taxonomy) is DISPLAYED to the user. The underlying data/taxonomy value
// itself is never changed here -- content.json still stores "Kinesthetic"
// exactly as the model tagged it. Only the on-screen label changes, so
// grouping/filtering logic elsewhere keeps using the real raw value.
//
// "Kinesthetic" (VARK's term for hands-on/practice-based learning) reads
// as jargon to a learner, so it's shown as "Practice" instead -- everything
// else passes through unchanged. Add new mappings here, not scattered
// across components, if the taxonomy grows.
const DISPLAY_LABELS = {
  Kinesthetic: "Practice",
};

export function learningTypeLabel(rawValue) {
  return DISPLAY_LABELS[rawValue] || rawValue;
}
