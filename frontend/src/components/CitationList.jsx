import React from "react";
import "./CitationList.css";

function formatScore(value) {
  if (typeof value !== "number") return "";
  return value.toFixed(3);
}

function citationTitle(citation) {
  return citation.display_name || citation.source_label || citation.filename || "Uploaded document";
}

function terms(citation) {
  if (Array.isArray(citation.matched_terms)) return citation.matched_terms.slice(0, 8);
  return [];
}

export default function CitationList({ citations }) {
  const items = Array.isArray(citations) ? citations.filter(Boolean) : [];
  if (!items.length) return null;

  return (
    <div className="citation-list" aria-label="Sources">
      <div className="citation-list-title">Sources</div>
      {items.map((citation, index) => {
        const key = citation.chunk_id || citation.id || `${citation.filename || "source"}-${index}`;
        const matchedTerms = terms(citation);
        return (
          <details className="citation-card" key={key}>
            <summary>
              <span className="citation-id">{citation.label || `[S${index + 1}]`}</span>
              <span className="citation-name">{citationTitle(citation)}</span>
              {typeof citation.score === "number" ? (
                <span className="citation-score">{formatScore(citation.score)}</span>
              ) : null}
            </summary>
            {citation.snippet ? <p className="citation-snippet">{citation.snippet}</p> : null}
            {matchedTerms.length ? (
              <div className="citation-terms">
                {matchedTerms.map((term) => (
                  <span key={term}>{term}</span>
                ))}
              </div>
            ) : null}
          </details>
        );
      })}
    </div>
  );
}
